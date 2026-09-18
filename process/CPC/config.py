"""Paths and filename conventions for the NOAA CPC land archive.

The land counterpart of `CRW/config.py`, and the one structural difference from
it is visible in every signature here: **CPC ships one NetCDF per year**, so the
unit of a file is a `(variable, year)` pair, not a date. Filename parsing lives
here; everything that opens a file and applies the grid conventions is in
`shared/fields.py`, so `api` gets identical behaviour without importing this
package.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from shared.fields import (  # noqa: F401 — re-exported
    LAND_DIR,
    LAND_RE,
    LAND_VARIABLES,
    land_path,
)

__all__ = [
    "LAND_DIR",
    "LAND_VARIABLES",
    "ARCHIVE_START",
    "YearFile",
    "land_path",
    "parse_filename",
    "scan",
    "available_years",
    "archive_years",
]

# Where the land archive starts, and it is CoralTemp's start rather than CPC's.
#
# CPC itself reaches back to 1979, which would buy the 1982/83 super El Nino that
# the ocean layers cannot show. It is deliberately left on the table so
# `/coverage` reports ONE date range for the dashboard and every date on the map
# has both an ocean layer and a land one. Moving this back is a one-line change
# plus a backfill; it is the presentation that would need thinking about.
ARCHIVE_START = dt.date(1985, 1, 1)


@dataclass(frozen=True)
class YearFile:
    """One land variable's file for one year.

    The analogue of `CRW.config.NcFile`, keyed by year rather than date because
    that is the unit the source publishes. A date is addressed by its index
    inside one of these — see `CPC/ingest.py`.
    """

    path: Path
    variable: str
    year: int

    @property
    def filename(self) -> str:
        return self.path.name


def parse_filename(path: Path) -> YearFile | None:
    """Return a `YearFile` for a recognised land file, else None.

    `LAND_RE` does not match a `.part`, so an interrupted download can never be
    picked up as a complete archive member — the same guarantee `CRW.config`
    gives for the daily files.
    """
    match = LAND_RE.match(path.name)
    if match is None:
        return None
    return YearFile(path=path, variable=match["variable"], year=int(match["year"]))


def scan(variable: str | None = None, nc_dir: Path | None = None) -> list[YearFile]:
    """All recognised land year files on disk, sorted by (variable, year)."""
    nc_dir = nc_dir or LAND_DIR
    if not nc_dir.exists():
        return []
    files = [f for f in (parse_filename(p) for p in sorted(nc_dir.glob("*.nc"))) if f]
    if variable is not None:
        files = [f for f in files if f.variable == variable]
    return sorted(files, key=lambda f: (f.variable, f.year))


def available_years(variable: str, nc_dir: Path | None = None) -> set[int]:
    return {f.year for f in scan(variable, nc_dir)}


def archive_years(start: dt.date | None = None, end: dt.date | None = None) -> list[int]:
    """Every year the archive should cover, inclusive.

    Defaults to `ARCHIVE_START` through today. Today rather than yesterday
    because a year file is a year file however few days it currently holds — the
    reader reports the days that are actually in it.
    """
    start = start or ARCHIVE_START
    end = end or dt.date.today()
    return list(range(start.year, end.year + 1))
