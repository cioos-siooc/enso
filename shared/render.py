"""Render a field array to a Web-Mercator WebP for the map.

The source grid is a regular 0.05-degree lat/lon field, which is linear in
longitude but *not* in Mercator y — so the rows are resampled onto an evenly
spaced Mercator axis here. Skipping that and handing Mapbox the raw array as an
image source stretches the field increasingly toward the pole.

**This module takes arrays, never a database client.** Images are rendered from
the NetCDF while it is still on disk (see `shared/fields.py`), which is what let
the `by_date` projection — 66% of storage — be dropped from the schema. Nothing
here reads ClickHouse.

**The images carry data, not colour.** `encode()` packs the value into the RGB
channels and the land mask into alpha; Mapbox applies the colour ramp itself
with `raster-color`. The reason is that the daily NetCDF is pruned to a
retention window, so once a bucket's file is gone the cached image is the only
surviving copy of that field — and a pre-coloured cache would have today's
colormap and today's vmin/vmax welded into it for good. Value-encoded, the
palette and the displayed range stay client-side settings.
"""

from __future__ import annotations

import datetime as dt
import functools
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image

from .domain import global_grid, land_grid, land_image, quantity, subset, variable
from .fields import global_ocean_mask, ocean_mask
from .periods import Period, start_of

log = logging.getLogger(__name__)

IMAGE_DIR = Path(os.environ.get("OISST_IMAGE_DIR", "/opt/data/images"))

MERCATOR_LAT_LIMIT = 85.0511287798066

# The Pacific box is 3800 source columns wide; 2048 keeps a whole bucket under
# ~200 KB while staying sharp at the zoom levels the map opens on.
DEFAULT_WIDTH = 2048

# Ocean that has SST but no climatology (the seasonal ice fringe). Drawn as a
# flat neutral grey on anomaly maps: transparent would read as land, and any
# colour on the diverging scale would read as a real anomaly near zero.
NO_CLIM_RGBA = (110, 110, 118, 255)


def _merc_y(lat_deg: np.ndarray | float) -> np.ndarray:
    lat = np.radians(np.clip(np.asarray(lat_deg, dtype="float64"), -MERCATOR_LAT_LIMIT, MERCATOR_LAT_LIMIT))
    return np.log(np.tan(np.pi / 4 + lat / 2))


def bounds() -> dict:
    """The rendered image's geographic extent, Mercator-clipped.

    Longitudes are **unwrapped** — the Pacific box's east edge is reported as
    290, not -70. Mapbox accepts that and places the quad correctly across the
    antimeridian; wrapping it would make west > east and collapse the source.
    """
    box = subset()
    half = 0.5 * (box.lon_max - box.lon_min) / max(box.nlon - 1, 1)
    return {
        "west": box.lon_min - half,
        "south": max(box.lat_min - half, -MERCATOR_LAT_LIMIT),
        "east": box.lon_max + half,
        "north": min(box.lat_max + half, MERCATOR_LAT_LIMIT),
    }


