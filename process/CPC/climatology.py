"""The land climatology: 1991-2020, per calendar day, smoothed, built here.

**Built from the year files, never from ClickHouse**, the way the frames are.
It needs 1991-2020 on disk, so it is built before `CPC.cli prune`; rebuilding it
later means fetching those years again (~6.5 GB).

One NetCDF per source (`tmax`, `tmin`, `precip`) in `LAND_CLIM_DIR`, shaped
`(mmdd, lat, lon)` over the whole CPC grid, south-up, float32. The 366 keys include 0229,
the same key set `sst_clim` uses, so `fields.mmdd_of()` indexes both.

### The window, and why sums and counts are windowed separately

Each layer's `baseline` in `domain.yml` declares a `window_days` — 15 for
temperature, 7 for rainfall — and the normal for calendar day k is the mean over
every baseline-year day within +/-(window-1)/2 keys of k. Computed as

    normal[k] = sum over window of SUM[j]  /  sum over window of COUNT[j]

rather than as a moving average of the per-day means, which makes it a true
**sample-weighted** mean: 0229 exists in 8 of the 30 years, and averaging it as
if it were an equal day would give its 8 samples the weight of 30. The window is
**circular** over the 366 keys, so 31 December's window reaches into January.

### What it refuses

- **A missing baseline year raises.** A normal over 29 years is a different
  baseline under the same label, and nothing downstream could tell.
- **The file records its period and window**, and `fields.read_land_clim` raises
  when they disagree with `domain.yml` — so editing a window without rebuilding
  fails loudly rather than serving the old normal under the new name.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import netCDF4
import numpy as np
from shared.domain import land_grid, land_shape, variables
from shared.fields import (
    LAND_CLIM_DIR,
    MMDD_KEYS,
    land_clim_path,
    land_path,
    land_valid_mask,
    mmdd_of,
    read_land_year,
)

log = logging.getLogger(__name__)

_INDEX = {k: i for i, k in enumerate(MMDD_KEYS)}


def declared_baseline(source: str) -> tuple[str, int]:
    """`(period, window_days)` the anomaly layer built on `source` declares.

    The climatology is per SOURCE and the declaration is per LAYER, so this is
    where the two meet. Exactly one anomaly layer reads each source today; two
    that disagreed would need two files, and raising says so rather than letting
    whichever came first win.
    """
    found = {
        (v.baseline.period, v.baseline.window_days)
        for v in variables().values()
        if v.grid == "land" and v.source == source and v.baseline is not None
    }
    if not found:
        raise ValueError(f"no land layer declares a baseline for source {source!r}")
    if len(found) > 1:
        raise ValueError(
            f"land layers on {source!r} declare different baselines {sorted(found)}; "
            "one climatology file cannot serve both"
        )
    return found.pop()


def baseline_years(period: str) -> list[int]:
    """`'1991-2020'` -> [1991, ..., 2020]."""
    start, end = (int(y) for y in period.split("-"))
    return list(range(start, end + 1))


def accumulate(
    source: str, years: list[int], nc_dir: Path | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Per-MMDD `(sums, counts)` over `years`, each `(366, 360, 720)`.

    Raises if any year's file is absent — see the module docstring. Only valid
    readings are counted; a cell outside the gauge analysis on some day simply
    contributes nothing to that day.
    """
    missing = [y for y in years if not land_path(source, y, nc_dir).exists()]
    if missing:
        raise FileNotFoundError(
            f"cannot build a {years[0]}-{years[-1]} {source} climatology: "
            f"{len(missing)} year file(s) missing ({missing[:5]}"
            f"{'...' if len(missing) > 5 else ''}). Fetch them with `CPC.cli fetch`."
        )

    shape = (len(MMDD_KEYS), *land_shape())
    sums = np.zeros(shape, dtype="float64")
    counts = np.zeros(shape, dtype="int32")
    for year in years:
        dates, stack = read_land_year(source, year, nc_dir)
        valid = land_valid_mask(stack)
        for i, date in enumerate(dates):
            k = _INDEX[mmdd_of(date)]
            sums[k] += np.where(valid[i], stack[i], 0.0)
            counts[k] += valid[i]
        log.info("%s %d: %d days", source, year, len(dates))
    return sums, counts


