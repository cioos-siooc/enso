"""Command-line entry point for the NOAA CPC land pipeline.

    python -m CPC.cli init                                  # schema (land tables)
    python -m CPC.cli fetch    [--year|--start-year|--end-year] [--variable]
    python -m CPC.cli backfill [--year ...] [--product] [--fresh]
    python -m CPC.cli run      [--recheck-days N]           # the daily job
    python -m CPC.cli scan
    python -m CPC.cli status

**A sibling of `CRW.cli`, not a subcommand of it.** CPC is the Climate Prediction
Center, a different NOAA program from Coral Reef Watch, and the mechanics differ
in the way that matters most to a CLI: a CPC file is a **year**, not a date. So
`fetch` takes years, `backfill` walks years, and `run` re-fetches the current
year's three files and ingests whatever days have appeared in them.

**There is no prune and no render here yet.** The whole land archive from 1985 is
~9.5 GB for all three variables, so unlike the ~153 GB ocean archive it is kept
forever — which means land history stays re-ingestable and re-renderable without
a re-download, and there is no retention window to reason about. Rendering,
climatology and anomaly are the next step; this package's job stops at a
populated table.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

from shared.ch import DATABASE, ensure_schema, get_client

from . import config, download, ingest, status as status_mod

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
    this_year = dt.date.today().year
    fetched = failed = skipped = 0

    with download.new_client() as client:
        for year in _years(args):
            for name in _variables(args):
                product = download.product(name)
                path = config.land_path(name, year)
                remote = download.head(year, product, client)

                if remote is None:
                    if year >= this_year:
                        log.info("%s not published yet", product.filename(year))
                    else:
                        log.warning("%s unavailable at the source", product.filename(year))
                    continue

                if path.exists() and not args.force:
                    # A past year matching on size is done. The current year is
                    # checked on size too, which is what notices appended days.
                    if path.stat().st_size == remote[0]:
                        skipped += 1
                        continue

                try:
                    download.fetch(year, product, client=client)
                except Exception:  # noqa: BLE001 — one year must not stop the rest
                    log.exception("failed to download %s", product.filename(year))
                    failed += 1
                else:
                    fetched += 1

    log.info("fetch: %d downloaded, %d already current, %d failed", fetched, skipped, failed)
    return 1 if failed else 0


def cmd_backfill(args) -> int:
    """Ingest the year files already on disk.

    Tolerates a partial archive, like `CRW.cli backfill`: re-running picks up
    whatever has since been fetched. `--fresh` truncates the selected product's
    table AND its status table together — emptying one without the other would
    make every date look ingested while its rows were gone.
    """
    client = get_client()
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
    finally:
        client.close()
    return 0


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


def cmd_run(args) -> int:
    """The daily job: fetch the current year's files, ingest what is new.

    **No date range and no catch-up watermark**, unlike `CRW.cli run`. A year
    file holds every day of its year, so "what is new" is simply the dates in it
    that status does not have — a missed run, a late publication and a normal day
    are all the same code path with no argument.

    `--recheck-days` re-ingests the trailing window regardless of status. CPC is
    a near-real-time gauge analysis and revises its recent end as more stations
    report, and that revision happens INSIDE an unchanged-looking year file — so
    unlike CoralTemp there is no per-date size or mtime that could reveal it.
    """
    today = dt.date.today()
    years = sorted({today.year, (today - dt.timedelta(days=args.recheck_days)).year})
    recheck_floor = today - dt.timedelta(days=args.recheck_days)

    fetch_args = argparse.Namespace(year=years, variable=None, force=False)
    if cmd_fetch(fetch_args):
        log.warning("some downloads failed; ingesting what landed")

    client = get_client()
    try:
        for tgt in _targets(args):
            for year in years:
                missing = [
                    name for name in tgt.variables
                    if not config.land_path(name, year).exists()
                ]
                if missing:
                    log.warning("%d: %s not on disk, skipping", year, ", ".join(missing))
                    continue

                # One pass: everything status does not have, plus the recheck
                # window re-ingested whether it has it or not.
                recheck = {
                    recheck_floor + dt.timedelta(days=n)
                    for n in range((today - recheck_floor).days + 1)
                }
                counts = ingest_one_year(client, year, tgt, args, force_dates=recheck)
                log.info(
                    "%d %s: %d ingested (incl. the %d-day recheck), %d skipped, "
                    "%d failed, %s rows",
                    year, tgt.key, counts["ingested"], args.recheck_days,
                    counts["skipped"], counts["failed"], f"{counts['rows']:,}",
                )
            last = status_mod.last_ingested(client, tgt.status_table)
            log.info("%s last ingested: %s", tgt.key, last)
    finally:
        client.close()
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
    p_run.set_defaults(func=cmd_run)

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