def to_mercator(
    field: np.ndarray, width: int = DEFAULT_WIDTH, nearest: bool = False
) -> np.ndarray:
    """Resample a lat-linear field onto an evenly spaced Mercator y axis.

    Returns a north-up array; the input's row 0 is the *southern* edge, as
    `shared.fields` guarantees.

    `nearest` samples instead of blending, and is required for a **categorical**
    field. Blending a Cat 2 against a Cat 4 produces a 3, which rounds to a real
    category the source never contained — a ring of spurious Cat 3 around every
    Cat 4 core. There is nothing between two classes to interpolate.

    The spacing comes from the field's own shape against the box's edges, so
    any field covering exactly the box resamples correctly. The land layers do
    not come through here: they are global, and `land_canvas()` places them.
    """
    extent = bounds()
    nrows, ncols = field.shape
    res = (extent["north"] - extent["south"]) / nrows
    lat_first = extent["south"] + 0.5 * res

    y_top, y_bot = _merc_y(extent["north"]), _merc_y(extent["south"])
    x_span = np.radians(extent["east"] - extent["west"])
    height = max(1, int(round(width * (y_top - y_bot) / x_span)))

    # Pixel centres, north to south.
    y = y_top + (np.arange(height) + 0.5) / height * (y_bot - y_top)
    lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)

    src = (lat - lat_first) / res
    if nearest:
        out = field[np.clip(np.rint(src).astype("int32"), 0, nrows - 1)]
    else:
        i0 = np.clip(np.floor(src).astype("int32"), 0, nrows - 1)
        i1 = np.clip(i0 + 1, 0, nrows - 1)
        w = (src - i0).astype("float32")[:, None]

        a, b = field[i0], field[i1]
        out = a * (1 - w) + b * w
        # Linear blending propagates NaN from either neighbour, which would erode
        # a pixel of ocean along every coastline; fall back to whichever side is
        # real.
        out = np.where(np.isnan(out), np.where(np.isnan(a), b, a), out)

    if width != ncols:
        # Longitude is linear in Mercator x, so this is a plain horizontal resize.
        src_x = (np.arange(width) + 0.5) / width * ncols - 0.5
        if nearest:
            out = out[:, np.clip(np.rint(src_x).astype("int32"), 0, ncols - 1)]
        else:
            j0 = np.clip(np.floor(src_x).astype("int32"), 0, ncols - 1)
            j1 = np.clip(j0 + 1, 0, ncols - 1)
            wx = (src_x - j0).astype("float32")[None, :]
            a, b = out[:, j0], out[:, j1]
            blended = a * (1 - wx) + b * wx
            out = np.where(np.isnan(blended), np.where(np.isnan(a), b, a), blended)

    return out


def _nearest_mercator_mask(
    mask: np.ndarray, width: int, nearest: bool = False
) -> np.ndarray:
    """Resample a boolean mask onto the same Mercator axes.

    Bilinear would produce fractional values along the ice edge with no sensible
    threshold; a mask is categorical, so it is thresholded at a half.

    `nearest` must match how the FIELD was resampled. A land layer draws its
    0.5-degree cells as blocks, and a mask resampled any other way would put the
    grey's edge a pixel off the block's — a sliver of transparency or of grey
    over a real value along every too-dry cell.
    """
    return to_mercator(mask.astype("float32"), width, nearest=nearest) > 0.5


@functools.lru_cache(maxsize=4)
def _fine_land(width: int) -> np.ndarray:
    """CoralTemp's land at 0.05 degree on the Mercator frame of `width` pixels.

    **The complement of the ocean rasters' own footprint, not a nearest-sampled
    mask.** The continuous ocean layers resample bilinearly with a NaN fallback
    that keeps whichever neighbour is real, so their coast sits one pixel
    landward of a nearest-sampled one. Cutting land with nearest left 11,987
    pixels (0.3% of the frame) drawn by BOTH rasters; cutting with the same
    bilinear footprint tiles them exactly. `mhw`'s nearest footprint is up to a
    pixel smaller, which leaves a one-pixel seam of basemap land — a coastline,
    not an overlap.

    Cached per width: identical for every land frame ever rendered.
    """
    ocean = np.where(ocean_mask(), 0.0, np.nan).astype("float32")
    return ~np.isfinite(to_mercator(ocean, width, nearest=False))


@dataclass(frozen=True)
class LandCanvas:
    """Where a land frame's pixels are, and which CPC cell each one shows.

    **The ocean frame's pixel grid, carried round the globe to -180..180.** Same
    pixel width in degrees, same Mercator row pitch, same south edge, so land
    and ocean pixels share their rows everywhere, and their columns exactly west
    of the dateline. East of it the columns are offset by a fixed fraction of a
    pixel, because 360 degrees is not a whole number of the ocean's pixels; see
    `_land_cut` for what that costs, and `domain.yml`'s `land_image` for why the
    frame stops at the dateline rather than following the ocean frame across it.
    """

    west: float
    east: float
    south: float
    north: float
    lat: np.ndarray  # pixel-centre latitude per row, north to south
    lon: np.ndarray  # pixel-centre longitude per column, -180..180
    px: float  # pixel width, degrees — the ocean frame's
    row0: int  # canvas row of the ocean frame's first row
    ocean_shape: tuple[int, int]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.lat), len(self.lon)

    @property
    def bounds(self) -> dict:
        return {"west": self.west, "south": self.south, "east": self.east, "north": self.north}