def windowed_mean(sums: np.ndarray, counts: np.ndarray, window_days: int) -> np.ndarray:
    """The circular, sample-weighted windowed mean over the MMDD axis.

    NaN where the window holds no sample at all — a cell that is never inside
    the gauge analysis.
    """
    if window_days < 1 or window_days % 2 == 0:
        raise ValueError(f"window_days must be a positive odd number, got {window_days}")
    half = (window_days - 1) // 2
    n = sums.shape[0]
    # Wrap the axis so a window at either end reads the other end, then take a
    # running sum. Cumulative sums rather than a loop over offsets: one pass.
    pad_s = np.concatenate([sums[-half:], sums, sums[:half]]) if half else sums
    pad_c = np.concatenate([counts[-half:], counts, counts[:half]]) if half else counts
    cs = np.concatenate([np.zeros((1, *sums.shape[1:])), np.cumsum(pad_s, axis=0)])
    cc = np.concatenate([np.zeros((1, *counts.shape[1:])), np.cumsum(pad_c, axis=0)])
    wsum = cs[window_days:window_days + n] - cs[:n]
    wcnt = cc[window_days:window_days + n] - cc[:n]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(wcnt > 0, wsum / wcnt, np.nan).astype("float32")


def write(
    source: str,
    normal: np.ndarray,
    *,
    period: str,
    window_days: int,
    clim_dir: Path | None = None,
) -> Path:
    """Write one source's climatology, via a temp file so a reader never sees half."""
    path = land_clim_path(source, clim_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".nc.part")

    grid = land_grid()
    with netCDF4.Dataset(tmp, "w", format="NETCDF4") as ds:
        ds.createDimension("mmdd", len(MMDD_KEYS))
        ds.createDimension("lat", normal.shape[1])
        ds.createDimension("lon", normal.shape[2])
        ds.createVariable("mmdd", "i2", ("mmdd",))[:] = np.array(MMDD_KEYS, dtype="int16")
        # South-up, like every array `shared.fields` returns: row 0 is the
        # southernmost row. Written out so the file explains itself to a reader that
        # is not this module.
        ds.createVariable("lat", "f4", ("lat",))[:] = grid.lat(np.arange(grid.nlat))
        ds.createVariable("lon", "f4", ("lon",))[:] = grid.lon(np.arange(grid.nlon))
        var = ds.createVariable(
            source, "f4", ("mmdd", "lat", "lon"),
            zlib=True, complevel=4, fill_value=np.float32(np.nan),
            chunksizes=(1, normal.shape[1], normal.shape[2]),
        )
        var[:] = normal
        var.units = "mm/day" if source == "precip" else "degC"
        ds.setncatts({
            "source": "NOAA CPC Global Unified (NOAA PSL)",
            "variable": source,
            "baseline_period": period,
            "window_days": np.int32(window_days),
            "statistic": "mean",
            "orientation": "south-up; row 0 is 89.75S; longitudes 0-360",
            "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        })
    tmp.replace(path)
    return path


def build(source: str, *, nc_dir: Path | None = None, clim_dir: Path | None = None) -> Path:
    """Build and write one source's climatology, per its declared baseline."""
    period, window = declared_baseline(source)
    years = baseline_years(period)
    sums, counts = accumulate(source, years, nc_dir)
    normal = windowed_mean(sums, counts, window)
    path = write(source, normal, period=period, window_days=window, clim_dir=clim_dir)
    log.info(
        "%s: %s, %d-day window, %d cells with a normal -> %s",
        source, period, window, int(np.isfinite(normal[0]).sum()), path,
    )
    return path


__all__ = ["LAND_CLIM_DIR", "build", "windowed_mean", "accumulate", "declared_baseline"]
