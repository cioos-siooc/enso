"""Grid geometry and variable metadata loaded from ``domain.yml``.

The single source of truth for converting between latitude/longitude and the
integer cell indices (``gy``, ``gx``) stored in ClickHouse. Those indices are
into the *global* CoralTemp grid, not the Pacific subset — see ``domain.yml``,
which also documents the two orientation conventions this file assumes.
"""

from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

_DOMAIN_YML = Path(__file__).with_name("domain.yml")


@dataclass(frozen=True)
class GlobalGrid:
    """The full CoralTemp 0.05-degree grid cell indices are defined against."""

    resolution: float
    lat0: float
    lon0: float
    nlat: int
    nlon: int

    def gy(self, lat):
        """Latitude (degrees_north) -> global row index."""
        return np.rint((np.asarray(lat, dtype="float64") - self.lat0) / self.resolution).astype("int32")

    def gx(self, lon):
        """Longitude -> global column index. Accepts -180..180 or 0..360."""
        lon = np.mod(np.asarray(lon, dtype="float64") - self.lon0, 360.0)
        return np.rint(lon / self.resolution).astype("int32") % self.nlon

    def lat(self, gy):
        return self.lat0 + np.asarray(gy, dtype="float64") * self.resolution

    def lon(self, gx):
        return self.lon0 + np.asarray(gx, dtype="float64") * self.resolution


