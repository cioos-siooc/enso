"""How far behind the archive is, for `/health` and `/health/data`.

Read from the two status tables rather than the daily tables: they hold one
row per date, so `max(date)` is instant, and "ingested" is what a date being
there means only once its status says so.

**Kept apart from liveness on purpose.** `/health` is the container healthcheck,
and `front` waits on `api` being healthy, so a late NOAA file must never turn it
red — that would take the site down over a data delay the site can still serve
around. `/health/data` is the one that goes 503, for an external monitor to
page on.
"""

from __future__ import annotations

import datetime as dt
import os

from modules.clickhouse_helpers import DATABASE, client

# CoralTemp publishes at about a day's latency, so a lag of 1 is normal and 2 is
# a run that has not happened yet today. 3 days behind is something to look at.
STALE_AFTER_DAYS = int(os.environ.get("STALE_AFTER_DAYS", "3"))

_ARCHIVES = {"sst": "ingest_status", "mhw": "mhw_status"}


def data_freshness(today: dt.date | None = None) -> dict:
    """Last ingested date and lag in days, per archive, plus the verdict."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    archives: dict[str, dict] = {}
    for name, table in _ARCHIVES.items():
        last = client().query(
            f"SELECT max(date) FROM {DATABASE}.{table} FINAL WHERE status = 'success_ingest'"
        ).result_rows[0][0]
        # An empty table comes back as the epoch rather than NULL.
        if not last or last <= dt.date(1970, 1, 1):
            archives[name] = {"last": None, "lagDays": None}
        else:
            archives[name] = {"last": last.isoformat(), "lagDays": (today - last).days}
    lags = [a["lagDays"] for a in archives.values()]
    stale = any(lag is None or lag > STALE_AFTER_DAYS for lag in lags)
    return {"staleAfterDays": STALE_AFTER_DAYS, "stale": stale, **archives}
