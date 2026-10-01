"""NetCDF -> ClickHouse ingest for the two daily archives.

CoralTemp SST is the primary one and is described below. The NOAA CRW Marine
Heatwave category rides the same machinery through `MHW_TARGET`: a different
file, a different table, and one difference of substance — **only cells actually
in a heatwave are stored**, so `mhw_daily` is ~24.2 B rows against `sst_daily`'s
~113.7 B. See `read_mhw_day` and `shared/ch.py`.


Each file holds one day of `analysed_sst` on the global 0.05-degree grid,
encoded as `short` counts of 0.01 degC with `_FillValue = -32768` over land.
Those raw counts go into ClickHouse untouched (see `shared/ch.py` for why),
subset to the Pacific box and keyed by their index into the *global* grid, so
widening the box later needs no reindex.

Grid conventions — the longitude roll and the latitude orientation — are applied
by `shared/fields.py`, not here.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

import numpy as np
from shared.ch import DATABASE, STATUS_FAILED, STATUS_INGESTING, STATUS_SUCCESS
from shared.domain import global_grid, subset
from shared.fields import (
    mhw_valid_mask,
    mmdd_of,
    no_clim_mask,
    read_clim_raw,
    read_daily_raw,
    read_mhw_raw,
    valid_mask,
)

from . import status as status_mod
from .config import NcFile

log = logging.getLogger(__name__)

COLUMNS = ["date", "gy", "gx", "sst_raw", "has_clim"]
MHW_COLUMNS = ["date", "gy", "gx", "cat"]


def read_day(nc: NcFile) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return `(gy, gx, sst_raw, has_clim)` for the box's ocean cells.

    `has_clim` is resolved here, at ingest, by reading the day's climatology
    file — it is per (cell, date) because the ice edge moves through the year,
    so it cannot be derived later from the cell alone. It is what keeps
    `mean(sst) - mean(clim)` exact over a box.
    """
    grid, box = global_grid(), subset()
    gy0, _ = box.gy_range(grid)
    gx0, _ = box.gx_range(grid)

    raw = read_daily_raw(nc.date)
    clim = read_clim_raw(mmdd_of(nc.date))

    ocean = valid_mask(raw)
    missing_clim = no_clim_mask(raw, clim)

    iy, ix = np.nonzero(ocean)
    return (
        (iy + gy0).astype("uint16"),
        (ix + gx0).astype("uint16"),
        raw[iy, ix].astype("int16"),
        (~missing_clim[iy, ix]).astype("uint8"),
    )


def read_mhw_day(nc: NcFile) -> tuple[np.ndarray, ...]:
    """Return `(gy, gx, cat)` for the box's cells that are in a heatwave.

    **Only category >= 1 is returned.** Land (-127), ice (-1) and heatwave-free
    ocean (0) are dropped, which is what takes the table from ~113.7 B rows to
    ~24.2 B. The zeros come back at query time from a LEFT JOIN against
    `sst_daily`, which is the authority on which cells are ocean on a given day —
    see `shared/ch.py`.

    Reads its own file; there is no climatology to consult and nothing to derive.
    """
    grid, box = global_grid(), subset()
    gy0, _ = box.gy_range(grid)
    gx0, _ = box.gx_range(grid)

    raw = read_mhw_raw(nc.date)
    iy, ix = np.nonzero(mhw_valid_mask(raw))
    return (
        (iy + gy0).astype("uint16"),
        (ix + gx0).astype("uint16"),
        raw[iy, ix].astype("uint8"),
    )


@dataclass(frozen=True)
class Target:
    """An archive's ingest destination: what to read, where to put it.

    The two products share `ingest_files` because the batching, the
    replace-before-reinsert dance and the per-day status bookkeeping are
    identical. Only the reader, the table and the columns differ.
    """

    table: str
    columns: list[str]
    reader: object  # NcFile -> tuple of per-cell arrays, one per column but date
    status_table: str