@dataclass(frozen=True)
class Subset:
    """The box that is actually ingested and rendered."""

    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    nlat: int
    nlon: int

    def gy_range(self, grid: GlobalGrid) -> tuple[int, int]:
        """Inclusive ``(first, last)`` global row index covered by the box."""
        return int(grid.gy(self.lat_min)), int(grid.gy(self.lat_max))

    def gx_range(self, grid: GlobalGrid) -> tuple[int, int]:
        """Inclusive ``(first, last)`` global column index covered by the box.

        Contiguous, not wrapping — which is the entire reason `domain.yml` puts
        `lon0` on the 0-360 convention. On the source's native -180..180 grid a
        Pacific box straddles the array edge and this would have to return two
        ranges, and every `WHERE gx BETWEEN` in the codebase would have to know.
        """
        return int(grid.gx(self.lon_min)), int(grid.gx(self.lon_max))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(west, south, east, north)`` for a Mapbox image source.

        Longitudes are returned **unwrapped** — a box reaching 290 is reported
        as 290, not -70. Mapbox accepts that and places the quad correctly
        across the antimeridian (verified in Chromium: `project([290,0])` and
        `project([-70,0])` return the same pixel). Wrapping the east edge into
        -180..180 would make west > east and collapse the image source.
        """
        return (self.lon_min, self.lat_min, self.lon_max, self.lat_max)

    def contains(self, lat: float, lon: float) -> bool:
        """Whether a point falls in the box. Accepts either lon convention."""
        half = 0.5 * (self.lon_max - self.lon_min) / max(self.nlon - 1, 1)
        if not (self.lat_min - half <= lat <= self.lat_max + half):
            return False
        # Bring the point onto the box's own 0-360 frame. A box crossing 360
        # (none today, but Box B ends at 289.975 and a wider one could) needs
        # the shifted comparison rather than a plain modulo.
        lon360 = (lon - self.lon_min) % 360.0 + self.lon_min
        return self.lon_min - half <= lon360 <= self.lon_max + half


@dataclass(frozen=True)
class Reference:
    """One citation, for a method this project did not invent.

    Kept structured rather than as a formatted string because the frontend
    renders the author/year as the link text and the full citation as its
    title — and because a bibliography written twice drifts.
    """

    authors: str
    year: int
    title: str
    source: str
    url: str


@dataclass(frozen=True)
class Baseline:
    """What a variable's value is measured *against*, said once.

    This exists because the dashboard carries **two different baselines** and
    nothing in the numbers themselves says so. `anom` is computed here, against
    a 1991-2020 daily mean; `mhw` arrives already categorised by NOAA against a
    1985-2012 mean **and 90th percentile**. The years differ, the window differs
    (1 day against 11), and the statistic differs — so a +1 degC anomaly and a
    Category 1 are not two views of one departure, and a reader who assumes they
    are will read the map wrong.

    The string used to be a constant in `api/modules/state.py`, another in
    `api/modules/timeseries.py`, and a literal in two TypeScript files and a Vue
    template. Declaring it here puts it where the rest of a variable's metadata
    already is and ships it through `/domain`, so the About dialog, the reading
    guide, the inline note and the API payloads cannot disagree about what the
    number is relative to.

    `statistic` is the load-bearing field. `mean` makes a departure; `p90` makes
    an EXCEEDANCE, which is why no anomaly value maps to a category: measured
    over this box, the P90-minus-mean departure a Cat 1 needs averages +1.02 degC
    but spans +0.60 at p5 to +1.62 at p95, so the threshold is a different number
    in every cell.
    """

    # "1991-2020". The years alone, for the many places that print just those.
    period: str
    # `mean` | `p90`. What the comparison is against, not merely over what years.
    statistic: str
    # One sentence naming the comparison, e.g. "the 1991-2020 daily mean".
    label: str
    # Who computed it. `here` means this project derived it from the source
    # archive; `noaa` means it arrived already applied and cannot be re-based.
    computed_by: str
    # Width in days of the window each day-of-year is averaged over. Ours is 1;
    # NOAA's MHW climatology uses 11, centred.
    window_days: int = 1
    # The longer explanation, shown in the inline note's popover.
    note: str | None = None
    # The method's own authors, where they are not the data provider.
    references: tuple[Reference, ...] = ()


@dataclass(frozen=True)
class Category:
    """One class of a categorical variable: its code, colour and name."""

    value: int
    color: str
    label: str


@dataclass(frozen=True)
class Preset:
    """A named display range for the colour-range control.

    A shortcut, not a mode: clicking one is exactly the range the user could
    have typed, so it goes through the same clamping and is remembered the same
    way. Narrowing to a band CLAMPS everything outside it to the end colours
    rather than hiding it — the band is emphasised, not isolated.

    The default range is deliberately NOT one of these. It is the variable's own
    `vmin`/`vmax`, and the control synthesises its chip from them, so there is
    one definition of it rather than two that can drift apart.
    """

    label: str
    vmin: float
    vmax: float


@dataclass(frozen=True)
class Variable:
    name: str
    long_name: str
    short_name: str
    units: str
    precision: int
    vmin: float
    vmax: float
    encoding: Encoding
    # How CoralTemp's own NetCDF packs the value. Meaningful for the ocean
    # variables, which read that file; a land layer reads CPC's float32 and has
    # nothing to declare here, so these are optional rather than filled with
    # numbers that describe no file.
    scale_factor: float = 1.0
    add_offset: float = 0.0
    fill_value: int | None = None
    # Which grid this variable's raster is built on: `global` (CoralTemp,
    # 0.05 degree) or `land` (NOAA CPC, 0.5 degree). Both render to the same
    # image bounds — see `render.bounds()` — so this decides which reader
    # `shared.buckets` uses, not where the image lands.
    grid: str = "global"
    # For a land layer, WHAT IT IS MADE OF, declared here rather than coded in
    # `shared.buckets`: the CPC variable it reads (`tmax`, `tmin`, `precip`)
    # and how a bucket is turned into the value drawn —
    #
    #   none        the mean over the bucket's days
    #   difference  the mean of (value - climatology) over those days
    #   log2_ratio  log2(mean(value) / mean(climatology)) over those days
    #
    # One declaration, so there is no second name -> source table to drift.
    source: str | None = None
    transform: str = "none"
    # The bucket lengths this layer exists at. The rainfall ratio is weekly and
    # monthly only: a daily rainfall anomaly is noise, where a daily temperature
    # anomaly (a heatwave day) is not.
    periods: tuple[str, ...] = ("daily", "weekly", "monthly")
    # `nearest` draws each source cell as a flat block. Land uses it because a
    # 0.5-degree cell is ~55 km and blending between centres would draw
    # gradients the gauge analysis never resolved. `categorical` implies it.
    resampling: str = "bilinear"
    # Below this climatological value a `log2_ratio` means nothing — one 0.5 mm
    # shower over a 0.05 mm/day normal reads as 1000% — so those cells draw the
    # sentinel grey instead. Measured: 7% of the box's land in January.
    min_normal: float | None = None
    # How the frontend should LABEL a value, where that differs from the number
    # itself. `log2_percent` is the rainfall ratio: stored and ranged as log2 so
    # a halving and a doubling sit equidistant from normal, printed as percent
    # (-1 -> 50%, 0 -> 100%, +1 -> 200%) so nobody has to read a logarithm.
    display: str | None = None
    # What the sentinel grey MEANS on this variable, for the legend. It is the
    # same colour for two different reasons: ocean with no climatology (the ice
    # fringe) and land too dry for a ratio.
    no_value_label: str | None = None
    # Exactly one of these two carries the palette. `colormap` names a
    # matplotlib colormap sampled server-side; `colors` lists the classes of a
    # categorical variable explicitly, because `mhw`'s five are NOAA's own and
    # are recognised on sight — sampling some sequential map at five points
    # would throw that away.
    colormap: str | None = None
    colors: tuple[Category, ...] = ()
    # What the *absence* of a value means on this variable, as a colour, where
    # that is a thing rather than a gap. Only `mhw` declares one: its image is
    # alpha 0 at land, ice AND heatwave-free ocean alike, so the ramp can never
    # be handed a code 0 to paint — the frontend draws this as a flat fill under
    # the raster instead. A continuous variable has no such class (its own gap is
    # `NO_CLIM_RGBA`, which the encoding *does* carry) and leaves this None.
    background_color: str | None = None
    # `anom` is computed as `sst - climatology(mmdd)` rather than stored.
    derived: bool = False
    # An ordinal class rather than a measurement. Three things follow, and each
    # of them is silently wrong if this is not honoured:
    #
    #   * the Mercator resample must be nearest, not bilinear — blending a Cat 2
    #     against a Cat 4 invents a Cat 3 along every edge;
    #   * the colour ramp must be a step, not an interpolation;
    #   * the displayed range is not user-adjustable, and the ramp is tabulated
    #     over the whole encoding range so entry k is exactly code k.
    categorical: bool = False
    # How far the *user* may move the displayed colour range, as opposed to
    # `vmin`/`vmax`, which are only where it opens. The frontend re-ranges the
    # map client-side — the images carry data, not colour — and this is what
    # bounds that control. Optional: absent, it falls back to `encoding` limits.
    #
    # It exists because the two are not the same question. `sst` packs into two
    # bytes at 0.01 degC and can therefore represent up to 650 degC, which is
    # arithmetic, not oceanography — a slider bounded by it would spend 95% of
    # its travel above the boiling point. `anom` has no such gap, so it can and
    # does simply omit this.
    limits: tuple[float, float] | None = None
    # Named shortcuts offered by the colour-range control. Same family as
    # `limits` — about the control, not about the data — and optional for the
    # same reason: `mhw` is categorical, its range is not the user's to move,
    # and the control does not exist for it. Validated against `range_limits()`
    # by the loader; see `Preset`.
    presets: tuple[Preset, ...] = ()
    # What this variable's value is measured against, where that is a
    # question at all. `sst` is an absolute temperature and declares none;
    # `anom` and `mhw` declare DIFFERENT ones, which is the whole reason
    # this is per-variable metadata rather than a single project constant.
    baseline: Baseline | None = None

    def range_limits(self) -> tuple[float, float]:
        """Bounds for a user-chosen display range, clipped to what is encodable."""
        low, high = self.encoding.value_range()
        # Never past the encoding: a range the image cannot represent would show
        # a span of colour that no pixel can ever land in.
        if self.limits is None:
            return low, high
        return max(self.limits[0], low), min(self.limits[1], high)

    def color_range(self) -> tuple[float, float]:
        """`raster-color-range`: the span the 256-entry ramp is tabulated over.

        A variable whose *codes* have to land one-per-ramp-entry must tabulate
        its whole encoding range. Two do, for different reasons: `anom`'s
        sentinel needs a slot of its own, and `mhw`'s categories need code k to
        be entry k — tabulate its five classes over 1..5 instead and code 2 lands
        at entry 63.75, where a Cat 2 can pick up Cat 1's colour.

        Everything else spends all 256 entries on the display range, which is
        where they are actually useful.
        """
        if self.encoding.sentinel is not None or self.categorical:
            return self.encoding.value_range()
        return self.vmin, self.vmax


@dataclass(frozen=True)
class Encoding:
    """How a variable's value is packed into the bytes of a rendered image.

    The images the map consumes carry **data, not colour** — Mapbox colours them
    with `raster-color`, which reads a scalar out of the RGB channels via
    `raster-color-mix` and looks it up in a ramp. So the packing here and the
    mix vector the frontend sends must agree exactly, and `mix()` is the one
    place that arithmetic is done: the API ships the result in `/domain` rather
    than the TypeScript re-deriving it.

    `channels` are listed **high byte first**, so ``[G, B]`` means
    ``value = (G * 256 + B) * scale + offset``.
    """

    channels: tuple[str, ...]
    scale: float
    offset: float
    # A reserved code, always 0, for a cell that is ocean but has no value on
    # this variable — the ice fringe with no climatology. Real data starts at 1.
    sentinel: int | None = None

    @property
    def depth(self) -> int:
        """Number of distinct codes, e.g. 256 for one channel, 65536 for two."""
        return 256 ** len(self.channels)

    @property
    def low_code(self) -> int:
        return 1 if self.sentinel is not None else 0

    def mix(self) -> list[float]:
        """`raster-color-mix`: ``[r, g, b, offset]``.

        Mapbox computes ``mix.r*src.r + mix.g*src.g + mix.b*src.b + mix.a`` with
        each channel arriving normalised to 0..1, so a channel holding byte
        ``n`` arrives as ``n/255`` and its weight carries the 255 back.
        """
        out = [0.0, 0.0, 0.0, self.offset]
        idx = {"R": 0, "G": 1, "B": 2}
        for i, channel in enumerate(self.channels):
            place = 256 ** (len(self.channels) - 1 - i)
            out[idx[channel.upper()]] = 255.0 * place * self.scale
        return out

    def value_range(self) -> tuple[float, float]:
        """The span this encoding can represent, sentinel code included."""
        return self.offset, self.offset + self.scale * (self.depth - 1)


@dataclass(frozen=True)
class Quantity:
    """A number a timeseries can report that is not a field on the map.

    Deliberately NOT a `Variable`, and the difference is the whole point: a
    variable is something `/image` can draw and the frontend's toggle is built
    from the list of them, so a quantity with no raster would appear there as a
    map layer that renders nothing. A quantity exists only once cells have been
    aggregated over an area — `mhw_extent` is the share of a box's ocean in a
    heatwave, which at a single cell would only ever be 0% or 100%.

    It carries just enough for a chart and a stat card to present it honestly:
    a name, a unit, a precision and a colour ramp. No `encoding` (nothing packs
    it into an image), no `presets` or `limits` (its range is the whole of what
    it can be), and no `categorical` — a quantity is continuous by construction.
    """

    name: str
    long_name: str
    short_name: str
    units: str
    precision: int
    vmin: float
    vmax: float
    colormap: str


@dataclass(frozen=True)
class Region:
    """A named area for the rollups: a lat/lon box, optionally cut by a polygon.

    `lat`/`lon` are always present and always the region's bounding box, because
    that box is what makes a region cheap: `ORDER BY (gy, gx, date)` turns it
    into a set of contiguous key ranges rather than a scan. For a polygon region
    the box is derived from the ring rather than written by hand, so the two
    cannot drift, and it is a PREFILTER — `region_cells` narrows it to the cells
    actually inside the zone. See `shared/mask.py`.
    """

    key: str
    label: str
    lat: tuple[float, float]
    lon: tuple[float, float]
    partial: bool = False
    # Outer rings, longitudes 0-360, or None for a plain box. No interior rings:
    # the islands inside a maritime zone are land, and land is excluded by
    # `sst_daily` holding ocean cells only, not by the geometry.
    polygon: tuple[tuple[tuple[float, float], ...], ...] | None = None

    @property
    def masked(self) -> bool:
        """Whether this region needs `region_cells` to mean what it says."""
        return self.polygon is not None

    def gy_range(self, grid: GlobalGrid) -> tuple[int, int]:
        """Inclusive `(first, last)` global row index of the bounding box."""
        return tuple(sorted(int(grid.gy(v)) for v in self.lat))

    def gx_range(self, grid: GlobalGrid) -> tuple[int, int]:
        """Inclusive `(first, last)` global column index of the bounding box.

        Contiguous, not wrapping, for the reason `Subset.gx_range` documents:
        `lon0` is on the 0-360 convention precisely so a Pacific box is one range.
        """
        return tuple(sorted(int(grid.gx(v)) for v in self.lon))


@functools.lru_cache(maxsize=1)
def _raw() -> dict:
    path = Path(os.environ.get("ENSO_DOMAIN_YML", _DOMAIN_YML))
    with path.open() as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=1)
def global_grid() -> GlobalGrid:
    return GlobalGrid(**_raw()["global"])


@functools.lru_cache(maxsize=1)
def subset() -> Subset:
    return Subset(**_raw()["subset"])


@functools.lru_cache(maxsize=1)
def land_grid() -> GlobalGrid:
    """The 0.5-degree CPC grid the land tables index.

    A `GlobalGrid` like `global_grid()` and deliberately the same type: the
    arithmetic is identical, only the resolution and origin differ. What differs
    is the *source* convention — CPC files are north-up and already 0-360, so the
    reader flips and does not roll. See `domain.yml`'s `land` block.
    """
    return GlobalGrid(**_raw()["land"])


def land_shape() -> tuple[int, int]:
    """`(nlat, nlon)` of every land array: the whole CPC grid, 360 x 720."""
    grid = land_grid()
    return grid.nlat, grid.nlon


@functools.lru_cache(maxsize=1)
def land_image() -> dict:
    """`{south, north}` of the land frames — see `domain.yml`'s `land_image`."""
    block = _raw()["land_image"]
    return {k: float(block[k]) for k in ("south", "north")}


