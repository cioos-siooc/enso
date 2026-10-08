"""Command-line entry point for the NOAA CPC land pipeline.

    python -m CPC.cli init                                  # schema (land tables)
    python -m CPC.cli fetch    [--year|--start-year|--end-year] [--variable]
    python -m CPC.cli backfill [--year ...] [--product] [--fresh]
    python -m CPC.cli run      [--recheck-days N] [--keep-nc] [--force]  # the scheduled job
    python -m CPC.cli clim     [--source]                   # 1991-2020 climatology
    python -m CPC.cli render   [--variable|--period|--start|--end] [--workers N]
    python -m CPC.cli prune    [--year ...] [--product] [--dry-run]
    python -m CPC.cli ocean-mask --date YYYY-MM-DD          # rebuild the coastline cut
    python -m CPC.cli scan
    python -m CPC.cli status

**A sibling of `CRW.cli`, not a subcommand of it.** CPC is the Climate Prediction
Center, a different NOAA program from Coral Reef Watch, and the mechanics differ
in the way that matters most to a CLI: a CPC file is a **year**, not a date. So
`fetch` takes years, `backfill` walks years, and `run` re-fetches the current
year's three files and ingests whatever days have appeared in them.

**The year files are deleted once used.** Every frame is pre-rendered and the
API never renders, so a year file is only needed until its days are ingested
and every frame they feed is in the cache — `prune` checks exactly that before
deleting (see `CPC/prune.py`). Order on a fresh box: `fetch` -> `backfill` ->
`clim` -> `render` -> `prune`. `run` prunes what it fetched at the end of every
run, so the current year is downloaded afresh daily, which it would be anyway:
CPC rewrites that file in place.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from dataclasses import dataclass

from shared.ch import DATABASE, ensure_schema, get_client
from shared.domain import variables as all_variables
from shared.fields import land_last_date, land_layer_ready
from shared.periods import PERIODS, span, start_of
from shared.render import DEFAULT_WIDTH

from CRW import imaging

from . import climatology, config, download, ingest, prune as prune_mod, status as status_mod

log = logging.getLogger(__name__)


def _parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None


def _years(args) -> list[int]:
    """The years a command covers, from `--year` or `--start-year`/`--end-year`."""
    if getattr(args, "year", None):
        return sorted(set(args.year))
    start = dt.date(args.start_year, 1, 1) if getattr(args, "start_year", None) else None
    end = dt.date(args.end_year, 12, 31) if getattr(args, "end_year", None) else None
    return config.archive_years(start, end)


def _targets(args) -> list[ingest.Target]:
    key = getattr(args, "product", None)
    return [ingest.target(key)] if key else [ingest.TEMP_TARGET, ingest.PRECIP_TARGET]


def _variables(args) -> list[str]:
    """Which of the three source variables a fetch covers."""
    if getattr(args, "variable", None):
        return list(args.variable)
    return list(config.LAND_VARIABLES)


def cmd_init(args) -> int:
    """Create the land tables. Idempotent, and fast — there is no climatology yet.

    Deliberately not the ocean side's `init`, which also loads 366 climatology
    files over ~20 minutes. A land climatology is computable from
    `land_temp_daily` / `land_precip_daily` once they are populated, since every
    year file stays on disk; that is the next step's problem, not this one's.
    """
    ensure_schema()
    log.info("land tables ready in database %s", DATABASE)
    return 0


def cmd_fetch(args) -> int:
    """Download year files, skipping ones already on disk and unchanged.

    A PAST year is fetched once and never again: it is immutable at the source
    (`tmax.2015.nc` was last modified in 2020). The CURRENT year is re-fetched
    whenever the server reports a different size or mtime, which is daily, since
    the file is rewritten in place as days are appended.
    """
    with download.new_client() as client:
        outcomes = [
            _fetch_year_file(
                client, name, year, download.head(year, download.product(name), client),
                force=args.force,
            )
            for year in _years(args) for name in _variables(args)
        ]
    return _report_fetch(outcomes)


def _fetch_year_file(client, name: str, year: int, remote, *, force: bool) -> str:
    """Download one year file unless the copy on disk already matches `remote`.

    `remote` is the file's `(size, mtime)` from a HEAD, or None if the source did
    not answer. Returns `fetched`, `current`, `unpublished` or `failed`.
    """
    product = download.product(name)
    if remote is None:
        if year >= dt.date.today().year:
            log.info("%s not published yet", product.filename(year))
        else:
            log.warning("%s unavailable at the source", product.filename(year))
        return "unpublished"

    path = config.land_path(name, year)
    # A past year matching on size is done. The current year is checked on size
    # too, which is what notices appended days.
    if path.exists() and not force and path.stat().st_size == remote[0]:
        return "current"

    try:
        download.fetch(year, product, client=client)
    except Exception:  # noqa: BLE001 — one year must not stop the rest
        log.exception("failed to download %s", product.filename(year))
        return "failed"
    return "fetched"


def _report_fetch(outcomes: list[str]) -> int:
    log.info(
        "fetch: %d downloaded, %d already current, %d failed",
        outcomes.count("fetched"), outcomes.count("current"), outcomes.count("failed"),
    )
    return 1 if "failed" in outcomes else 0


def cmd_backfill(args) -> int:
    """Ingest the year files already on disk.

    Tolerates a partial archive, like `CRW.cli backfill`: re-running picks up
    whatever has since been fetched. `--fresh` truncates the selected product's
    table AND its status table together — emptying one without the other would
    make every date look ingested while its rows were gone.
    """
    client = get_client()
    failed = 0
    try:
        for tgt in _targets(args):
            if args.fresh:
                log.warning("truncating %s and %s", tgt.table, tgt.status_table)
                client.command(f"TRUNCATE TABLE IF EXISTS {DATABASE}.{tgt.table}")
                client.command(f"TRUNCATE TABLE IF EXISTS {DATABASE}.{tgt.status_table}")

            totals = {"ingested": 0, "skipped": 0, "failed": 0, "rows": 0}
            for year in _years(args):
                missing = [
                    name for name in tgt.variables
                    if not config.land_path(name, year).exists()
                ]
                if missing:
                    log.info("%d: %s not on disk, skipping", year, ", ".join(missing))
                    continue
                counts = ingest_one_year(client, year, tgt, args)
                for key in totals:
                    totals[key] += counts[key]
                log.info(
                    "%d %s: %d ingested, %d skipped, %d failed, %s rows",
                    year, tgt.key, counts["ingested"], counts["skipped"],
                    counts["failed"], f"{counts['rows']:,}",
                )
            log.info(
                "%s total: %d ingested, %d skipped, %d failed, %s rows",
                tgt.key, totals["ingested"], totals["skipped"], totals["failed"],
                f"{totals['rows']:,}",
            )
            failed += totals["failed"]
    finally:
        client.close()
    return 1 if failed else 0


def ingest_one_year(client, year: int, tgt: ingest.Target, args, **kwargs) -> dict[str, int]:
    """`ingest.ingest_year` with this CLI's shared options applied."""
    return ingest.ingest_year(
        client, year, tgt=tgt,
        force=getattr(args, "force", False),
        start=getattr(args, "start", None) or config.ARCHIVE_START,
        end=getattr(args, "end", None),
        source_url=download.product(tgt.variables[0]).url(year),
        **kwargs,
    )


