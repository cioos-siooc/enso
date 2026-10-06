"""Point timeseries for the land overlay's six layers.

The land twin of `timeseries.point_timeseries`, and deliberately a separate
module: the land tables index a DIFFERENT grid (CPC's 0.5 degree, `land_grid()`)
under the same `gy`/`gx` column names, and nothing here may ever be joined to an
ocean table. Keeping the two apart is the cheapest way to keep that true.

**A bucket means exactly what the map frame means** — `shared/buckets.py`'s
`_land_bucket`, cell for cell:

    none        mean of the dailies
    difference  mean of (value - normal(mmdd)) over days that have a normal
    log2_ratio  log2(mean(value) / mean(normal)) over those same days, floored
                at 2^LOG2_FLOOR, and null where the normal is under `min_normal`

So a chart point and the map frame for the same bucket agree, which is the
invariant the period mechanism exists for. The reduction is done here in Python
rather than in SQL because the normal lives in the climatology FILE, not in
ClickHouse (there is no `land_clim` table yet — ROADMAP B6), and one cell's
record is ~15k rows either way.

**"Land" is CoralTemp's land, at 0.05 degree**, not "a CPC cell with data". The
land frames are cut to that coastline (`global_ocean_mask`), so a click that
lands on drawn ocean must not come back with the 0.5-degree block that
overhangs it — the chart would plot rain for a pixel the map shows as sea. An
ocean pixel answers with an empty series and `surface: "ocean"`, which is how
the ocean and land series partition a click between them.
"""

from __future__ import annotations

import datetime as dt
import functools
import logging
import math

from shared.buckets import LOG2_FLOOR
from shared.domain import global_grid, land_grid, variable
from shared.fields import global_ocean_mask, land_layer_ready, mmdd_of, read_land_clim_cell

from .clickhouse_helpers import DATABASE, client
from .periods import Period, start_of

log = logging.getLogger(__name__)

# Which table and column each CPC source is read from.
_SOURCE_COLUMNS = {
    "tmax": ("land_temp_daily", "tmax"),
    "tmin": ("land_temp_daily", "tmin"),
    "precip": ("land_precip_daily", "precip"),
}


class LandLayerError(ValueError):
    """A request the layer cannot answer: an undeclared period, or no normal yet."""


def is_ocean(lat: float, lon: float) -> bool:
    """Whether the 0.05-degree pixel under a click is CoralTemp ocean."""
    grid = global_grid()
    return bool(global_ocean_mask()[int(grid.gy(lat)), int(grid.gx(lon))])


# Per cell, not per file: a whole climatology is ~380 MB and the API runs several
# workers. The file is chunked one day per chunk, so a cold cell decompresses all
# 366 of them; caching the 366 floats that come out is what makes the second
# request for the same cell (every period and variable toggle) free.
@functools.lru_cache(maxsize=512)
def _cell_normal(source: str, gy: int, gx: int, period: str, window_days: int) -> dict[int, float]:
    return read_land_clim_cell(source, gy, gx, period=period, window_days=window_days)


def land_point_timeseries(
    lat: float,
    lon: float,
    start: dt.date | None = None,
    end: dt.date | None = None,
    period: Period = "daily",
    variable_name: str = "land_tmax",
) -> dict:
    """Every ingested day of one land layer at the CPC cell nearest `(lat, lon)`."""
    var = variable(variable_name)
    if var.grid != "land":
        raise LandLayerError(f"{variable_name} is not a land layer")
    if period not in var.periods:
        raise LandLayerError(
            f"{var.short_name} is shown {' or '.join(var.periods)} only, not {period}"
        )
    if var.transform != "none" and not land_layer_ready(variable_name):
        raise LandLayerError("The 1991-2020 land climatology has not been built yet")

    grid = land_grid()
    gy, gx = int(grid.gy(lat)), int(grid.gx(lon))
    ocean = is_ocean(lat, lon)

    rows: list[tuple] = []
    if not ocean:
        table, column = _SOURCE_COLUMNS[var.source]
        clauses, params = "", {"gy": gy, "gx": gx}
        if start is not None:
            clauses += " AND date >= %(start)s"
            params["start"] = start
        if end is not None:
            clauses += " AND date <= %(end)s"
            params["end"] = end
        rows = client().query(
            f"""
            SELECT date, {column} FROM {DATABASE}.{table}
            WHERE gy = %(gy)s AND gx = %(gx)s{clauses}
            ORDER BY date
            """,
            parameters=params,
        ).result_rows

    normal: dict[int, float] = {}
    if rows and var.transform != "none":
        normal = _cell_normal(
            var.source, gy, gx, var.baseline.period, var.baseline.window_days
        )

    # Fold days into buckets. Ordered by date, so buckets arrive in order too.
    buckets: dict[dt.date, list] = {}
    for date, value in rows:
        if value is None or not math.isfinite(value):
            continue
        acc = buckets.setdefault(start_of(date, period), [0, 0.0, 0.0, 0])
        acc[0] += 1  # days present
        if var.transform == "none":
            acc[1] += value
            acc[3] += 1
            continue
        clim = normal.get(mmdd_of(date))
        if clim is None:
            continue
        acc[1] += value
        acc[2] += clim
        acc[3] += 1  # days paired with a normal

    places = var.precision
    dates, values, n_days = [], [], []
    for bucket, (n, total, clim_total, paired) in buckets.items():
        value: float | None
        if paired == 0:
            value = None
        elif var.transform == "none":
            value = total / paired
        elif var.transform == "difference":
            value = (total - clim_total) / paired
        else:
            actual, norm = total / paired, clim_total / paired
            # Too dry for a ratio: the map's grey. Null here, not a number.
            value = None if norm < var.min_normal else math.log2(max(actual / norm, 2.0**LOG2_FLOOR))
        dates.append(str(bucket))
        values.append(None if value is None else round(value, places))
        n_days.append(n)

    return {
        "variable": variable_name,
        "quantity": None,
        "units": var.units,
        "period": period,
        "surface": "ocean" if ocean else "land",
        "requested": {"lat": lat, "lon": lon},
        "cell": {
            "gy": gy,
            "gx": gx,
            "lat": float(grid.lat(gy)),
            "lon": float(grid.lon(gx)),
        },
        "dates": dates,
        "values": values,
        "n_days": n_days,
        "climatologyBaseline": var.baseline.period if var.baseline else None,
    }