def subset_shape(grid: GlobalGrid) -> tuple[int, int]:
    """``(nlat, nlon)`` the configured box covers on `grid`.

    Derived rather than declared, so the box has one definition. `subset`'s own
    `nlat`/`nlon` are the answer for `global_grid()` (2500 x 3800) and are kept
    there because they are load-bearing in the image bounds; this is what gives
    the same box's shape on any other grid — 250 x 380 on `land_grid()`.
    """
    gy0, gy1 = subset().gy_range(grid)
    gx0, gx1 = subset().gx_range(grid)
    return gy1 - gy0 + 1, gx1 - gx0 + 1


@functools.lru_cache(maxsize=1)
def variables() -> dict[str, Variable]:
    out = {}
    for name, cfg in _raw()["variables"].items():
        cfg = dict(cfg)
        enc = dict(cfg.pop("encoding"))
        enc["channels"] = tuple(enc["channels"])
        if cfg.get("limits") is not None:
            cfg["limits"] = tuple(cfg["limits"])
        if cfg.get("periods") is not None:
            cfg["periods"] = tuple(cfg["periods"])
        cfg["colors"] = tuple(Category(**c) for c in cfg.get("colors", ()))
        cfg["presets"] = tuple(Preset(**p) for p in cfg.get("presets", ()))
        if cfg.get("baseline") is not None:
            b = dict(cfg["baseline"])
            b["references"] = tuple(Reference(**r) for r in b.get("references", ()))
            cfg["baseline"] = Baseline(**b)
        out[name] = Variable(name=name, encoding=Encoding(**enc), **cfg)
        _check_presets(out[name])
        _check_baseline(out[name])
        _check_layer(out[name])
    return out