@dataclass(frozen=True)
class RunPlan:
    """What one `run` covers, decided by its HEADs before anything is fetched.

    `targets` are the products with a changed year file (all of them under
    `force`), `unchanged` the keys of the rest. `remote` is every year file's
    `(size, mtime)` as HEAD saw it BEFORE the download, which is the version a
    successful run records — so a file rewritten mid-run reads as changed next
    time rather than as handled. `None` is not published, or the host is down.
    """

    today: dt.date
    recheck_floor: dt.date
    years: list[int]
    targets: list[ingest.Target]
    unchanged: list[str]
    remote: dict[tuple[str, int], tuple[int, str] | None]

    @property
    def recheck(self) -> set[dt.date]:
        """The trailing window re-ingested whether status has it or not."""
        return {
            self.recheck_floor + dt.timedelta(days=n)
            for n in range((self.today - self.recheck_floor).days + 1)
        }


def plan_run(
    product: str | None = None, recheck_days: int = 14, force: bool = False
) -> RunPlan:
    """`run`'s first stage: which years it covers, and which products changed.

    **It is a HEAD per year file, and the run stops here if none has changed**
    since the last run that finished with it (`land_source_files`). The files
    change about once a day and the run fires hourly, so without this every
    firing would download ~200 MB to find nothing new. The check is per
    product: temperature and precipitation are rewritten at different hours,
    and one being new does not make the other worth fetching. `force` skips it.
    """
    today = dt.date.today()
    recheck_floor = today - dt.timedelta(days=recheck_days)
    # Every year a re-rendered bucket reads from, not just the recheck window's:
    # the month containing the floor starts earlier, and a week containing
    # early January starts in the previous December. Those files may have been
    # pruned by the last run, so they are fetched again.
    earliest = min(start_of(recheck_floor, p) for p in PERIODS)
    years = list(range(earliest.year, today.year + 1))
    targets = [ingest.target(product)] if product else [ingest.TEMP_TARGET, ingest.PRECIP_TARGET]

    # A None (not published yet, or the host is down) counts as unchanged:
    # there is nothing to fetch, and the next run asks again.
    with download.new_client() as http:
        remote = {
            (name, year): download.head(year, download.product(name), http)
            for tgt in targets for name in tgt.variables for year in years
        }
    client = get_client()
    try:
        seen = status_mod.seen_versions(client)
    finally:
        client.close()

    def changed(tgt: ingest.Target) -> bool:
        return any(
            remote[(name, year)] is not None and remote[(name, year)] != seen.get((name, year))
            for name in tgt.variables for year in years
        )

    unchanged: list[str] = []
    if not force:
        unchanged = [tgt.key for tgt in targets if not changed(tgt)]
        targets = [tgt for tgt in targets if changed(tgt)]
        if unchanged:
            log.info("%s: no year file changed since the last run", ", ".join(unchanged))
    return RunPlan(today, recheck_floor, years, targets, unchanged, remote)