SST_TARGET = Target("sst_daily", COLUMNS, read_day, status_mod.SST_TABLE)
MHW_TARGET = Target("mhw_daily", MHW_COLUMNS, read_mhw_day, status_mod.MHW_TABLE)


def delete_day(
    client, date: dt.date, table: str = "sst_daily", *, lightweight: bool = False
) -> None:
    """Remove an already-ingested day so it can be replaced.

    Both daily tables are plain MergeTrees, so by default this is a mutation
    that rewrites the affected parts of the day's partition. Expensive, and
    deliberately so: it only runs when the source revises a date in place,
    which is rare and confined to the recent, per-year end of the archive.

    `lightweight` is for clearing what a crashed insert left behind, which can
    happen anywhere in a backfill. There the mutation would rewrite merged parts
    of a decade partition — tens of GiB for one day — and it ran past the
    client's timeout while stalling every concurrent insert. Instead it issues a
    lightweight DELETE and does NOT wait for it: during a bulk ingest the parts
    it must touch are nearly always being merged, and a synchronous one sat
    unapplied for over 30 minutes. Not waiting is safe because a mutation only
    applies to parts that existed when it was created, so the day's rows
    reinserted straight afterwards are untouched. Until it applies, a read of
    that day sees both copies; the merges (or the `OPTIMIZE ... FINAL` a
    backfill ends with) settle it. A day with no rows — a file that failed to
    read — issues nothing.
    """
    if lightweight:
        present = client.query(
            f"SELECT count() FROM {DATABASE}.{table} WHERE date = %(date)s",
            parameters={"date": date},
        ).result_rows[0][0]
        if present:
            client.command(
                f"DELETE FROM {DATABASE}.{table} WHERE date = %(date)s",
                parameters={"date": date},
                settings={"lightweight_deletes_sync": 0},
            )
        return
    client.command(
        f"ALTER TABLE {DATABASE}.{table} DELETE WHERE date = %(date)s",
        parameters={"date": date},
        settings={"mutations_sync": 2},
    )


# The RowBinary layout of every column either daily table carries. `date` is a
# ClickHouse Date, which on the wire is a UInt16 count of days since 1970-01-01.
ROW_BINARY = {
    "date": "<u2", "gy": "<u2", "gx": "<u2",
    "sst_raw": "<i2", "has_clim": "u1", "cat": "u1",
}
_EPOCH = dt.date(1970, 1, 1)

# Blocks of ~a day rather than ClickHouse's default ~1 M rows, so a 5-day batch
# lands as ~6 parts instead of ~86. Not one block per insert: an 86 M-row block
# made the server throw `std::length_error` in `splitBlockIntoParts` on about
# 1 insert in 175 (ClickHouse 26.5, 8 concurrent writers).
_INSERT_BLOCKS = {
    "max_insert_block_size": 1 << 24,
    "min_insert_block_size_rows": 0,
    "min_insert_block_size_bytes": 0,
}


def _row_binary(dtype: np.dtype, files: list[NcFile], days: list[tuple]) -> bytes:
    """Pack a batch into RowBinary: a numpy record array, straight to bytes.

    This replaces `client.insert()` with Python lists, which cost ~11 GB of
    objects per 5-day global batch and, worse, serialises the Date column
    through `struct.pack(*column)` — one Python argument per row. At 86 M rows
    that segfaulted Python 3.13 intermittently (clickhouse-connect 1.8.0,
    `driver/common.py:write_array`), leaving part of the batch inserted.
    """
    total = sum(int(cols[0].size) for cols in days)
    out = np.empty(total, dtype=dtype)
    names = dtype.names
    at = 0
    for nc, cols in zip(files, days):
        n = int(cols[0].size)
        out["date"][at : at + n] = (nc.date - _EPOCH).days
        for name, values in zip(names[1:], cols):
            out[name][at : at + n] = values
        at += n
    return out.tobytes()