_GRIDS = ("global", "land")
_TRANSFORMS = ("none", "difference", "log2_ratio")
_LAND_SOURCES = ("tmax", "tmin", "precip")
_PERIODS = ("daily", "weekly", "monthly")


def _check_layer(v: Variable) -> None:
    """Reject a layer declaration `shared.buckets` could not honour.

    Each of these would otherwise fail far from here — a misspelt transform as
    an empty frame, a land layer with no source as a KeyError inside a render
    worker, a period typo as a variable that never renders at one period and
    never says why.
    """
    if v.grid not in _GRIDS:
        raise ValueError(f"{v.name}: grid {v.grid!r} is not one of {_GRIDS}")
    if v.transform not in _TRANSFORMS:
        raise ValueError(f"{v.name}: transform {v.transform!r} is not one of {_TRANSFORMS}")
    bad = [p for p in v.periods if p not in _PERIODS]
    if bad or not v.periods:
        raise ValueError(f"{v.name}: periods {v.periods} must be a non-empty subset of {_PERIODS}")
    if v.resampling not in ("nearest", "bilinear"):
        raise ValueError(f"{v.name}: resampling {v.resampling!r} is not nearest or bilinear")
    if v.grid == "land":
        if v.source not in _LAND_SOURCES:
            raise ValueError(
                f"{v.name}: a land layer needs a source in {_LAND_SOURCES}, got {v.source!r}"
            )
        if v.transform != "none" and v.baseline is None:
            # An anomaly with no declared baseline is a departure from nothing
            # the UI can name — and the climatology reader checks its file
            # against exactly this block.
            raise ValueError(f"{v.name}: transform {v.transform!r} needs a baseline block")
        if v.transform == "log2_ratio" and v.min_normal is None:
            raise ValueError(
                f"{v.name}: a log2_ratio needs min_normal, or every desert cell "
                "divides by a normal of ~0"
            )
        if v.transform == "log2_ratio" and v.encoding.sentinel is None:
            raise ValueError(
                f"{v.name}: a log2_ratio needs an encoding sentinel for its "
                "too-dry-for-a-ratio cells"
            )
    elif v.source is not None or v.transform != "none":
        raise ValueError(f"{v.name}: source/transform are land-only declarations")


