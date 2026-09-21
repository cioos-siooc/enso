"""One bucket of one variable, built from whatever NetCDF is on disk.

**This is the single implementation, and that is the point.** It used to exist
twice — `process/CRW/imaging.py` for the bulk and daily renders, and
`api/modules/render.py` for the on-demand render of buckets still inside the
retention window — which is exactly the drift the retirement of `api/prerender.py`
was meant to end. Two copies of "what is a week" is one copy too many, and the
MHW variable made that concrete: it aggregates a bucket differently from the
other two, and a second copy would have quietly kept averaging it.

Nothing here touches ClickHouse. Images are built from files, never from the
database — see `shared/ch.py` for why the schema carries no `by_date` projection.

### How a bucket is reduced, per variable

`sst` and `anom` take the **mean** over the days present. `mhw` takes the
**maximum**, because a category is an ordinal class and its mean is not one: a
cell at Cat 1 for two days of seven averages to 0.29, which is not a category at
all and would draw as nothing. The max answers the question the frame is read
for — how bad did it get this week — and keeps every period on the same discrete
1..5 scale, so one legend serves all three.

The six **land** layers are reduced by what `domain.yml` declares for each
(`source`, `transform`) — see `_land_bucket` at the foot of this module.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import numpy as np

from . import fields
from .domain import variable
from .periods import Period, span

log = logging.getLogger(__name__)


def _day_field(
    day: dt.date, variable_name: str, nc_dir: Path | None, mhw_dir: Path | None
) -> tuple[np.ndarray, np.ndarray | None] | None:
    """One day's `(value, no_clim)` for a variable, or None if its file is absent.

    NaN in `value` means "no value here" in every case; what that means
    physically differs by variable, and `no_clim` is the only distinction that
    survives into the image (ocean with SST but no climatology, drawn grey). For
    `mhw` there is deliberately no such distinction — land, ice and heatwave-free
    ocean are all simply not a heatwave.
    """
    try:
        if variable_name == "mhw":
            # `sst_dir` is not a fallback: on a leap day the MHW file carries
            # no land of its own and the CoralTemp file is what supplies it.
            return (
                fields.as_category(fields.read_mhw_raw(day, mhw_dir, sst_dir=nc_dir)),
                None,
            )
        raw = fields.read_daily_raw(day, nc_dir)
        if variable_name == "sst":
            return fields.as_celsius(raw), None
        clim = fields.read_clim_raw(fields.mmdd_of(day))
        return fields.anomaly(raw, clim), fields.no_clim_mask(raw, clim)
    except (FileNotFoundError, OSError):
        return None


def bucket_field(
    date: dt.date,
    period: Period,
    variable_name: str,
    available: set[dt.date] | None = None,
    *,
    nc_dir: Path | None = None,
    mhw_dir: Path | None = None,
    land_dir: Path | None = None,
) -> tuple[np.ndarray, np.ndarray | None, int] | None:
    """Reduce a bucket to one field, from whatever NetCDF is still on disk.

    Returns `(field, no_clim_mask_or_None, n_days)`, or None if no day in the
    bucket had a file. `n_days` lets the caller see how much of the bucket the
    result actually rests on.

    Cells are reduced where present: a cell that is ocean on some days of the
    week and ice-masked on others still gets a result over the days it had.

    `available` is an optional set of dates known to be on disk, which lets a
    caller skip the open/fail cycle on a sparse archive. It is only ever a
    filter — a date in it whose file is missing is still handled.
    """
    var = variable(variable_name)
    if var.grid == "land":
        return _land_bucket(date, period, var, land_dir=land_dir)

    first, last = span(date, period)
    reduce_max = var.categorical

    total: np.ndarray | None = None
    count: np.ndarray | None = None
    peak: np.ndarray | None = None
    missing_any: np.ndarray | None = None
    n_days = 0

    day = first
    while day <= last:
        if available is not None and day not in available:
            day += dt.timedelta(days=1)
            continue

        result = _day_field(day, variable_name, nc_dir, mhw_dir)
        if result is None:
            day += dt.timedelta(days=1)
            continue
        value, no_clim = result

        finite = np.isfinite(value)
        if count is None:
            count = np.zeros(value.shape, dtype="int32")
            missing_any = np.zeros(value.shape, dtype=bool)
            if reduce_max:
                peak = np.full(value.shape, -np.inf, dtype="float32")
            else:
                total = np.zeros(value.shape, dtype="float64")

        if reduce_max:
            # `np.maximum` would propagate the NaN; the whole point is that a day
            # with no heatwave at a cell must not erase another day's.
            np.maximum(peak, np.where(finite, value, -np.inf), out=peak)
        else:
            total[finite] += value[finite]
        count[finite] += 1
        if no_clim is not None:
            missing_any |= no_clim
        n_days += 1
        day += dt.timedelta(days=1)

    if count is None or n_days == 0:
        return None

    if reduce_max:
        field = np.where(count > 0, peak, np.nan).astype("float32")
    else:
        with np.errstate(invalid="ignore"):
            field = np.where(count > 0, total / np.maximum(count, 1), np.nan).astype("float32")

    # A cell with no anomaly on any contributing day stays "no climatology"; one
    # that had an anomaly on at least one day carries that day's value.
    no_clim = (missing_any & (count == 0)) if variable_name == "anom" else None
    return field, no_clim, n_days


# --- The land layers ---------------------------------------------------------
#
# Same contract as the ocean path above — `(field, no_value_mask, n_days)` or
# None — so `render.encode()`, `CRW.imaging` and the API's on-demand render take
# land with no branch of their own. What differs is where a day comes from (a
# slice of a CPC year file, via `fields.read_land_days`) and what a bucket is,
# which the variable DECLARES in `domain.yml` rather than this module deciding
# by name:
#
#   none        mean of the dailies. For tmax/tmin that is "the average daily
#               high/low", which is what a normal is; for precip it is mean
#               mm/day, so one legend serves every period.
#   difference  mean of (value - climatology(mmdd)) over the days present.
#   log2_ratio  log2(mean(value) / mean(climatology)), both over the SAME
#               valid days of the same cell — a ratio of means is a ratio of
#               totals, so this is "the bucket's rainfall as a share of normal".
#
# **The ratio is floored at 2^LOG2_FLOOR before the log**, not left to reach
# log2(0) = -inf: a bone-dry month is common in a dry region, and it must land on
# the driest colour. The encoding's own clamp would do the same with a huge
# negative, but a -inf passes through `to_mercator`'s arithmetic as NaN-adjacent
# trouble, so it is settled here where the meaning is.

LOG2_FLOOR = -4.0


def _land_bucket(
    date: dt.date, period: Period, var, *, land_dir: Path | None = None
) -> tuple[np.ndarray, np.ndarray | None, int] | None:
    if period not in var.periods:
        # The API refuses these with a 400 before they get here; reaching this
        # means a caller skipped `variable.periods`, and an empty frame would be
        # the silent version of that mistake.
        raise ValueError(
            f"{var.name} is not drawn at the {period} period "
            f"(declared: {', '.join(var.periods)})"
        )

    first, last = span(date, period)
    dates, stack = fields.read_land_days(var.source, first, last, land_dir)
    if not dates:
        return None

    valid = fields.land_valid_mask(stack)
    count = valid.sum(axis=0)
    has_data = count > 0
    values = np.where(valid, stack, 0.0).astype("float64")

    if var.transform == "none":
        with np.errstate(invalid="ignore", divide="ignore"):
            field = np.where(has_data, values.sum(axis=0) / count, np.nan)
        return field.astype("float32"), None, len(dates)

    clim = fields.read_land_clim(
        var.source,
        [fields.mmdd_of(d) for d in dates],
        period=var.baseline.period,
        window_days=var.baseline.window_days,
    )
    # A cell with a reading but no normal on that day contributes to neither
    # side. The climatology mask is static in practice, but a day is only
    # compared with a normal that exists.
    paired = valid & np.isfinite(clim)
    n = paired.sum(axis=0)
    usable = n > 0
    clim0 = np.where(paired, clim, 0.0).astype("float64")
    vals0 = np.where(paired, stack, 0.0).astype("float64")

    if var.transform == "difference":
        with np.errstate(invalid="ignore", divide="ignore"):
            field = np.where(usable, (vals0 - clim0).sum(axis=0) / n, np.nan)
        return field.astype("float32"), None, len(dates)

    # log2_ratio
    with np.errstate(invalid="ignore", divide="ignore"):
        actual = np.where(usable, vals0.sum(axis=0) / n, np.nan)
        normal = np.where(usable, clim0.sum(axis=0) / n, np.nan)
    too_dry = usable & (normal < var.min_normal)
    ok = usable & ~too_dry
    ratio = np.full(actual.shape, np.nan)
    ratio[ok] = actual[ok] / normal[ok]
    field = np.full(actual.shape, np.nan, dtype="float64")
    field[ok] = np.log2(np.maximum(ratio[ok], 2.0**LOG2_FLOOR))
    # `too_dry` is the no-value mask `encode()` turns into the sentinel grey:
    # the cell has rainfall data, it just has no meaningful normal to divide by.
    return field.astype("float32"), too_dry, len(dates)