def ingest_files(
    client,
    files: list[NcFile],
    *,
    force: bool = False,
    batch_days: int = 5,
    on_committed=None,
    source_url: str = "",
    target: Target = SST_TARGET,
) -> dict[str, int]:
    """Ingest a list of files, skipping days already loaded.

    `batch_days` defaults to 5, not the OISST-era 30: an SST day is now ~7.5M
    rows rather than ~96k, so 30 days is a 225M-row insert and a needless memory
    spike. Batching at all still matters — a per-file insert over the full
    archive would create ~15k parts. An MHW day is ~1.6M rows, so the same batch
    size is comfortably smaller there.

    `on_committed(nc)` fires per file once its batch has actually landed, which
    is how `backfill --delete-nc` reclaims disk safely.
    """
    existing = status_mod.load(client, target.status_table)
    counts = {"ingested": 0, "skipped": 0, "failed": 0, "rows": 0}

    pending: list[NcFile] = []
    rows_per_day: list[int] = []
    days: list[tuple] = []  # per pending day, its per-column arrays
    dtype = np.dtype([(c, ROW_BINARY[c]) for c in target.columns])

    def flush() -> None:
        if not pending:
            return
        # Marked before the insert, because a large insert lands as several
        # parts and is not atomic: a crash part-way leaves rows with no success
        # status, and the next run would insert them a second time. A day left
        # at `ingesting` is cleared by the replace path below before reinsert.
        for nc in pending:
            status_mod.record(client, nc, STATUS_INGESTING, table=target.status_table)
        try:
            client.raw_insert(
                f"{DATABASE}.{target.table}",
                target.columns,
                insert_block=_row_binary(dtype, pending, days),
                settings=_INSERT_BLOCKS,
                fmt="RowBinary",
            )
        except Exception as exc:  # noqa: BLE001 — recorded per-day below
            log.exception("insert failed for %d day(s)", len(pending))
            for nc in pending:
                status_mod.record(
                    client, nc, STATUS_FAILED, message=str(exc)[:500],
                    table=target.status_table,
                )
                counts["failed"] += 1
        else:
            for nc, n_rows in zip(pending, rows_per_day):
                status_mod.record(
                    client, nc, STATUS_SUCCESS, n_rows=n_rows, source_url=source_url,
                    table=target.status_table,
                )
                counts["ingested"] += 1
                counts["rows"] += n_rows
                if on_committed is not None:
                    on_committed(nc)
        finally:
            pending.clear()
            rows_per_day.clear()
            days.clear()

    for nc in files:
        row = existing.get(nc.date)
        if not force and status_mod.is_current(row):
            counts["skipped"] += 1
            continue

        try:
            columns = target.reader(nc)
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop the run
            log.exception("failed to read %s", nc.filename)
            status_mod.record(
                client, nc, STATUS_FAILED, message=str(exc)[:500],
                table=target.status_table,
            )
            counts["failed"] += 1
            continue

        # A day previously loaded must be cleared first: the daily tables are
        # plain MergeTrees and would otherwise end up holding both versions.
        # `ingesting` and `failed` may have left part of an insert behind, so
        # they are cleared too, with a lightweight delete (see `delete_day`).
        if row is not None and row["status"] in (STATUS_SUCCESS, STATUS_INGESTING, STATUS_FAILED):
            flush()
            crashed = row["status"] != STATUS_SUCCESS
            log.info("%s %s in %s", "clearing interrupted" if crashed else "replacing already-ingested",
                     nc.date, target.table)
            delete_day(client, nc.date, target.table, lightweight=crashed)

        n = int(columns[0].size)
        days.append(columns)
        pending.append(nc)
        rows_per_day.append(n)

        if len(pending) >= batch_days:
            log.info("inserting %d day(s) up to %s", len(pending), nc.date)
            flush()

    flush()
    return counts
