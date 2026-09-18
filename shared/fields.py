"""Read CoralTemp NetCDF into subset arrays on the project's own conventions.

This module exists so the two orientation rules are applied in exactly one
place. Both produce output that looks entirely plausible when they are wrong,
which is why they are asserted here rather than trusted at each call site:

  1. **Longitude.** Source files run -179.975..179.975. The project indexes on
     0-360 (`domain.yml`'s `lon0: 0.025`) so the Pacific box is one contiguous
     `gx` span instead of two wrapping ones. The conversion is a roll by half
     the grid: ``gx_project = (gx_file + 3600) % 7200``.

  2. **Latitude.** The DAILY files are south-up (`lat[0] = -89.975`), matching
     `lon0`'s companion `lat0`. The 366 CLIMATOLOGY files are **north-up**
     (`lat[0] = +89.975`) and must be flipped. Subtracting them unflipped gives
     an anomaly field in the +/-18 degC range rather than +/-5 — wrong in every
     cell, and it renders as a perfectly believable map.

Everything returned is already subset to `domain.yml`'s box, so row 0 is the
box's southern edge and column 0 its western edge.

**The NOAA CPC land archive is read here too, and its conventions are not these
two.** It is already 0-360 (so it must NOT be rolled) and it is north-up (so it
must be flipped), on its own 0.5-degree grid. See the land section at the foot of
this module; `_check_land_axes` verifies both against the file's own coordinates
rather than trusting either.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from pathlib import Path

import netCDF4
import numpy as np

from .domain import global_grid, land_grid, subset, subset_shape, variable

log = logging.getLogger(__name__)

# Both archives live under the one ./data bind mount: the daily files in
# `sst/`, the 366 climatology files in `climatology/`. They are separate
# directories because they have opposite lifetimes — the dailies are pruned to
# a retention window, the climatology is kept forever.
NC_DIR = Path(os.environ.get("OISST_NC_DIR", "/opt/data/sst"))
CLIM_DIR = Path(os.environ.get("CRW_CLIM_DIR", "/opt/data/climatology"))
# The Marine Heatwave category archive: a THIRD daily archive, one file per date,
# from a different product suite than CoralTemp (see `download.py` for the URL).
# It shares the grid and the land mask exactly — measured, both have the same
# 7,477,923 ocean cells in the Pacific box — but not the lifetime: like the
# dailies it is pruned to the retention window.
MHW_DIR = Path(os.environ.get("CRW_MHW_DIR", "/opt/data/MHW"))
# The land archive: NOAA CPC Global Unified, from NOAA PSL. A FOURTH archive, and
# the only one that is **one file per YEAR** rather than per date — `precip.2015.nc`
# holds all 365 days. It also has the opposite lifetime to the dailies: nothing
# prunes it. The whole record from 1985 is ~9.5 GB for all three variables, so it
# is kept forever like the climatology, which is what keeps land history
# re-ingestable and re-renderable without a re-download.
LAND_DIR = Path(os.environ.get("CPC_NC_DIR", "/opt/data/land"))

# coraltemp_v3.1_19850101.nc
DAILY_RE = re.compile(r"^coraltemp_v3\.1_(?P<date>\d{8})\.nc$")
# noaa-crw_mhw_v1.0.1_category_19850101.nc
MHW_RE = re.compile(r"^noaa-crw_mhw_v1\.0\.1_category_(?P<date>\d{8})\.nc$")
# ct5km_v3.1_clim-sst-mean-daily-window-01day-01grid-source19912020_day0101.nc
CLIM_GLOB = "ct5km_v3.1_clim-sst-mean-daily-window-01day-01grid-source*_day{mmdd:04d}.nc"
# precip.2015.nc / tmax.2015.nc / tmin.2015.nc — a YEAR, not a date.
LAND_RE = re.compile(r"^(?P<variable>precip|tmax|tmin)\.(?P<year>\d{4})\.nc$")
LAND_VARIABLES = ("precip", "tmax", "tmin")

VARIABLE_NAME = "analysed_sst"
MHW_VARIABLE_NAME = "heatwave_category"

# The category range that counts as a heatwave. Everything outside it is dropped
# at ingest and drawn transparent: land, ice and heatwave-free ocean are three
# different things but none of them is a marine heatwave, and this layer exists
# to show where one is.
#
# **Both ends are load-bearing, and the upper one is the whole reason this is a
# range rather than a floor.** NOAA re-encoded `heatwave_category` on
# **2024-07-01**, mid-archive and without changing the filename, the version
# string or the URL:
#
#     ..2024-06-30   int8   _FillValue=-127  valid_min=-2  land -127, ice -1
#     2024-07-01..   uint8  _FillValue= 251  valid_min= 0  land and ice both 251
#
# A `raw >= 1` floor is correct on the first and catastrophic on the second: 251
# is a *positive* number, so every land and ice cell passes it. It cost 1.7
# billion junk rows in `mhw_daily` (787 days, ~46% of the table) and put land at
# Cat 5 in every rendered frame from that date on — and nothing failed. The
# ingest ran clean, `/coverage` reported the archive complete, and the only
# outward sign was a region mean of 62 on a 1..5 scale.
#
# Testing `<= 5` instead of the file's own `_FillValue` is deliberate: 1..5 is
# fixed by the product definition (it is the five names in the legend), so the
# rule holds across both encodings and any third one NOAA ships next. The fill
# value is what changed; the categories are what did not.
MHW_MIN_CATEGORY = 1
MHW_MAX_CATEGORY = 5

# The companion `mask` variable in the same file: 0 water, 1 ice, 2 land.
MHW_MASK_NAME = "mask"
MHW_MASK_LAND = 2
# What a repaired land cell is rewritten to. Any value outside 1..5 does, since
# `mhw_valid_mask` is the only thing that reads it; the first encoding's own
# land code is used so a repaired array looks like the file it came from.
MHW_LAND_CODE = -127

# **A third failure of the source's land encoding, and this one is not a
# re-encoding — it is a bad file.** Every **29 February** in the archive ships
# with land collapsed into ocean and set to category 5:
#
#     2024-02-28   land: 8,726,860 cells at -127   mask: 8,726,860 cells at 2
#     2024-02-29   land: none at -127              mask: no 2 at all
#                  category 5: 8,731,446 cells     mask: 22,240,556 at 0 (water)
#
# The `mask` variable is wrong the same way — it reports water where land is —
# and its ice count is byte-identical across 2016, 2020 and 2024, so the
# leap-day mask is frozen boilerplate rather than that day's. All ten leap days
# in the archive are affected.
#
# `mhw_valid_mask`'s 1..5 bound cannot catch it: 5 is a legal category. It cost
# 2,022,077 land cells a day at Cat 5 in `mhw_daily`, took the basin's heatwave
# extent to 62.4% on 2024-02-29 against ~30% either side, and drew the
# continents in Cat 5's dark red on every leap-day frame.
#
# So the file's own land encoding is not trusted on its own: `read_mhw_raw`
# checks that the file actually carries land, and when it does not it takes the
# land mask from the same date's CoralTemp file — the authority on which cells
# are ocean everywhere else in this project — and rewrites those cells. It
# raises rather than guessing if that file is not on disk: ingesting a leap day
# with land at Cat 5 is exactly the silent failure this is here to end.


def mmdd_of(date: dt.date) -> int:
    """The climatology key for a date: month*100 + day, e.g. 2026-08-24 -> 824.

    Leap days need no special case — CoralTemp ships a `day0229` file.
    """
    return date.month * 100 + date.day


def daily_path(date: dt.date, nc_dir: Path | None = None) -> Path:
    return (nc_dir or NC_DIR) / f"coraltemp_v3.1_{date:%Y%m%d}.nc"


def mhw_path(date: dt.date, nc_dir: Path | None = None) -> Path:
    return (nc_dir or MHW_DIR) / f"noaa-crw_mhw_v1.0.1_category_{date:%Y%m%d}.nc"


def clim_path(mmdd: int, clim_dir: Path | None = None) -> Path:
    """The climatology file for an MMDD key.

    Globbed rather than formatted because the baseline years are embedded in the
    filename (`source19912020`); a future re-baselining should be picked up, not
    silently missed.
    """
    clim_dir = clim_dir or CLIM_DIR
    matches = sorted(clim_dir.glob(CLIM_GLOB.format(mmdd=mmdd)))
    if not matches:
        raise FileNotFoundError(f"no climatology file for mmdd {mmdd:04d} in {clim_dir}")
    if len(matches) > 1:
        log.warning("multiple climatology files for %04d, using %s", mmdd, matches[-1].name)
    return matches[-1]


def _subset_indices():
    """``(gy0, gy1, gx0, gx1)`` inclusive global indices of the configured box."""
    grid, box = global_grid(), subset()
    gy0, gy1 = box.gy_range(grid)
    gx0, gx1 = box.gx_range(grid)
    return gy0, gy1, gx0, gx1


def _to_project_frame(raw: np.ndarray, *, flip_lat: bool) -> np.ndarray:
    """Roll a full-grid source array onto the project's axes and subset it."""
    grid, box = global_grid(), subset()
    if raw.shape != (grid.nlat, grid.nlon):
        raise ValueError(f"expected {(grid.nlat, grid.nlon)} grid, got {raw.shape}")

    if flip_lat:
        raw = raw[::-1]
    # -180..180 -> 0..360. `lon0` sits half a grid from the source's origin.
    raw = np.roll(raw, grid.nlon // 2, axis=1)

    gy0, gy1, gx0, gx1 = _subset_indices()
    out = raw[gy0 : gy1 + 1, gx0 : gx1 + 1]
    if out.shape != (box.nlat, box.nlon):
        raise ValueError(
            f"subset produced {out.shape}, domain.yml declares {(box.nlat, box.nlon)}"
        )
    return out


def _read_raw(path: Path, *, squeeze_time: bool, var_name: str = VARIABLE_NAME) -> np.ndarray:
    with netCDF4.Dataset(path) as ds:
        var = ds.variables[var_name]
        # Raw shorts, not the masked/scaled floats netCDF4 would hand back — the
        # scale factor is reapplied by the ALIAS columns in ClickHouse, and by
        # `as_celsius()` for rendering. For MHW it also keeps the fill value
        # visible instead of collapsed into a mask — which is what lets
        # `mhw_valid_mask` see, and reject, the 251 that the post-2024-07-01
        # files use for land and ice.
        var.set_auto_maskandscale(False)
        return np.asarray(var[0] if squeeze_time else var[:])


def read_daily_raw(date: dt.date, nc_dir: Path | None = None) -> np.ndarray:
    """One day's raw Int16 SST over the box. Already south-up; rolled to 0-360."""
    return _to_project_frame(
        _read_raw(daily_path(date, nc_dir), squeeze_time=True), flip_lat=False
    )


def mhw_carries_land(date: dt.date, nc_dir: Path | None = None) -> bool:
    """Does this MHW file's own `mask` variable flag any land?

    A good file flags ~8.7 M land cells globally. A leap-day file flags none,
    having collapsed land into water and set its category to 5 — see
    `MHW_LAND_CODE` above. This is the whole detection: land is not optional on
    a global grid, so its absence is the file telling you it is wrong.
    """
    mask = _read_raw(mhw_path(date, nc_dir), squeeze_time=True, var_name=MHW_MASK_NAME)
    return bool((mask == MHW_MASK_LAND).any())


def read_mhw_raw(
    date: dt.date,
    nc_dir: Path | None = None,
    *,
    sst_dir: Path | None = None,
) -> np.ndarray:
    """One day's raw heatwave category over the box, land repaired if need be.

    South-up like the dailies — **verified, not assumed**: the MHW files declare
    `lat[0] = -89.975` exactly as CoralTemp does, so no flip. (NOAA's own browse
    PNGs for the same product *are* north-up, which is a trap if the palette is
    ever re-derived from one.)

    Values come back as the source's own codes, and **which codes those are
    depends on the date** — NOAA re-encoded the variable on 2024-07-01. Before:
    int8, -127 land, -1 ice, 0 no heatwave. From then on: uint8, 251 for land
    *and* ice together, 0 no heatwave. Only 1..5 mean the same thing in both,
    which is why `mhw_valid_mask` bounds the range at both ends rather than
    testing for a fill value. See `MHW_MIN_CATEGORY`.

    **On a file that carries no land at all — every 29 February in the archive —
    the land mask is taken from the same date's CoralTemp file** and those cells
    are rewritten to `MHW_LAND_CODE`. That file has to be on disk; without it
    this raises rather than returning a field with continents at Cat 5. See
    `MHW_LAND_CODE` for the measurement.
    """
    raw = _to_project_frame(
        _read_raw(mhw_path(date, nc_dir), squeeze_time=True, var_name=MHW_VARIABLE_NAME),
        flip_lat=False,
    )
    if mhw_carries_land(date, nc_dir):
        return raw
    return _repair_mhw_land(raw, date, sst_dir)


def _repair_mhw_land(raw: np.ndarray, date: dt.date, sst_dir: Path | None) -> np.ndarray:
    """Cut land out of a leap-day MHW field using the day's CoralTemp mask."""
    path = daily_path(date, sst_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"{mhw_path(date).name} carries no land — its category 5 covers the "
            f"continents (see shared/fields.py) — and {path} is not on disk to "
            "take a land mask from. Download the CoralTemp file for this date "
            "and retry; ingesting or rendering it as it stands would put land "
            "at Cat 5."
        )
    land = ~valid_mask(_to_project_frame(_read_raw(path, squeeze_time=True), flip_lat=False))
    # int16 because MHW_LAND_CODE has to fit whichever dtype the file used, and
    # the post-2024-07-01 files are unsigned.
    out = raw.astype("int16")
    out[land] = MHW_LAND_CODE
    log.info("%s: repaired %d land cells miscoded as ocean", date, int(land.sum()))
    return out


def mhw_valid_mask(raw: np.ndarray) -> np.ndarray:
    """Cells that are actually in a heatwave — the only ones stored or drawn.

    Bounded above as well as below. See `MHW_MIN_CATEGORY` for why: the upper
    bound is what excludes the post-2024-07-01 files' 251 fill, which a floor
    alone lets through as a heatwave four times worse than Cat 5.
    """
    return (raw >= MHW_MIN_CATEGORY) & (raw <= MHW_MAX_CATEGORY)


def as_category(raw: np.ndarray) -> np.ndarray:
    """Raw MHW codes -> float32 category, NaN everywhere there is no heatwave.

    Land, ice and heatwave-free ocean all become NaN, which is what puts them in
    alpha 0 downstream. They are three genuinely different states, but this layer
    answers one question — where is there a heatwave, and how bad — and for that
    question they are the same answer. (Contrast `anom`, where ocean-without-a-
    value has to be told apart from land and gets its own grey sentinel.)
    """
    out = raw.astype("float32")
    out[~mhw_valid_mask(raw)] = np.nan
    return out


def read_clim_raw(mmdd: int, clim_dir: Path | None = None) -> np.ndarray:
    """One MMDD's raw Int16 climatology over the box, **flipped** to south-up."""
    return _to_project_frame(
        _read_raw(clim_path(mmdd, clim_dir), squeeze_time=False), flip_lat=True
    )


def valid_mask(raw: np.ndarray, variable_name: str = "sst") -> np.ndarray:
    return raw != variable(variable_name).fill_value


def as_celsius(raw: np.ndarray, variable_name: str = "sst") -> np.ndarray:
    """Raw counts -> float32 degC, with the fill value becoming NaN."""
    var = variable(variable_name)
    out = raw.astype("float32") * var.scale_factor + var.add_offset
    out[raw == var.fill_value] = np.nan
    return out


def check_orientation(daily_raw: np.ndarray, clim_raw: np.ndarray) -> None:
    """Assert the climatology's ocean is a subset of the day's ocean.

    This is the diagnostic that catches a latitude flip. Correctly oriented, the
    climatology covers a strict subset of the daily field (it omits the ice
    fringe); flipped, the overlap collapses — globally from 13.31M cells to
    9.17M, and the resulting anomaly spans about +/-18 degC instead of +/-5.

    Raises rather than warns: a wrong map is worse than no map.
    """
    dm = valid_mask(daily_raw)
    cm = valid_mask(clim_raw)
    orphans = int((cm & ~dm).sum())
    if orphans:
        raise ValueError(
            f"{orphans} climatology cells have no daily value — the climatology "
            "is expected to be a strict subset of the daily ocean mask. A "
            "latitude flip is the usual cause; see shared/fields.py."
        )


def anomaly(daily_raw: np.ndarray, clim_raw: np.ndarray) -> np.ndarray:
    """`daily - climatology` in degC, NaN where either side is absent.

    NaN therefore means two different things, which the renderer separates:
    land (no daily value) and ice-fringe ocean (daily but no climatology). Use
    `no_clim_mask()` to tell them apart.
    """
    check_orientation(daily_raw, clim_raw)
    out = as_celsius(daily_raw) - as_celsius(clim_raw)
    return out


def no_clim_mask(daily_raw: np.ndarray, clim_raw: np.ndarray) -> np.ndarray:
    """Ocean cells with SST but no climatology — anomaly undefined, not land."""
    return valid_mask(daily_raw) & ~valid_mask(clim_raw)


# --- The land archive: NOAA CPC Global Unified -------------------------------
#
# A different NOAA program (Climate Prediction Center, not Coral Reef Watch), a
# different grid (0.5 degree, `domain.yml`'s `land` block) and a different file
# shape (one NetCDF per YEAR, `(time, lat, lon)`). The reader lives here anyway,
# because this module exists to be the ONE place a grid convention is applied,
# and this source has two of its own:
#
#   1. It is **already 0-360** (`lon 0.25 .. 359.75`), so it is the one source in
#      the project that must NOT be rolled. Rolling it by half the grid — the
#      habit every other reader here has — would draw the Pacific over Africa.
#
#   2. It is **north-up** (`lat[0] = +89.75`), so it must be flipped, exactly as
#      the CoralTemp climatology files are.
#
# Neither failure is loud. `_check_land_axes` therefore verifies both against the
# file's own coordinate variables on every read, which is exact rather than
# heuristic: if the rows and columns we slice are not the degrees `domain.yml`
# says they are, nothing downstream can tell.

# What the files use for "no data here" — ocean, and land outside the gauge
# network. Not a `_FillValue`, so netCDF4's own masking is not what finds it.
LAND_MISSING = -9.96921e36
# Anything at or below this is the missing sentinel. A generous threshold rather
# than an equality test: the value is a float32 the file declares to 6 digits,
# and a real temperature never approaches -1e30.
LAND_MISSING_FLOOR = -1e30

# Storage quantisation, and the two scales are not the same choice.
#
# Temperature: 0.01 degC into Int16. `valid_range` is -90..50, so -9000..5000,
# comfortably inside the type. Unlike SST these counts are a QUANTISATION rather
# than the source's own encoding — CPC ships float32 — costing ~0.005 degC on an
# analysis whose real uncertainty is station density.
#
# Precipitation: 0.1 mm into UInt16, deliberately NOT 0.01. Rain is non-negative,
# and 0.01 mm would cap a UInt16 at 655.35 mm against a measured global maximum
# of 666.69 mm and a declared `valid_range` of 1000 — i.e. it would clip real
# values, at exactly the extremes a rainfall map is read for. 0.1 mm reaches
# 6553.5 mm and is the precision daily rainfall is reported at anyway.
LAND_TEMP_SCALE = 0.01
LAND_PRECIP_SCALE = 0.1
LAND_PRECIP_MAX_COUNT = 65535


def land_path(variable_name: str, year: int, nc_dir: Path | None = None) -> Path:
    """The year file for one land variable, e.g. `tmax.2015.nc`."""
    if variable_name not in LAND_VARIABLES:
        raise ValueError(
            f"unknown land variable {variable_name!r}; known: {LAND_VARIABLES}"
        )
    return (nc_dir or LAND_DIR) / f"{variable_name}.{year}.nc"


def _land_file_slices() -> tuple[slice, slice]:
    """The box as a slice into a NORTH-UP file's `(lat, lon)` axes.

    Sliced on the way off disk rather than after: a year of the full grid is
    ~378 MB of float32, the box is ~138 MB, and nothing needs the rest.
    """
    grid = land_grid()
    gy0, gy1 = subset().gy_range(grid)
    gx0, gx1 = subset().gx_range(grid)
    # Project row `gy` counts north from the south pole; the file's rows count
    # south from the north pole. This is the flip, expressed as an index.
    return slice(grid.nlat - 1 - gy1, grid.nlat - gy0), slice(gx0, gx1 + 1)


def _check_land_axes(ds) -> None:
    """Verify the file's own lat/lon against `domain.yml`'s `land` grid.

    The exact form of the orientation guard the ocean side gets heuristically
    from `check_orientation()`. Both of this source's conventions are checked at
    once: if the file were south-up, or on a -180..180 longitude frame, the
    degrees at the sliced indices would not be the degrees the grid declares, and
    every downstream consumer would be told the wrong cell's value with complete
    confidence.
    """
    grid = land_grid()
    lat = np.asarray(ds.variables["lat"][:], dtype="float64")
    lon = np.asarray(ds.variables["lon"][:], dtype="float64")
    if lat.shape != (grid.nlat,) or lon.shape != (grid.nlon,):
        raise ValueError(
            f"land file has a {lat.size}x{lon.size} grid, domain.yml's `land` "
            f"declares {grid.nlat}x{grid.nlon}"
        )
    ys, xs = _land_file_slices()
    gy0, gy1 = subset().gy_range(grid)
    gx0, gx1 = subset().gx_range(grid)

    # [::-1] is the flip itself: applied, the file's rows must read as the
    # project's south-up latitudes.
    want_lat = grid.lat(np.arange(gy0, gy1 + 1))
    got_lat = lat[ys][::-1]
    if not np.allclose(got_lat, want_lat, atol=1e-6):
        raise ValueError(
            "land file latitudes do not match the `land` grid after the flip "
            f"(got {got_lat[0]:.3f}..{got_lat[-1]:.3f}, expected "
            f"{want_lat[0]:.3f}..{want_lat[-1]:.3f}). The file is expected to be "
            "north-up; see shared/fields.py."
        )
    # No roll, and this is what says so. CPC ships 0-360 already.
    want_lon = grid.lon(np.arange(gx0, gx1 + 1))
    got_lon = lon[xs]
    if not np.allclose(got_lon, want_lon, atol=1e-6):
        raise ValueError(
            "land file longitudes do not match the `land` grid "
            f"(got {got_lon[0]:.3f}..{got_lon[-1]:.3f}, expected "
            f"{want_lon[0]:.3f}..{want_lon[-1]:.3f}). CPC files are already "
            "0-360 and must NOT be rolled; see shared/fields.py."
        )


def read_land_year(
    variable_name: str, year: int, nc_dir: Path | None = None
) -> tuple[list[dt.date], np.ndarray]:
    """One year of a land variable over the box: `(dates, stack)`.

    `stack` is `(ntime, 250, 380)` float32 in the source's own units — degC or
    mm — south-up and unrolled, with `LAND_MISSING` left visible rather than
    masked. Quantisation into storage counts happens at ingest.

    **Per year, not per date, and deliberately.** These are 60-80 MB HDF5 files
    holding every day of a year; opening one per date would be ~365 opens of the
    same file to read a 250x380 slice out of each.

    `dates` is as long as `stack`'s first axis and comes from the file's own
    `time`, so a partly-written current-year file — which is the normal state of
    `precip.2026.nc` — reports exactly the days it holds.
    """
    path = land_path(variable_name, year, nc_dir)
    ys, xs = _land_file_slices()
    with netCDF4.Dataset(path) as ds:
        _check_land_axes(ds)
        time = ds.variables["time"]
        stamps = netCDF4.num2date(
            time[:], time.units, only_use_cftime_datetimes=False, only_use_python_datetimes=True
        )
        dates = [dt.date(t.year, t.month, t.day) for t in stamps]

        var = ds.variables[variable_name]
        var.set_auto_maskandscale(False)
        stack = np.asarray(var[:, ys, xs], dtype="float32")

    # The flip. See `_land_file_slices`.
    stack = stack[:, ::-1, :]

    want = subset_shape(land_grid())
    if stack.shape[1:] != want:
        raise ValueError(f"{path.name}: box came out {stack.shape[1:]}, expected {want}")
    if len(dates) != stack.shape[0]:
        raise ValueError(f"{path.name}: {len(dates)} timestamps for {stack.shape[0]} days")
    return dates, stack


def land_valid_mask(raw: np.ndarray) -> np.ndarray:
    """Cells that carry a reading.

    **Zero is a reading, not a gap**, which is the easiest thing to get wrong
    here: a dry day over Darwin is 0.0 mm and belongs in the table. Only the
    missing sentinel and NaN are absent.
    """
    return np.isfinite(raw) & (raw > LAND_MISSING_FLOOR)


def to_temp_counts(celsius: np.ndarray) -> np.ndarray:
    """degC -> the Int16 counts `land_temp_daily` stores. See `LAND_TEMP_SCALE`."""
    counts = np.rint(np.asarray(celsius, dtype="float64") / LAND_TEMP_SCALE)
    if counts.size and (counts.min() < -32768 or counts.max() > 32767):
        raise ValueError(
            f"temperature {counts.min() * LAND_TEMP_SCALE:.2f}.."
            f"{counts.max() * LAND_TEMP_SCALE:.2f} degC does not fit Int16 at "
            f"{LAND_TEMP_SCALE} degC — the source declares valid_range -90..50"
        )
    return counts.astype("int16")


def to_precip_counts(mm: np.ndarray) -> np.ndarray:
    """mm -> the UInt16 counts `land_precip_daily` stores.

    Raises rather than clipping on an overflow, for the reason
    `shared/render.py` clamps rather than wraps: a silently wrapped 6600 mm would
    come back as a drizzle, and the extremes are what a rainfall layer is read
    for. At 0.1 mm the ceiling is 6553.5 mm against a measured global maximum of
    666.69 mm, so this should never fire — and if it does, it is news.
    """
    counts = np.rint(np.asarray(mm, dtype="float64") / LAND_PRECIP_SCALE)
    if counts.size and (counts.min() < 0 or counts.max() > LAND_PRECIP_MAX_COUNT):
        raise ValueError(
            f"precipitation {counts.min() * LAND_PRECIP_SCALE:.1f}.."
            f"{counts.max() * LAND_PRECIP_SCALE:.1f} mm does not fit UInt16 at "
            f"{LAND_PRECIP_SCALE} mm"
        )
    return counts.astype("uint16")