@functools.lru_cache(maxsize=4)
def land_canvas(width: int = DEFAULT_WIDTH) -> LandCanvas:
    """The land frame on the pixel grid of the ocean frame `width` pixels wide.

    `width` names the OCEAN frame's grid, which is also the image cache key: a
    `w2048` land frame is ~3,880 px wide, at the ocean frame's pixels per degree.
    """
    ext = bounds()
    px = (ext["east"] - ext["west"]) / width
    y_top, y_bot = _merc_y(ext["north"]), _merc_y(ext["south"])
    height = max(1, int(round(width * (y_top - y_bot) / np.radians(ext["east"] - ext["west"]))))
    dy = (y_top - y_bot) / height
    want = land_image()

    # Step west from the ocean frame's own west edge, so the columns west of
    # the dateline ARE the ocean frame's.
    west = ext["west"] - np.floor((ext["west"] + 180.0) / px + 1e-9) * px
    ncols = int(np.floor((180.0 - west) / px + 1e-9))
    rows_above = int(np.floor((_merc_y(want["north"]) - y_top) / dy + 1e-9))
    rows_below = int(np.floor((y_bot - _merc_y(want["south"])) / dy + 1e-9))
    y_north = y_top + rows_above * dy
    y_south = y_bot - rows_below * dy
    nrows = rows_above + height + rows_below

    to_lat = lambda y: np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)  # noqa: E731
    # Pixel centres, exactly as `to_mercator` places the ocean frame's.
    y = y_north - (np.arange(nrows) + 0.5) * dy
    return LandCanvas(
        west=float(west),
        east=float(west + ncols * px),
        south=float(to_lat(y_south)),
        north=float(to_lat(y_north)),
        lat=to_lat(y),
        lon=west + (np.arange(ncols) + 0.5) * px,
        px=float(px),
        row0=rows_above,
        ocean_shape=(height, width),
    )


def land_bounds(width: int = DEFAULT_WIDTH) -> dict:
    """The land frame's corners, for `/domain`'s `landImageBounds`."""
    return land_canvas(width).bounds


def _land_index(width: int) -> tuple[np.ndarray, np.ndarray]:
    """`(rows, cols)` into the global CPC grid for each canvas pixel (nearest)."""
    c, grid = land_canvas(width), land_grid()
    return (
        np.clip(grid.gy(c.lat), 0, grid.nlat - 1),
        grid.gx(c.lon),
    )


def _ocean_columns(width: int) -> tuple[np.ndarray, np.ndarray]:
    """For each canvas column, the ocean-frame columns under its two edges.

    Both are -1 where that edge is outside the ocean frame. West of the
    dateline the two are the same column (the grids coincide); east of it they
    are neighbours, since the offset is under a pixel.
    """
    c = land_canvas(width)
    west = bounds()["west"]
    left = c.lon - 0.5 * c.px
    edges = []
    # A hair inside each edge, so a shared boundary is not counted as overlap.
    for x in (left + 1e-6 * c.px, left + c.px - 1e-6 * c.px):
        j = np.floor((np.mod(x - west, 360.0)) / c.px).astype("int64")
        edges.append(np.where(j < width, j, -1))
    return edges[0], edges[1]


