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
import logging
from pathlib import Path

from shared.periods import Period
from shared.render import (  # noqa: F401 — re-exported for call sites
    DEFAULT_WIDTH,
    IMAGE_DIR,
    MERCATOR_LAT_LIMIT,
    NO_CLIM_RGBA,
    bounds,
    cache_path,
    colorize,
    colormap_stops,
    encode,
    land_bounds,
    quantity_stops,
    to_mercator,
    write_cache,
)

log = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_WIDTH",
    "IMAGE_DIR",
    "MERCATOR_LAT_LIMIT",
    "NO_CLIM_RGBA",
    "bounds",
    "cache_path",
    "colorize",
    "colormap_stops",
    "encode",
    "land_bounds",
    "quantity_stops",
    "render",
    "to_mercator",
]


def render(
    date: dt.date,
    width: int = DEFAULT_WIDTH,
    period: Period = "daily",
    variable_name: str = "sst",
) -> bytes | None:
    """The cached WebP for one bucket, or None if `process` has not written it."""
    path: Path = cache_path(date, width, period, variable_name)
    return path.read_bytes() if path.is_file() else None
