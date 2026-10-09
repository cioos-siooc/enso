"""NOAA's official ENSO index, the Relative Oceanic Nino Index (RONI), as published.

The ribbon's own index (`state.enso_state`) is the Nino 3.4 anomaly against this
archive's fixed 1991-2020 normal. NOAA has rated ENSO with RONI since February
2025: the Nino 3.4 anomaly minus the tropical-mean (20S-20N) anomaly, rescaled,
so warming the whole tropics shares is taken out. In a year when the whole ocean
is warm the two differ by most of a degree (JAS 2026: +2.65 here, +1.69 RONI),
so the dashboard shows NOAA's number beside its own rather than leaving the
visitor to wonder which one the news is quoting.

**It is read, not computed.** A RONI-style number worked out here from CoralTemp
would be a third index under NOAA's name. The file is CPC's own, ~15 KB, one row
per overlapping three-month season since DJF 1950, from ERSSTv6. CPC updates it
by the 5th of each month and says the newest values may move for up to two
months, so the latest season is an estimate.

Fetched on demand and held per worker for `TTL`. A failed fetch keeps serving the
last good copy; with none, callers get None for `RETRY` before the next attempt,
so a NOAA outage costs one short timeout per worker rather than one per request.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
import urllib.request

log = logging.getLogger(__name__)

URL = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"
SOURCE = "NOAA Climate Prediction Center"
PAGE = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"

TTL = 6 * 3600
RETRY = 600
TIMEOUT = 5

# Indexed by the season's middle month minus one, as in `state._SEASONS`. CPC
# labels a season with its middle month's year: DJF 1950 is Dec 1949-Feb 1950.
_SEASONS = (
    "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ",
    "JJA", "JAS", "ASO", "SON", "OND", "NDJ",
)

_lock = threading.Lock()
_cache: list[dict] | None = None
_fetched = 0.0
_failed = 0.0


def _parse(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[0] not in _SEASONS:
            continue
        season, year, value = parts[0], int(parts[1]), float(parts[2])
        middle = dt.date(year, _SEASONS.index(season) + 1, 1)
        rows.append({"season": f"{season} {year}", "middle": str(middle), "value": value})
    if not rows:
        raise ValueError("no seasons in the RONI file")
    return rows


def seasons() -> list[dict] | None:
    """Every published season, oldest first, each dated by its middle month."""
    global _cache, _fetched, _failed
    now = time.monotonic()
    with _lock:
        if _cache is not None and now - _fetched < TTL:
            return _cache
        if now - _failed < RETRY:
            return _cache
        try:
            # CPC refuses urllib's default User-Agent.
            req = urllib.request.Request(URL, headers={"User-Agent": "OSTA (osta.cioospacific.ca)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                _cache = _parse(resp.read().decode("ascii", "replace"))
            _fetched = now
        except Exception as exc:  # noqa: BLE001 - any failure keeps the last copy
            log.warning("RONI fetch failed, %s: %s", "serving the last copy" if _cache else "none held", exc)
            _failed = now
        return _cache


def latest() -> dict | None:
    """The newest season, for the ribbon."""
    rows = seasons()
    if not rows:
        return None
    return {**rows[-1], "source": SOURCE, "url": PAGE}