def fetch_product(plan: RunPlan, tgt: ingest.Target) -> bool:
    """Download `tgt`'s year files for the run. False if any download failed.

    Against the HEADs `plan_run` already made, rather than asking again.
    """
    with download.new_client() as client:
        outcomes = [
            _fetch_year_file(client, name, year, plan.remote[(name, year)], force=False)
            for year in plan.years for name in tgt.variables
        ]
    return _report_fetch(outcomes) == 0


def ingest_product_year(client, plan: RunPlan, tgt: ingest.Target, year: int) -> dict[str, int]:
    """Ingest one year file: every day status lacks, plus the recheck window.

    Raises `FileNotFoundError` when a file is not on disk — a failed download,
    or a year not published yet.
    """
    missing = [name for name in tgt.variables if not config.land_path(name, year).exists()]
    if missing:
        raise FileNotFoundError(f"{year}: {', '.join(missing)} not on disk")
    args = argparse.Namespace(start=None, end=None, force=False)
    counts = ingest_one_year(client, year, tgt, args, force_dates=plan.recheck)
    log.info(
        "%d %s: %d ingested (incl. the %d-day recheck), %d skipped, %d failed, %s rows; "
        "last ingested %s",
        year, tgt.key, counts["ingested"], (plan.today - plan.recheck_floor).days,
        counts["skipped"], counts["failed"], f"{counts['rows']:,}",
        status_mod.last_ingested(client, tgt.status_table),
    )
    return counts


