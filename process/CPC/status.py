"""Per-date ingest state for the two land products.

**This is a binding, not a copy.** `CRW/status.py` is already table-parameterised
and knows nothing about CoralTemp beyond its default table name, so the land
products reuse it outright — `load`, `ingested_dates`, `last_ingested`, `record`
and `is_current` all come from there. Two tables, `land_temp_status` and
`land_precip_status`, for the same reason `mhw_status` is not a column on
`ingest_status`: the table is `ORDER BY date`, a product would have to join the
sorting key, and the two products genuinely progress independently.

**One thing means something different here, and the column names do not say so.**
`remote_size` / `remote_modified` describe the **year file** a date came out of,
not the date's own file — CPC ships one NetCDF per year. So every date in 2026
shares one pair of values, and that pair changes every day as the current year's
file is rewritten in place. For CoralTemp those columns answer "has this DATE
been revised"; here they answer "is this YEAR worth fetching again". Whether a
given date's values were revised inside an unchanged year file is not knowable
from them, which is what `--recheck-days` is for.

`filename` is the year file's name for the same reason, so a status row still
names the thing on disk it came from.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from CRW.status import (  # noqa: F401 — re-exported, deliberately not reimplemented
    COLUMNS,
    ingested_dates,
    is_current,
    last_ingested,
    load,
    record,
)

TEMP_TABLE = "land_temp_status"
PRECIP_TABLE = "land_precip_status"

TABLES = {"temp": TEMP_TABLE, "precip": PRECIP_TABLE}


@dataclass(frozen=True)
class LandDate:
    """One date, as `CRW.status.record` wants to be handed it.

    `record` needs `.date`, `.path` and `.filename`; a CoralTemp `NcFile` has all
    three because a date IS a file there. Here a date is one time index inside a
    year file, so this carries the date alongside the file it came out of rather
    than pretending the pair is one thing.
    """

    date: dt.date
    path: Path

    @property
    def filename(self) -> str:
        return self.path.name