@functools.lru_cache(maxsize=4)
def _land_cut(width: int) -> np.ndarray:
    """Where a land pixel may be opaque.

    Everywhere, CoralTemp's land at 0.05 degree, sampled at the pixel centre.
    Inside the ocean frame it is also **clear of the ocean rasters' footprint**
    (`_fine_land`'s complement): west of the dateline that is one ocean pixel,
    and the cut tiles the two rasters exactly; east of it a land pixel straddles
    two ocean pixels and must be clear of both, which is what leaves the
    sub-pixel strip of basemap there rather than an overlap.
    """
    c, grid = land_canvas(width), global_grid()
    gy = np.clip(grid.gy(c.lat), 0, grid.nlat - 1)
    land = ~global_ocean_mask()[np.ix_(gy, grid.gx(c.lon))]

    h, _ = c.ocean_shape
    clear = _fine_land(width)  # True where no ocean raster draws
    rows = slice(c.row0, c.row0 + h)
    for cols in _ocean_columns(width):
        inside = cols >= 0
        land[rows, inside] &= clear[:, cols[inside]]
    return land


def land_to_canvas(field: np.ndarray, width: int = DEFAULT_WIDTH) -> np.ndarray:
    """A global `(360, 720)` land array on the land frame, nearest (0.5-degree blocks)."""
    rows, cols = _land_index(width)
    return field[np.ix_(rows, cols)]


def colorize(
    field: np.ndarray,
    variable_name: str = "sst",
    no_clim: np.ndarray | None = None,
) -> Image.Image:
    """Map values to RGBA using the variable's colormap.

    `sst` is sequential and `anom` diverging — see domain.yml for why that
    distinction is not cosmetic. `no_clim`, when given, paints ocean cells that
    have no climatology in a flat grey after colouring.

    **Not on the serving path.** `encode()` ships data and the browser colours
    it; this exists so a field can be eyeballed or diffed against a reference
    without a browser, and to build the legend stops below.
    """
    var = variable(variable_name)
    if var.colors:
        # A categorical variable has no colormap to normalise against: its
        # classes are integers, so the boundaries go between them.
        cmap = matplotlib.colors.ListedColormap([c.color for c in var.colors])
        cmap = cmap.with_extremes(bad=(0, 0, 0, 0))
        norm = matplotlib.colors.BoundaryNorm(
            [c.value - 0.5 for c in var.colors] + [var.colors[-1].value + 0.5],
            cmap.N,
            clip=True,
        )
    else:
        cmap = matplotlib.colormaps[var.colormap].with_extremes(bad=(0, 0, 0, 0))
        norm = matplotlib.colors.Normalize(vmin=var.vmin, vmax=var.vmax, clip=True)
    rgba = cmap(norm(np.ma.masked_invalid(field)), bytes=True)
    if no_clim is not None:
        rgba[no_clim] = NO_CLIM_RGBA
    return Image.fromarray(rgba, mode="RGBA")


def _neighbour_sum(a: np.ndarray) -> np.ndarray:
    """Sum of each cell's four neighbours, wrapping at the edges.

    The same result as summing four `np.roll`s, in place of four full copies:
    this is most of `_bleed`'s cost, and measured 2x faster with identical output.
    """
    out = np.zeros_like(a)
    out[1:] += a[:-1]
    out[:1] += a[-1:]
    out[:-1] += a[1:]
    out[-1:] += a[:1]
    out[:, 1:] += a[:, :-1]
    out[:, :1] += a[:, -1:]
    out[:, :-1] += a[:, 1:]
    out[:, -1:] += a[:, :1]
    return out