def render_product(plan: RunPlan, tgt: ingest.Target) -> int:
    """Re-render every bucket the recheck window touches, open or closed.

    A CPC revision lands INSIDE a year file, so a week that closed a fortnight
    ago can still change — and its cached frame with it. Unconditional writes,
    the same rule `imaging.render_date` follows for the ocean's open buckets.
    """
    rendered = render_touched(tgt, plan.recheck_floor)
    log.info("%s: re-rendered %d land frame(s)", tgt.key, rendered)
    return rendered


def finish_product(
    client, plan: RunPlan, tgt: ingest.Target, *, succeeded: bool, keep_nc: bool
) -> tuple[int, int] | None:
    """Record `tgt`'s versions as done, then prune what the run fetched.

    Only a product that `succeeded` records its versions; one with a failure
    records nothing and is retried by the next run. The prune goes through the
    same check as `CPC.cli prune`: a year whose frames are not all rendered
    stays until `CPC.cli render` has run. Returns `(deleted, kept)`, or None
    under `keep_nc`.
    """
    if succeeded:
        status_mod.record_versions(client, {
            (name, year): plan.remote[(name, year)]
            for name in tgt.variables for year in plan.years
            if plan.remote[(name, year)] is not None
        })
    if keep_nc:
        return None
    return prune_mod.prune(client, tgt, plan.years)


def run(
    *,
    product: str | None = None,
    recheck_days: int = 14,
    keep_nc: bool = False,
    force: bool = False,
) -> str:
    """The scheduled job: fetch the current year's files, ingest what is new.

    Returns the outcome: `unchanged`, `ingested` or `failed`. `flows.land_run`
    calls the same stages — `plan_run`, `fetch_product`, `ingest_product_year`,
    `render_product`, `finish_product`, in this order — as Prefect tasks, so
    the scheduled run and the CLI are the same job.

    **No date range and no catch-up watermark**, unlike `CRW.cli run`. A year
    file holds every day of its year, so "what is new" is simply the dates in it
    that status does not have — a missed run, a late publication and a normal day
    are all the same code path with no argument.

    `recheck_days` re-ingests the trailing window regardless of status. CPC is
    a near-real-time gauge analysis and revises its recent end as more stations
    report, and that revision happens INSIDE the year file — so unlike CoralTemp
    there is no per-date size or mtime that could reveal it. It does change the
    file's own size and mtime, which is what the HEAD check reads.

    A product whose download failed still ingests what is on disk, but counts
    as failed: its versions are not recorded, so the next run fetches again.
    """
    plan = plan_run(product, recheck_days, force)
    if not plan.targets:
        return "unchanged"

    failed: set[str] = set()
    for tgt in plan.targets:
        if not fetch_product(plan, tgt):
            log.warning("%s: some downloads failed; ingesting what landed", tgt.key)
            failed.add(tgt.key)

    client = get_client()
    try:
        for tgt in plan.targets:
            for year in plan.years:
                try:
                    counts = ingest_product_year(client, plan, tgt, year)
                except FileNotFoundError as exc:
                    log.warning("%s, skipping", exc)
                    failed.add(tgt.key)
                    continue
                if counts["failed"]:
                    failed.add(tgt.key)
    finally:
        client.close()

    for tgt in plan.targets:
        render_product(plan, tgt)

    client = get_client()
    try:
        for tgt in plan.targets:
            finish_product(
                client, plan, tgt, succeeded=tgt.key not in failed, keep_nc=keep_nc
            )
    finally:
        client.close()
    return "failed" if failed else "ingested"


def cmd_run(args) -> int:
    """`run`, from the command line. Exit 1 if any product failed."""
    outcome = run(
        product=args.product, recheck_days=args.recheck_days,
        keep_nc=args.keep_nc, force=args.force,
    )
    log.info("run: %s", outcome)
    return 1 if outcome == "failed" else 0


layers_for = prune_mod.layers_for

