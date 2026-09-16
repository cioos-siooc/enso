"""Data invariants, as a command: `python -m CRW.cli check`.

Every check here guards a failure that has already happened in this project and
that **nothing reported at the time**. The ingest ran clean, `/coverage` said
the archive was complete, and the dashboard drew a believable map. Each one was
found by a human noticing a number that could not be true. This makes noticing
a command, so it can run after a `run` or before a deploy.

Exit status is the number of failed checks, capped at 1: 0 all good, 1 not.
Warnings print but do not fail.

**Cheap by default.** The only checks that read the daily tables are limited to
the last `--days` (default 45) dates, which partition pruning keeps to one or
two partitions. `--full` removes the limit and scans all of `mhw_daily`, which
is a full column read of ~24 B rows: a manual step, not something to schedule
on the production HDD.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from shared.ch import DATABASE, STATUS_SUCCESS
from shared.domain import regions

from . import status as status_mod

# A repaired 29 February has ~1,600 Cat 5 cells in the box (2024-02-29: 1,612);
# an unrepaired one has ~2,022,000, because land arrives as Cat 5. The threshold
# sits far from both, so neither a strong heatwave nor a partial repair lands
# on the wrong side of it.
LEAP_DAY_CAT5_MAX = 200_000

# A named region with no heatwave day at all over this many rolled-up days is
# a rollup built while `mhw_daily` was empty, not a region that never warmed.
MIN_DAYS_FOR_ZERO_EXTENT = 365

# The whole ingested box has never been heatwave-free on a single day since
# 1985 (its archive minimum is well above zero), so a zero there is a broken
# rollup, not a calm day.
BASIN_REGION = "pacific"


@dataclass
class Result:
    name: str
    level: str  # "ok" | "warn" | "fail" | "skip"
    detail: str


def _last_success(client, table: str) -> dt.date | None:
    last = client.query(
        f"SELECT max(date) FROM {DATABASE}.{table} FINAL WHERE status = %(s)s",
        parameters={"s": STATUS_SUCCESS},
    ).result_rows[0][0]
    return last if last and last > dt.date(1970, 1, 1) else None


def check_freshness(client, today: dt.date, stale_after: int) -> list[Result]:
    out = []
    for label, table in (("sst", status_mod.SST_TABLE), ("mhw", status_mod.MHW_TABLE)):
        last = _last_success(client, table)
        name = f"freshness.{label}"
        if last is None:
            out.append(Result(name, "fail", f"{table} records no successful ingest"))
            continue
        lag = (today - last).days
        level = "ok" if lag <= stale_after else "fail"
        out.append(Result(name, level, f"last ingested {last}, {lag} days ago (limit {stale_after})"))
    return out


def check_climatology(client) -> Result:
    keys = client.query(f"SELECT uniqExact(mmdd) FROM {DATABASE}.sst_clim").result_rows[0][0]
    level = "ok" if keys == 366 else "fail"
    return Result("climatology.keys", level, f"{keys} of 366 MMDD keys in sst_clim")


def check_mhw_table_matches_status(client) -> Result:
    """The status table saying "ingested" while the data table is empty.

    This is the state a `repartition` leaves `mhw_daily` in mid-flight, and it
    is the one `/coverage`'s `mhw.complete` cannot see, since that reads the
    status table.
    """
    days = client.query(
        f"SELECT uniqExact(date) FROM {DATABASE}.{status_mod.MHW_TABLE} FINAL WHERE status = %(s)s",
        parameters={"s": STATUS_SUCCESS},
    ).result_rows[0][0]
    rows = client.query(
        f"SELECT total_rows FROM system.tables WHERE database = %(d)s AND name = 'mhw_daily'",
        parameters={"d": DATABASE},
    ).result_rows
    n = int(rows[0][0] or 0) if rows else 0
    if days and not n:
        return Result(
            "mhw.table_vs_status", "fail",
            f"mhw_status records {days} ingested days but mhw_daily holds no rows "
            "(a repartition in flight?) — every heatwave query now reports category 0",
        )
    return Result("mhw.table_vs_status", "ok", f"{days} days ingested, {n:,} rows")


def check_mhw_categories(client, since: dt.date | None) -> Result:
    """No stored category outside 1..5: the 2024-07-01 re-encoding's 251 fill."""
    where = "WHERE (cat < 1 OR cat > 5)" + (" AND date >= %(since)s" if since else "")
    bad = client.query(
        f"SELECT count() FROM {DATABASE}.mhw_daily {where}",
        parameters={"since": since} if since else None,
    ).result_rows[0][0]
    scope = f"since {since}" if since else "whole archive"
    if bad:
        return Result("mhw.category_range", "fail", f"{bad:,} rows with cat outside 1..5 ({scope})")
    return Result("mhw.category_range", "ok", f"none outside 1..5 ({scope})")


