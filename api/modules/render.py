"""Serving map imagery from the API: the cache, and nothing else.

**The API never renders.** Every frame, ocean and land, is produced by
`process` — `CRW.cli run`/`render` and `CPC.cli run`/`render` — and `/image`
serves what they wrote or 404s. There was an on-demand path here for buckets
whose NetCDF was still on disk; it is gone because the source files do not
stay: CoralTemp is pruned to its retention window, and the land year files are
deleted once ingested and rendered (`CPC.cli prune`). A fallback that works
only while a file happens to exist hides a missing frame until the day it
starts 404ing, and each miss cost ~1-9 s of an API thread besides.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from shared.periods import Period, span
from shared.render import (  # noqa: F401 — re-exported for SERVER.py
    DEFAULT_WIDTH,
    NO_CLIM_RGBA,
    bounds,
    cache_path,
    colormap_stops,
    land_bounds,
    quantity_stops,
)

__all__ = [
    "DEFAULT_WIDTH",
    "NO_CLIM_RGBA",
    "bounds",
    "cached_frame",
    "colormap_stops",
    "frame_settled",
    "land_bounds",
    "quantity_stops",
]

# How far back `process` may still rewrite a frame. CoralTemp is re-checked for
# in-place revisions over 30 days (`CRW.cli run --recheck-days`) and CPC over 14,
# so a bucket that ended before this is not written again by the daily runs and
# can be cached by a browser for long. Generous on purpose: a frame wrongly
# called settled is stale in someone's browser, one wrongly called recent costs
# a revalidation.
SETTLED_AFTER_DAYS = 45


def cached_frame(
    date: dt.date,
    width: int = DEFAULT_WIDTH,
    period: Period = "daily",
    variable_name: str = "sst",
) -> Path | None:
    """The cached WebP for one bucket, or None if `process` has not written it."""
    path = cache_path(date, width, period, variable_name)
    return path if path.is_file() else None


def frame_settled(date: dt.date, period: Period, today: dt.date | None = None) -> bool:
    """Whether the bucket containing `date` is past every re-render window."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    return span(date, period)[1] < today - dt.timedelta(days=SETTLED_AFTER_DAYS)