def _bleed(codes: np.ndarray, known: np.ndarray, passes: int = 8) -> np.ndarray:
    """Fill unknown cells (land) with nearby known values.

    Land cannot be left at 0. Mapbox filters the texture, so a coastal texel
    that blends an ocean value against a land 0 decodes to the bottom of the
    scale — a wrong-coloured fringe along every coastline. Land is cut by the
    **alpha** channel, which is exact; the value channels just need to carry
    something harmless underneath it.

    Bleeding operates on the integer code, never on the packed channels: with a
    two-channel value, averaging the low byte across a 255->0 wrap would land
    the result a full 256 counts away. int32 holds four neighbours' worth of the
    largest two-channel code (4 x 65535).
    """
    if known.all():
        return codes
    if not known.any():
        # Nothing to bleed from: a frame with no value anywhere (every pixel
        # transparent). The fill is invisible under alpha 0, so zeros will do.
        return np.zeros_like(codes)
    codes = np.where(known, codes, int(np.median(codes[known]))).astype("int32")
    for _ in range(passes):
        if known.all():
            break
        acc = _neighbour_sum(np.where(known, codes, 0))
        cnt = _neighbour_sum(known.astype("int32"))
        grow = (~known) & (cnt > 0)
        codes = np.where(grow, acc // np.maximum(cnt, 1), codes)
        known = known | grow
    return codes.astype("int64")


def encode(
    field: np.ndarray,
    width: int = DEFAULT_WIDTH,
    variable_name: str = "sst",
    no_clim: np.ndarray | None = None,
) -> bytes:
    """Value-encoded WebP bytes for a field array on the subset grid.

    The image carries the **data**, not a picture of it: the value goes into the
    RGB channels per the variable's `encoding`, land goes into alpha, and Mapbox
    applies the colour ramp itself via `raster-color`. That is what keeps the
    palette and the displayed range client-side settings — which matters here
    because the NetCDF archive is pruned to a retention window, so a re-render
    of history is not available to fall back on. A pre-coloured cache would weld
    today's colour choices into the only surviving copy of the data.

    **Lossless, necessarily.** Lossy WebP is YUV 4:2:0 — it subsamples chroma
    and quantises, which is harmless for a picture and ruinous for packed data.
    Measured on this field at q90: mean error 0.074 degC but a maximum of
    1.613 degC, i.e. visible blotches. Lossless costs 2.3-2.7x the bytes and
    actually *decodes* slightly cheaper (no inverse DCT, no YUV conversion).
    """
    var = variable(variable_name)
    enc = var.encoding
    # Nearest for a class (blending two categories invents a third) and for any
    # layer that declares it — the land layers, whose 0.5-degree cells should
    # draw as the blocks they are rather than as gradients never measured.
    nearest = var.categorical or var.resampling == "nearest"
    land = var.grid == "land"
    merc = land_to_canvas(field, width) if land else to_mercator(field, width, nearest=nearest)
    has_value = np.isfinite(merc)

    # Ocean without a value on this variable — the ice fringe, which has SST but
    # no climatology. Opaque like any other ocean cell, but flagged so the ramp
    # can paint it a flat grey; transparent would read as land and a scale
    # colour would read as a real anomaly near zero.
    if no_clim is None:
        sentinel_cells = np.zeros_like(has_value)
    elif land:
        sentinel_cells = land_to_canvas(no_clim, width)
    else:
        sentinel_cells = _nearest_mercator_mask(no_clim, width, nearest=nearest)
    ocean = has_value | sentinel_cells
    if land:
        # Cut to CoralTemp's 0.05-degree coastline. Without this a 0.5-degree
        # land block overhangs the sea along every coast, and the land raster
        # sits above the basemap's land fill — see `fields.ocean_mask`.
        ocean &= _land_cut(width)

    # CLAMP, never wrap. An out-of-range value that overflows the code would
    # reappear at the opposite end of the scale — a record-warm cell drawn as
    # the coldest colour on the map.
    codes = np.round((np.nan_to_num(merc, nan=0.0) - enc.offset) / enc.scale)
    codes = np.clip(codes, enc.low_code, enc.depth - 1).astype("int64")
    if enc.sentinel is not None:
        codes = np.where(sentinel_cells, enc.sentinel, codes)
    # Land layers skip the bleed passes and take the median fill alone. They
    # are always drawn `raster-resampling: nearest`, so the value under a
    # transparent texel never reaches the screen, and the 8 passes were ~1/3 of
    # a land frame's encode (the unknown area is the whole ocean).
    codes = _bleed(codes, ocean, passes=0 if land else 8)

    rgba = np.zeros((*merc.shape, 4), dtype="uint8")
    index = {"R": 0, "G": 1, "B": 2}
    n = len(enc.channels)
    for i, channel in enumerate(enc.channels):
        shift = 8 * (n - 1 - i)
        rgba[..., index[channel.upper()]] = ((codes >> shift) & 0xFF).astype("uint8")
    if n == 1:
        # Mirror the single channel across RGB: libwebp's subtract-green
        # transform then codes two of the three planes as zero, for free.
        rgba[..., 1] = rgba[..., 2] = rgba[..., 0]
    rgba[..., 3] = np.where(ocean, 255, 0).astype("uint8")

    buffer = io.BytesIO()
    # `method=4`: 6 buys under 2% for ~2.5x the encode time. Land frames are
    # ~3x the pixels and mostly transparent, and measured the same size (within
    # 2%) at `method=1` and lossless effort (`quality`) 25 in two thirds of the
    # time — which over ~92k frames is hours.
    method, effort = (1, 25) if land else (4, 80)
    Image.fromarray(rgba, mode="RGBA").save(
        buffer, format="WEBP", lossless=True, method=method, quality=effort
    )
    return buffer.getvalue()


def cache_path(
    date: dt.date,
    width: int = DEFAULT_WIDTH,
    period: Period = "daily",
    variable_name: str = "sst",
    image_dir: Path | None = None,
) -> Path:
    """Cache file for a bucket, keyed by (variable, period, bucket start, width).

    Keyed by the bucket's *first* day, so every date inside a week or month
    resolves to the same render.
    """
    bucket = start_of(date, period)
    return (
        (image_dir or IMAGE_DIR)
        / variable_name
        / period
        / f"{bucket:%Y}"
        / f"{bucket:%Y-%m-%d}_w{width}.webp"
    )


def write_cache(path: Path, payload: bytes) -> None:
    """Write a rendered bucket to its cache file, tolerating a bad volume."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Via a temp file so a half-written image is never served: the API may
        # be answering requests out of this same directory.
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(payload)
        tmp.replace(path)
    except OSError:
        log.warning("could not cache %s", path, exc_info=True)


def colormap_stops(variable_name: str = "sst", n: int = 33) -> list[dict]:
    """Legend stops: evenly spaced values with their hex colours.

    For a **categorical** variable the stops are the classes themselves — one per
    category, at its own integer value, in NOAA's own colours. They are still
    evenly spaced, which is what lets the frontend re-label them onto a range the
    same way it does a sampled colormap's; for a categorical that re-labelling is
    the identity, because the range is not adjustable.
    """
    var = variable(variable_name)
    if var.colors:
        return [
            {"value": float(c.value), "color": c.color, "label": c.label}
            for c in var.colors
        ]
    return _sampled_stops(var.colormap, var.vmin, var.vmax, n)


def quantity_stops(name: str, n: int = 33) -> list[dict]:
    """The same, for a series-only `quantities` entry.

    A quantity has no categories and no adjustable range, so this is always the
    sampled path. It exists so the colormap stays evaluated in exactly one place
    — matplotlib, server-side — for a region's marine-heatwave extent as much as
    for a map variable.
    """
    q = quantity(name)
    return _sampled_stops(q.colormap, q.vmin, q.vmax, n)


def _sampled_stops(colormap: str, vmin: float, vmax: float, n: int) -> list[dict]:
    """`n` evenly spaced values across `vmin..vmax`, with their hex colours.

    Evenly spaced is load-bearing, not incidental: it is what lets the frontend
    re-label the same colours onto a narrower display range by index alone
    (`stopsFor`), without evaluating a colormap of its own.
    """
    cmap = matplotlib.colormaps[colormap]
    values = np.linspace(vmin, vmax, n)
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
    return [
        {"value": round(float(v), 3), "color": matplotlib.colors.to_hex(cmap(norm(v)))}
        for v in values
    ]