def climatology_ready(layer: str) -> bool:
    """See `shared.fields.land_layer_ready` — one definition, shared with `/coverage`."""
    return land_layer_ready(layer)


def product_last_date(tgt: ingest.Target) -> dt.date | None:
    """The last day this product's files ALL hold.

    Temperature needs tmax and tmin both, so it ends at the earlier of the two;
    and temperature and rainfall do not end on the same day (measured one day
    apart), which is why this is per product and never shared.
    """
    ends = [land_last_date(name) for name in tgt.variables]
    return None if any(e is None for e in ends) else min(ends)


def render_touched(tgt: ingest.Target, since: dt.date, width: int = DEFAULT_WIDTH) -> int:
    """Rewrite every bucket of `tgt`'s layers containing a day from `since` on."""
    hi = product_last_date(tgt)
    if hi is None or hi < since:
        return 0
    layers = [name for name in layers_for(tgt) if climatology_ready(name)]
    skipped = sorted(set(layers_for(tgt)) - set(layers))
    if skipped:
        log.warning("no matching climatology for %s; run `CPC.cli clim`", ", ".join(skipped))

    jobs: set[tuple[dt.date, str, str]] = set()
    day = since
    while day <= hi:
        for period in PERIODS:
            for name in layers:
                if period in all_variables()[name].periods:
                    jobs.add((span(day, period)[0], period, name))
        day += dt.timedelta(days=1)

    # Across the render pool, like `CPC.cli render`: a 14-day recheck touches
    # ~100 frames per product, which one at a time was minutes of every run.
    imaging.render_jobs([(bucket, period, name, width) for bucket, period, name in sorted(jobs)])
    return len(jobs)


def cmd_clim(args) -> int:
    """Build the 1991-2020 climatology for each land source, from the year files.

    Minutes, not hours: 30 year files per source, read once each. Rebuild after
    editing a layer's `baseline.window_days` — the anomaly reader refuses a file
    built for a different window rather than serving it under the new label.
    """
    sources = args.source or list(config.LAND_VARIABLES)
    failed = 0
    for source in sources:
        try:
            climatology.build(source)
        except FileNotFoundError as exc:
            log.error("%s", exc)
            failed += 1
    return 1 if failed else 0


def cmd_render(args) -> int:
    """Render every closed land bucket, in parallel, through the ocean's machinery.

    `CRW.imaging.render_range` is generic — it goes through `bucket_field`,
    which dispatches land layers to their own reader — so there is no second
    render loop here. What is land-specific is the RANGE: it is bounded per
    product, because temperature and rainfall end on different days, and a layer
    whose climatology is missing or stale is skipped with a warning rather than
    queued to fail inside a worker.
    """
    wanted = set(args.variable or [])
    periods = tuple(args.period or PERIODS)
    total = {"rendered": 0, "skipped": 0, "pending": 0, "empty": 0, "bytes": 0, "seconds": 0.0}

    for tgt in (ingest.TEMP_TARGET, ingest.PRECIP_TARGET):
        layers = [n for n in layers_for(tgt) if not wanted or n in wanted]
        if not layers:
            continue
        stale = [n for n in layers if not climatology_ready(n)]
        if stale:
            log.warning("skipping %s: no matching climatology; run `CPC.cli clim`",
                        ", ".join(stale))
        layers = [n for n in layers if n not in stale]
        hi = product_last_date(tgt)
        if not layers or hi is None:
            continue
        lo = max(args.start or config.ARCHIVE_START, config.ARCHIVE_START)
        hi = min(hi, args.end) if args.end else hi
        if lo > hi:
            continue
        # A year missing mid-range would cache every week and month touching
        # it as a short mean, and once the neighbouring files are pruned that
        # frame can no longer be told apart from a good one. So refuse.
        gaps = [
            f"{name}.{year}" for year in range(start_of(lo, "weekly").year, hi.year + 1)
            for name in tgt.variables
            if year >= config.ARCHIVE_START.year and not config.land_path(name, year).exists()
        ]
        if gaps:
            log.error("%s: year files missing in %s..%s: %s; fetch them first",
                      tgt.key, lo, hi, ", ".join(gaps))
            return 1

        def progress(done, n, written, elapsed, key=tgt.key):
            rate = done / elapsed if elapsed else 0.0
            eta = (n - done) / rate if rate else 0.0
            print(f"  {key} {done}/{n}  {rate:.1f}/s  eta {eta / 60:.1f}m  "
                  f"{written / 1e6:.0f} MB", flush=True)

        print(f"{tgt.key}: {lo} .. {hi} | {','.join(layers)} | {','.join(periods)}")
        counts = imaging.render_range(
            lo, hi, variables=tuple(layers), periods=periods, width=args.width,
            workers=args.workers, force=args.force, limit=args.limit,
            dry_run=args.dry_run, progress=progress,
        )
        for key in total:
            total[key] += counts.get(key, 0)

    print(f"{total['pending']} to render, {total['skipped']} already cached")
    if not args.dry_run:
        print(f"rendered {total['rendered']} image(s), {total['bytes'] / 1e6:.0f} MB "
              f"in {total['seconds'] / 60:.1f}m"
              + (f"; {total['empty']} empty" if total["empty"] else ""))
    return 0