def _check_presets(v: Variable) -> None:
    """Reject a declared preset the control could not honour.

    Raised rather than clipped, and rather than asserted (`assert` vanishes
    under `-O`). The frontend's `setScale` clamps every range it is given, so a
    preset past `range_limits()` has no loud symptom at all — it just lands
    somewhere other than where its label says, which is a chip that lies.
    """
    lo, hi = v.range_limits()
    for p in v.presets:
        if not lo <= p.vmin < p.vmax <= hi:
            raise ValueError(
                f"{v.name}: preset {p.label!r} spans {p.vmin}..{p.vmax}, "
                f"outside the adjustable range {lo}..{hi}"
            )


def _check_baseline(v: Variable) -> None:
    """Reject a baseline that claims something the rest of the code contradicts.

    Two rules, both cheap and both guarding a confusion that is invisible in the
    output. A `statistic` outside the known pair would be printed verbatim into
    the UI, where an unrecognised word reads as a typo rather than as a claim.
    And `computed_by: here` asserts that this project derived the comparison and
    could re-base it — true of `anom`, false of `mhw`, whose categories arrive
    already fixed against NOAA's own climatology and cannot be recomputed from
    anything in this database.
    """
    b = v.baseline
    if b is None:
        return
    if b.statistic not in ("mean", "p90"):
        raise ValueError(
            f"{v.name}: baseline statistic {b.statistic!r} is not 'mean' or 'p90'"
        )
    if b.computed_by not in ("here", "noaa"):
        raise ValueError(
            f"{v.name}: baseline computed_by {b.computed_by!r} is not 'here' or 'noaa'"
        )
    if b.window_days < 1 or b.window_days % 2 == 0:
        # A centred window has to be odd, or it has no centre day.
        raise ValueError(
            f"{v.name}: baseline window_days {b.window_days} is not a positive odd number"
        )