def check_leap_days(client, since: dt.date | None, until: dt.date) -> Result:
    """Every 29 February ships with land at Cat 5; check the repair held."""
    first_year = since.year if since else 1985
    days = [
        dt.date(y, 2, 29) for y in range(first_year, until.year + 1)
        if calendar.isleap(y) and (since is None or dt.date(y, 2, 29) >= since)
        and dt.date(y, 2, 29) <= until
    ]
    if not days:
        return Result("mhw.leap_day_land", "skip", "no 29 February in range")
    rows = dict(client.query(
        f"SELECT date, countIf(cat = 5) FROM {DATABASE}.mhw_daily "
        "WHERE date IN %(days)s GROUP BY date",
        parameters={"days": days},
    ).result_rows)
    bad = {d: rows[d] for d in days if rows.get(d, 0) > LEAP_DAY_CAT5_MAX}
    if bad:
        listed = ", ".join(f"{d} ({n:,})" for d, n in sorted(bad.items()))
        return Result(
            "mhw.leap_day_land", "fail",
            f"Cat 5 counts that look like land: {listed} — run CRW.cli repair-mhw-land",
        )
    return Result("mhw.leap_day_land", "ok", f"{len(days)} leap day(s) under {LEAP_DAY_CAT5_MAX:,} Cat 5 cells")


def check_rollup_coverage(client) -> list[Result]:
    """Every named region rolled up through the last ingested SST date."""
    last = _last_success(client, status_mod.SST_TABLE)
    have = dict(client.query(
        f"SELECT region, max(date) FROM {DATABASE}.region_daily GROUP BY region"
    ).result_rows)
    out = []
    for key in sorted(regions()):
        name = f"rollup.coverage.{key}"
        reached = have.get(key)
        if reached is None:
            out.append(Result(name, "fail", "no rows in region_daily — run CRW.cli rollup --region " + key))
        elif last and reached < last:
            out.append(Result(name, "fail", f"rolled up through {reached}, ingested through {last}"))
        else:
            out.append(Result(name, "ok", f"through {reached}"))
    return out


def check_rollup_mhw(client, today: dt.date) -> list[Result]:
    """A region whose heatwave extent is zero on every day is a stale rollup.

    Rollup reads, so always over the whole history: ~9 regions x 15k rows.
    """
    rows = client.query(
        f"""
        SELECT region, count(), countIf(mhw_area_frac > 0)
        FROM {DATABASE}.region_daily FINAL
        GROUP BY region
        """
    ).result_rows
    out = []
    for region, n, positive in sorted(rows):
        name = f"rollup.mhw.{region}"
        if n >= MIN_DAYS_FOR_ZERO_EXTENT and positive == 0:
            out.append(Result(
                name, "fail",
                f"heatwave extent is 0 on all {n:,} days — rolled up while mhw_daily was "
                f"empty? Re-run: CRW.cli rollup --region {region} --fresh",
            ))
        else:
            out.append(Result(name, "ok", f"{positive:,} of {n:,} days with a heatwave"))

    window = client.query(
        f"""
        SELECT count(), countIf(mhw_area_frac = 0)
        FROM {DATABASE}.region_daily FINAL
        WHERE region = %(r)s AND date > %(since)s
        """,
        parameters={"r": BASIN_REGION, "since": today - dt.timedelta(days=30)},
    ).result_rows[0]
    if window[0] and window[1]:
        out.append(Result(
            f"rollup.mhw.{BASIN_REGION}.recent", "fail",
            f"{window[1]} of the last {window[0]} days report no heatwave anywhere in the basin",
        ))
    return out


def run_checks(client, *, days: int = 45, full: bool = False, stale_after: int = 3,
               today: dt.date | None = None) -> list[Result]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    last = _last_success(client, status_mod.SST_TABLE) or today
    since = None if full else last - dt.timedelta(days=days)

    results: list[Result] = []
    results += check_freshness(client, today, stale_after)
    results.append(check_climatology(client))
    table = check_mhw_table_matches_status(client)
    results.append(table)
    if table.level == "fail":
        results.append(Result("mhw.category_range", "skip", "mhw_daily is empty"))
        results.append(Result("mhw.leap_day_land", "skip", "mhw_daily is empty"))
    else:
        results.append(check_mhw_categories(client, since))
        results.append(check_leap_days(client, since, last))
    results += check_rollup_coverage(client)
    results += check_rollup_mhw(client, last)
    return results
