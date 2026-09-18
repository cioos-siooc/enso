"""NetCDF -> ClickHouse ingest for the two land products.

The shape is `CRW/ingest.py`'s — a `Target` per product, one `ingest_year`
routine both share, per-date status bookkeeping — with one structural difference
that comes straight from the source: **CPC ships one NetCDF per year**, so the
loop walks time indices inside a file rather than files. The file is opened once
per year by `shared.fields.read_land_year` and the days are sliced out of the
resulting stack; opening it per date would be ~365 opens of the same 80 MB HDF5
file to read a 250x380 slice out of each.

The grid conventions — CPC is north-up and already 0-360, so it is flipped and
NOT rolled — are applied by `shared/fields.py`, not here, and verified there
against the file's own coordinate variables.

**Temperature takes two files at once.** `tmax` and `tmin` are separate downloads
and one table, so a year is ingested only when both are on disk, and only cells
valid in both are stored. Measured, the two masks are byte-identical, so this
should never drop anything — which is exactly why a day where they diverge is
logged rather than passed over in silence.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shared.ch import DATABASE, STATUS_FAILED, STATUS_SUCCESS
from shared.domain import land_grid, subset
from shared.fields import (
    land_path,
    land_valid_mask,
    read_land_year,
    to_precip_counts,
    to_temp_counts,
)

from . import status as status_mod

log = logging.getLogger(__name__)

TEMP_COLUMNS = ["date", "gy", "gx", "tmax_raw", "tmin_raw"]
PRECIP_COLUMNS = ["date", "gy", "gx", "precip_raw"]


def _box_origin() -> tuple[int, int]:
    """`(gy0, gx0)` of the box on the LAND grid — 60, 200 as configured."""
    grid = land_grid()
    return subset().gy_range(grid)[0], subset().gx_range(grid)[0]


def read_temp_day(stacks: dict[str, np.ndarray], i: int) -> tuple[np.ndarray, ...]:
    """`(gy, gx, tmax_raw, tmin_raw)` for one time index of a temperature year.

    Only cells with BOTH readings are returned. A cell with a maximum and no
    minimum has no `tmean`, and storing it with a sentinel minimum would put a
    fabricated number behind an ALIAS that looks computed.
    """
    gy0, gx0 = _box_origin()
    tmax, tmin = stacks["tmax"][i], stacks["tmin"][i]

    vmax, vmin = land_valid_mask(tmax), land_valid_mask(tmin)
    both = vmax & vmin
    divergent = int((vmax ^ vmin).sum())
    if divergent:
        # Measured across 2026, this is 0 everywhere. If it ever fires, the
        # assumption that the two variables share a mask has changed and the
        # table's meaning has quietly narrowed with it.
        log.warning(
            "time index %d: %d cells have one of tmax/tmin but not the other; "
            "storing only the %d with both",
            i, divergent, int(both.sum()),
        )

    iy, ix = np.nonzero(both)
    return (
        (iy + gy0).astype("uint16"),
        (ix + gx0).astype("uint16"),
        to_temp_counts(tmax[iy, ix]),
        to_temp_counts(tmin[iy, ix]),
    )


def read_precip_day(stacks: dict[str, np.ndarray], i: int) -> tuple[np.ndarray, ...]:
    """`(gy, gx, precip_raw)` for one time index of a precipitation year.

    **Every valid cell, wet or dry.** A stored 0 is a real reading — it did not
    rain — and dropping the dry cells would make a missing row mean either "dry"
    or "outside the gauge analysis", which nothing downstream could tell apart.
    """
    gy0, gx0 = _box_origin()
    precip = stacks["precip"][i]
    iy, ix = np.nonzero(land_valid_mask(precip))
    return (
        (iy + gy0).astype("uint16"),
        (ix + gx0).astype("uint16"),
        to_precip_counts(precip[iy, ix]),
    )


@dataclass(frozen=True)
class Target:
    """A land product's ingest destination: what to read, where to put it.

    `variables` is a list because temperature is two files and one table. The
    reader is handed every variable's stack for the year, keyed by name, so it
    can require them jointly.
    """

    key: str
    variables: tuple[str, ...]
    table: str
    columns: list[str]
    reader: object  # (stacks, i) -> per-cell arrays, one per column but date
    status_table: str


TEMP_TARGET = Target(
    "temp", ("tmax", "tmin"), "land_temp_daily", TEMP_COLUMNS,
    read_temp_day, status_mod.TEMP_TABLE,
)
PRECIP_TARGET = Target(
    "precip", ("precip",), "land_precip_daily", PRECIP_COLUMNS,
    read_precip_day, status_mod.PRECIP_TABLE,
)

TARGETS = {t.key: t for t in (TEMP_TARGET, PRECIP_TARGET)}


def target(key: str) -> Target:
    try:
        return TARGETS[key]
    except KeyError:
        raise KeyError(f"unknown land target {key!r}; known: {sorted(TARGETS)}") from None


def delete_day(client, date: dt.date, table: str) -> None:
    """Remove an already-ingested date so it can be replaced.

    Both land tables are plain MergeTrees, so this is a mutation. It is far
    cheaper here than on the ocean side — a land day is ~21 k rows against SST's
    7.5 M — but it is still a part rewrite, which is why the ingest skips a date
    it already holds unless told otherwise.
    """
    client.command(
        f"ALTER TABLE {DATABASE}.{table} DELETE WHERE date = %(date)s",
        parameters={"date": date},
        settings={"mutations_sync": 2},
    )


def ingest_year(
    client,
    year: int,
    *,
    tgt: Target,
    nc_dir: Path | None = None,
    force: bool = False,
    force_dates: set[dt.date] | None = None,
    only_dates: set[dt.date] | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
    source_url: str = "",
    remote: tuple[int, str] | None = None,
) -> dict[str, int]:
    """Ingest one year of one product, skipping dates already loaded.

    **One insert per year, not per batch of days.** A land day is ~21 k rows, so
    a whole year is ~7.6 M — about the size of a single CoralTemp day, which the
    ocean side inserts five at a time. Batching finer would only create parts.

    `only_dates` restricts the ingest to a set of dates; `start`/`end` clip the
    year to a range. Both are applied on top of the skip-what-is-loaded rule.

    `force_dates` is the opposite: dates re-ingested even though status already
    has them. That is what `run`'s recheck window is — CPC revises its recent end
    as more stations report, and it does so INSIDE a year file, where no per-date
    size or mtime could reveal it. Passing a set rather than re-running with
    `force=True` keeps it to one delete-and-insert per date instead of two.
    """
    force_dates = force_dates or set()
    stacks: dict[str, np.ndarray] = {}
    dates: list[dt.date] | None = None
    for name in tgt.variables:
        d, stack = read_land_year(name, year, nc_dir)
        if dates is not None and d != dates:
            raise ValueError(
                f"{name}.{year}.nc covers {len(d)} days, "
                f"{tgt.variables[0]}.{year}.nc covers {len(dates)} — the two "
                "temperature files must agree before either is ingested"
            )
        dates, stacks[name] = d, stack

    existing = status_mod.load(client, tgt.status_table)
    counts = {"ingested": 0, "skipped": 0, "failed": 0, "rows": 0}

    buffers: list[list] = [[] for _ in tgt.columns]
    pending: list[tuple[dt.date, int]] = []
    # The file a status row names. For temperature that is `tmax.YYYY.nc`, the
    # first of the two — `file_size` and `filename` describe one file and there
    # are two, so it names the one the table is keyed on rather than inventing a
    # combined name that matches nothing on disk.
    year_file = land_path(tgt.variables[0], year, nc_dir)

    for i, date in enumerate(dates or []):
        if start and date < start:
            continue
        if end and date > end:
            continue
        if only_dates is not None and date not in only_dates:
            continue

        row = existing.get(date)
        if status_mod.is_current(row) and not force and date not in force_dates:
            counts["skipped"] += 1
            continue

        try:
            columns = tgt.reader(stacks, i)
        except Exception as exc:  # noqa: BLE001 — one bad day must not stop the year
            log.exception("failed to read %s from %s", date, year_file.name)
            status_mod.record(
                client, status_mod.LandDate(date, year_file), STATUS_FAILED,
                message=str(exc)[:500], table=tgt.status_table,
            )
            counts["failed"] += 1
            continue

        # A date previously loaded must be cleared first: plain MergeTrees would
        # otherwise end up holding both versions.
        if row is not None and row["status"] == STATUS_SUCCESS:
            log.info("replacing already-ingested %s in %s", date, tgt.table)
            delete_day(client, date, tgt.table)

        n = int(columns[0].size)
        buffers[0].extend([date] * n)
        for j, values in enumerate(columns, start=1):
            buffers[j].extend(values.tolist())
        pending.append((date, n))

    if not pending:
        return counts

    log.info("inserting %d day(s) of %s for %d", len(pending), tgt.table, year)
    try:
        client.insert(
            f"{DATABASE}.{tgt.table}", buffers,
            column_names=tgt.columns, column_oriented=True,
        )
    except Exception as exc:  # noqa: BLE001 — recorded per-day below
        log.exception("insert failed for %d day(s) of %d", len(pending), year)
        for date, _ in pending:
            status_mod.record(
                client, status_mod.LandDate(date, year_file), STATUS_FAILED,
                message=str(exc)[:500], table=tgt.status_table,
            )
            counts["failed"] += 1
        return counts

    size, modified = remote or (0, "")
    for date, n_rows in pending:
        status_mod.record(
            client, status_mod.LandDate(date, year_file), STATUS_SUCCESS,
            n_rows=n_rows, source_url=source_url, remote_size=size,
            remote_modified=modified, table=tgt.status_table,
        )
        counts["ingested"] += 1
        counts["rows"] += n_rows
    return counts