def cmd_prune(args) -> int:
    """Delete year files that are ingested and fully rendered; keep the rest.

    Each kept year is logged with its reason — the first missing day or frame —
    so the answer to "why is this still here" is the fix to run.
    """
    client = get_client()
    deleted = kept = 0
    try:
        for tgt in _targets(args):
            d, k = prune_mod.prune(client, tgt, _years(args), dry_run=args.dry_run)
            deleted, kept = deleted + d, kept + k
    finally:
        client.close()
    log.info("prune: %d product-year(s) %s, %d kept",
             deleted, "deletable" if args.dry_run else "deleted", kept)
    return 0


def cmd_ocean_mask(args) -> int:
    """Rebuild `shared/masks/coraltemp_ocean.npz`, the coastline land frames are cut to.

    Needs one CoralTemp daily file on disk — any date inside the retention
    window will do, since CoralTemp's land is constant. Only needed if the box
    in `domain.yml` moves; the file is committed, because land frames are
    rendered long after the CoralTemp dailies have been pruned.
    """
    from shared.fields import build_ocean_mask, ocean_mask

    path = build_ocean_mask(args.date)
    ocean_mask.cache_clear()
    log.info("%s: %d ocean cells from %s", path, int(ocean_mask().sum()), args.date)
    return 0


def cmd_scan(args) -> int:
    """What is on disk, per variable and year."""
    files = config.scan()
    if not files:
        log.info("no land files in %s", config.LAND_DIR)
        return 0
    by_variable: dict[str, list[int]] = {}
    for f in files:
        by_variable.setdefault(f.variable, []).append(f.year)
    for name in config.LAND_VARIABLES:
        years = sorted(by_variable.get(name, []))
        if not years:
            log.info("%-7s none", name)
            continue
        size = sum(
            config.land_path(name, y).stat().st_size for y in years
        )
        log.info(
            "%-7s %d years, %d..%d, %.1f GB", name, len(years), years[0], years[-1],
            size / 1e9,
        )
    return 0