def variable(name: str) -> Variable:
    try:
        return variables()[name]
    except KeyError:
        raise KeyError(f"unknown variable {name!r}; known: {sorted(variables())}") from None


@functools.lru_cache(maxsize=1)
def quantities() -> dict[str, Quantity]:
    """Series-only quantities from `domain.yml`. Empty if the block is absent."""
    return {
        name: Quantity(name=name, **cfg)
        for name, cfg in (_raw().get("quantities") or {}).items()
    }


def quantity(name: str) -> Quantity:
    try:
        return quantities()[name]
    except KeyError:
        raise KeyError(f"unknown quantity {name!r}; known: {sorted(quantities())}") from None


_REGION_DIR = Path(__file__).with_name("regions")


def _load_polygon(filename: str) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Outer rings of a stored region polygon, longitudes on the 0-360 frame.

    Plain `json` rather than a geometry library: the file is read once per
    process and nothing here needs an operation on it beyond point-in-polygon,
    which `shared/mask.py` gets from matplotlib.
    """
    with (_REGION_DIR / filename).open() as fh:
        feature = json.load(fh)
    geom = feature["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    rings = tuple(
        tuple((float(x), float(y)) for x, y in poly[0])
        for poly in polys
        if len(poly[0]) >= 4
    )
    if not rings:
        raise ValueError(f"{filename}: no usable ring")
    return rings


@functools.lru_cache(maxsize=1)
def regions() -> dict[str, Region]:
    """The named regions, boxes and polygons alike.

    A polygon region declares `polygon:` and NO bounds: its box is derived from
    the ring here, so widening or replacing the geometry cannot leave a stale
    hand-written box behind quietly selecting the wrong key ranges. A box region
    declares bounds and no polygon. Declaring both is an error rather than a
    precedence rule — there would be no way to tell which one a stored row meant.
    """
    out = {}
    for key, cfg in _raw()["regions"].items():
        polygon = _load_polygon(cfg["polygon"]) if cfg.get("polygon") else None
        if polygon is not None and ("lat" in cfg or "lon" in cfg):
            raise ValueError(
                f"region {key!r}: declares both a polygon and explicit bounds; "
                "a polygon's box is derived from its ring"
            )
        if polygon is not None:
            xs = [x for ring in polygon for x, _ in ring]
            ys = [y for ring in polygon for _, y in ring]
            lat, lon = (min(ys), max(ys)), (min(xs), max(xs))
        else:
            lat, lon = tuple(cfg["lat"]), tuple(cfg["lon"])
        out[key] = Region(
            key=key,
            label=cfg["label"],
            lat=lat,
            lon=lon,
            partial=cfg.get("partial", False),
            polygon=polygon,
        )
    return out
