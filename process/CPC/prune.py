"""Deleting land year files once everything built from them exists.

**The year files are a staging area, not an archive.** Once a year is in
ClickHouse and every map frame it feeds is in the image cache, nothing reads
the file again: the API serves frames from the cache and never renders
(`api/modules/render.py`). So a file is deleted as soon as that is TRUE, and is
checked rather than assumed, because the check is the only thing standing
between a missed render and a frame that can then only come back by
re-downloading.

A `(product, year)` is prunable when, for every day its files hold:

1. **status says ingested** — every date `Jan 1 .. last day in the file`; and
2. **every frame exists** — each bucket of each layer the product feeds, at
   each period the layer is declared at, overlapping those days. That includes
   the week that starts in the previous December, and the anomaly layers, so a
   year cannot be pruned before `CPC.cli clim` has been built and rendered from.

The current year passes the same check. `run` renders its open buckets, so the
file goes at the end of each run and the next run downloads it again — CPC
rewrites it in place daily, so it would be re-downloaded anyway.

**What deletion costs.** `CPC.cli clim` needs 1991-2020 on disk, and a
`render --force` of old history needs its years. Both mean a re-fetch
(~9.5 GB for everything) after a prune. The climatology files themselves
(`climatology/*.clim.nc`) are never touched: every future anomaly frame reads
them.
"""

from __future__ import annotations

import datetime as dt
import logging

from shared.domain import variables as all_variables
from shared.fields import land_file_last_date
from shared.periods import span, start_of
from shared.render import DEFAULT_WIDTH, cache_path

from . import config, ingest, status as status_mod

log = logging.getLogger(__name__)


def layers_for(tgt: ingest.Target) -> list[str]:
    """The land map layers built from a target's source variables."""
    return [
        name for name, v in all_variables().items()
        if v.grid == "land" and v.source in tgt.variables
    ]


def year_last_date(tgt: ingest.Target, year: int) -> dt.date | None:
    """The last day ALL of a product's files hold for `year`, or None."""
    ends = []
    for name in tgt.variables:
        if not config.land_path(name, year).exists():
            return None
        ends.append(land_file_last_date(name, year))
    return None if any(e is None for e in ends) else min(ends)


def missing_frames(
    tgt: ingest.Target, first: dt.date, last: dt.date, width: int = DEFAULT_WIDTH
) -> list[str]:
    """Every frame fed by `first..last` of `tgt` that is not in the cache."""
    missing = []
    variables = all_variables()
    for name in layers_for(tgt):
        for period in variables[name].periods:
            cursor = start_of(first, period)
            while cursor <= last:
                if not cache_path(cursor, width, period, name).is_file():
                    missing.append(f"{name}/{period}/{cursor}")
                cursor = span(cursor, period)[1] + dt.timedelta(days=1)
    return missing


def check(
    tgt: ingest.Target, year: int, ingested: set[dt.date], width: int = DEFAULT_WIDTH
) -> str | None:
    """Why `tgt`'s files for `year` cannot be deleted yet, or None if they can."""
    last = year_last_date(tgt, year)
    if last is None:
        return "not on disk (or empty)"
    first = dt.date(year, 1, 1)
    days = [first + dt.timedelta(days=n) for n in range((last - first).days + 1)]
    not_ingested = [d for d in days if d not in ingested]
    if not_ingested:
        return f"{len(not_ingested)} day(s) not ingested, first {not_ingested[0]}"
    missing = missing_frames(tgt, first, last, width)
    if missing:
        return f"{len(missing)} frame(s) not rendered, e.g. {missing[0]}"
    return None


def prune(
    client, tgt: ingest.Target, years: list[int], *, dry_run: bool = False,
    width: int = DEFAULT_WIDTH,
) -> tuple[int, int]:
    """Delete `tgt`'s year files that pass `check`. Returns (deleted, kept)."""
    ingested = status_mod.ingested_dates(client, tgt.status_table)
    deleted = kept = 0
    for year in years:
        if not any(config.land_path(n, year).exists() for n in tgt.variables):
            continue
        reason = check(tgt, year, ingested, width)
        if reason:
            log.warning("%s %d kept: %s", tgt.key, year, reason)
            kept += 1
            continue
        for name in tgt.variables:
            path = config.land_path(name, year)
            if dry_run:
                log.info("would delete %s", path.name)
            else:
                path.unlink(missing_ok=True)
                log.info("deleted %s", path.name)
        deleted += 1
    return deleted, kept