def cmd_status(args) -> int:
    """Per-status day and row counts, per land product."""
    client = get_client()
    try:
        for tgt in _targets(args):
            rows = client.query(
                f"SELECT status, count(), sum(n_rows), min(date), max(date) "
                f"FROM {DATABASE}.{tgt.status_table} FINAL GROUP BY status ORDER BY status"
            ).result_rows
            if not rows:
                log.info("%s: nothing ingested", tgt.key)
                continue
            for status, days, n_rows, first, last in rows:
                log.info(
                    "%-7s %-16s %6d days  %15s rows  %s..%s",
                    tgt.key, status, days, f"{int(n_rows or 0):,}", first, last,
                )
            total = client.query(
                f"SELECT count() FROM {DATABASE}.{tgt.table}"
            ).result_rows[0][0]
            log.info("%-7s %s rows in %s", tgt.key, f"{total:,}", tgt.table)
    finally:
        client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="CPC.cli", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_years(p):
        p.add_argument("--year", type=int, action="append", help="repeatable")
        p.add_argument("--start-year", type=int)
        p.add_argument("--end-year", type=int)
        return p

    sub.add_parser("init", help="create the land tables").set_defaults(func=cmd_init)

    p_fetch = with_years(sub.add_parser("fetch", help="download year files"))
    p_fetch.add_argument(
        "--variable", choices=config.LAND_VARIABLES, action="append", help="repeatable"
    )
    p_fetch.add_argument("--force", action="store_true", help="re-download even if current")
    p_fetch.set_defaults(func=cmd_fetch)

    p_back = with_years(sub.add_parser("backfill", help="ingest the local archive"))
    p_back.add_argument("--product", choices=sorted(ingest.TARGETS))
    p_back.add_argument("--start", type=_parse_date)
    p_back.add_argument("--end", type=_parse_date)
    p_back.add_argument("--force", action="store_true", help="re-ingest dates already loaded")
    p_back.add_argument(
        "--fresh", action="store_true",
        help="truncate the product's table and its status table first",
    )
    p_back.set_defaults(func=cmd_backfill)

    p_run = sub.add_parser("run", help="fetch the current year and ingest what is new")
    p_run.add_argument("--product", choices=sorted(ingest.TARGETS))
    p_run.add_argument(
        "--recheck-days", type=int, default=14,
        help="re-ingest this trailing window; CPC revises its recent end in place",
    )
    p_run.add_argument(
        "--keep-nc", action="store_true",
        help="keep the year files instead of pruning them at the end",
    )
    p_run.add_argument(
        "--force", action="store_true",
        help="run even if no year file has changed since the last run",
    )
    p_run.set_defaults(func=cmd_run)

    p_clim = sub.add_parser("clim", help="build the 1991-2020 land climatology")
    p_clim.add_argument(
        "--source", choices=config.LAND_VARIABLES, action="append", help="repeatable"
    )
    p_clim.set_defaults(func=cmd_clim)

    land_layers = sorted(n for n, v in all_variables().items() if v.grid == "land")
    p_rend = sub.add_parser("render", help="render closed land buckets in bulk")
    p_rend.add_argument("--variable", choices=land_layers, action="append", help="repeatable")
    p_rend.add_argument("--period", choices=PERIODS, action="append", help="repeatable")
    p_rend.add_argument("--start", type=_parse_date)
    p_rend.add_argument("--end", type=_parse_date)
    p_rend.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    p_rend.add_argument("--workers", type=int)
    p_rend.add_argument("--limit", type=int)
    p_rend.add_argument("--force", action="store_true", help="re-render cached frames")
    p_rend.add_argument("--dry-run", action="store_true")
    p_rend.set_defaults(func=cmd_render)

    p_prune = with_years(sub.add_parser(
        "prune", help="delete year files that are ingested and fully rendered"))
    p_prune.add_argument("--product", choices=sorted(ingest.TARGETS))
    p_prune.add_argument("--dry-run", action="store_true")
    p_prune.set_defaults(func=cmd_prune)

    p_mask = sub.add_parser("ocean-mask", help="rebuild the coastline land frames are cut to")
    p_mask.add_argument("--date", type=_parse_date, required=True,
                        help="a CoralTemp date whose daily file is on disk")
    p_mask.set_defaults(func=cmd_ocean_mask)

    sub.add_parser("scan", help="report what is on disk").set_defaults(func=cmd_scan)

    p_status = sub.add_parser("status", help="summarise pipeline state")
    p_status.add_argument("--product", choices=sorted(ingest.TARGETS))
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
