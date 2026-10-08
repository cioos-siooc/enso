"""The date-ordered `*_recent` tables: when the rollup may read them, and filling them.

`sst_recent` and `mhw_recent` (`shared/ch.py`) hold the archive tables' last
`RECENT_DAYS` ordered `(date, gy, gx)`, so the one-date rollup `run` does after
every ingest reads that date's rows and nothing else. On the archive tables the
same rollup reads the whole current-year partition per region.

**They are a cache, and the rollup only reads them when it can prove they are
complete** (`covers`). A materialized view fills them on insert, so a date
ingested before they existed is missing, and a date whose rows were deleted on
one side only would be wrong. So for every date in the range, each table's row
count is checked against the `n_rows` its status table recorded for the date's
last successful ingest; one mismatch and the rollup reads the archive tables
instead, exactly as it did before these existed. A `count()` over one date of a
date-ordered table is cheap, and the status tables are ~15k rows.

`fill` is the one-off after a deploy (`CRW.cli recent`): it copies whatever
dates of the window the views have not seen yet. It reads the archive tables'
partitions the window falls in once, which is the cost the views avoid on
every later run.
"""

from __future__ import annotations

import datetime as dt
import logging

from shared.ch import DATABASE, RECENT_DAYS, STATUS_SUCCESS

from . import status as status_mod

log = logging.getLogger(__name__)

# archive table -> (recent table, its status table, the columns it copies)
TABLES = {
    "sst_daily": ("sst_recent", status_mod.SST_TABLE, "date, gy, gx, sst_raw, has_clim"),
    "mhw_daily": ("mhw_recent", status_mod.MHW_TABLE, "date, gy, gx, cat"),
}

# Days kept clear of the TTL edge: a date about to expire may already be gone
# from a merged part, and the rollup should not have to find that out.
_MARGIN_DAYS = 7


def recent_of(table: str) -> str | None:
    """The `*_recent` twin of an archive table, or None if it has none."""
    entry = TABLES.get(table)
    return entry[0] if entry else None


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def in_window(start: dt.date | None, end: dt.date | None, today: dt.date | None = None) -> bool:
    """Whether `start..end` lies inside what the recent tables keep."""
    if start is None or end is None:
        return False
    floor = (today or _today()) - dt.timedelta(days=RECENT_DAYS - _MARGIN_DAYS)
    return floor <= start <= end


def _mismatched(client, recent: str, status_table: str, start: dt.date, end: dt.date) -> list[dt.date]:
    """Dates in range whose recent row count differs from what status recorded."""
    params = {"start": start, "end": end, "ok": STATUS_SUCCESS}
    expected = dict(client.query(
        f"SELECT date, n_rows FROM {DATABASE}.{status_table} FINAL "
        "WHERE status = %(ok)s AND date BETWEEN %(start)s AND %(end)s",
        parameters=params,
    ).result_rows)
    got = dict(client.query(
        f"SELECT date, count() FROM {DATABASE}.{recent} "
        "WHERE date BETWEEN %(start)s AND %(end)s GROUP BY date",
        parameters=params,
    ).result_rows)
    dates = sorted(set(expected) | set(got))
    return [d for d in dates if int(got.get(d, 0)) != int(expected.get(d, 0))]


def covers(client, start: dt.date | None, end: dt.date | None) -> bool:
    """Whether both recent tables hold exactly the archive's rows for `start..end`."""
    if not in_window(start, end):
        return False
    for recent, status_table, _ in TABLES.values():
        bad = _mismatched(client, recent, status_table, start, end)
        if bad:
            log.info("%s does not match %s on %d date(s), first %s; rolling up from the archive",
                     recent, status_table, len(bad), bad[0])
            return False
    return True


def delete_day(client, table: str, date: dt.date) -> None:
    """Clear a date from an archive table's recent twin, if it has one.

    A lightweight delete, applied synchronously: the table is small and
    date-ordered, and the rollup that follows a re-ingest must not see both
    copies.
    """
    recent = recent_of(table)
    if recent is None:
        return
    client.command(
        f"DELETE FROM {DATABASE}.{recent} WHERE date = %(date)s",
        parameters={"date": date},
    )


def fill(client, today: dt.date | None = None) -> dict[str, int]:
    """Copy into each recent table the dates of the window it does not match on.

    Returns the number of dates copied per table. Safe to re-run: a date is
    cleared before it is copied, and one that already matches is left alone.
    """
    today = today or _today()
    start = today - dt.timedelta(days=RECENT_DAYS - _MARGIN_DAYS)
    copied: dict[str, int] = {}
    for archive, (recent, status_table, columns) in TABLES.items():
        dates = _mismatched(client, recent, status_table, start, today)
        copied[recent] = len(dates)
        if not dates:
            log.info("%s: all dates from %s match", recent, start)
            continue
        log.info("%s: copying %d date(s) from %s, %s .. %s", recent, len(dates), archive,
                 dates[0], dates[-1])
        client.command(
            f"DELETE FROM {DATABASE}.{recent} WHERE date IN %(dates)s",
            parameters={"dates": dates},
        )
        client.command(
            f"INSERT INTO {DATABASE}.{recent} ({columns}) "
            f"SELECT {columns} FROM {DATABASE}.{archive} WHERE date IN %(dates)s",
            parameters={"dates": dates},
        )
    return copied
