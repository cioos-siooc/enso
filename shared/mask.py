"""Turn a region polygon into the grid cells it covers.

A region in `domain.yml` is normally a lat/lon box, and a box needs nothing more
than `WHERE gy BETWEEN ... AND gx BETWEEN ...`. A few real-world regions are not
boxes — Canada's Pacific bioregions are a 200-nautical-mile arc with two
negotiated lateral boundaries — and for those the box is only a *prefilter*: the cells it selects
have to be narrowed again to the ones actually inside the polygon.

**That narrowing is materialised, not evaluated per query.** The rasterisation
here runs once per region into `region_cells`, and every aggregation then reads
that table. It is the same reasoning as `region_daily`: a named region is asked
for over and over, and re-deciding which of its cells are in the zone on each
request would put a point-in-polygon test in the path of a 113-billion-row scan.

**A cell is in the region when its CENTRE is inside the polygon.** No partial
weighting: a 0.05-degree cell is ~5.5 km, the zone is ~450,000 km2, and the
boundary cells are a rim one cell thick. Weighting them by their covered
fraction would be a second, subtler definition of "in the region" that the
`count()` in `region_daily.n_cells` could not describe.

Nothing here decides what is OCEAN. The mask is pure geometry and includes the
land inside the zone; `sst_daily` holds ocean cells only, so the join that reads
this table drops the land — which is also why the stored polygon carries no
interior rings for the islands. A hole is stored only for WATER a region does
not cover (`Region.holes`), and a cell inside one is out.
"""

from __future__ import annotations

import numpy as np

from .domain import GlobalGrid, Region


def cells_in(region: Region, grid: GlobalGrid) -> tuple[np.ndarray, np.ndarray]:
    """The `(gy, gx)` global cell indices whose centres fall inside `region`.

    Returns the box's own cells for a region with no polygon, so callers do not
    have to branch — though the box path has no reason to call this, since a box
    is expressible as a `BETWEEN` and a polygon is not.
    """
    gy0, gy1 = region.gy_range(grid)
    gy = np.arange(gy0, gy1 + 1)
    gx = region.gx_columns(grid)
    GY, GX = np.meshgrid(gy, gx, indexing="ij")

    if region.polygon is None:
        return GY.ravel(), GX.ravel()

    # Onto the ring's own frame. The grid answers 0-360; a ring crossing the
    # prime meridian is stored continuous (-98..12 for the North Atlantic), and a
    # cell at 5 degrees east must be tested as 5, not as 365 — or at 350 as -10.
    # `gx_columns` runs west to east, so these come out increasing — provided
    # the frame is centred on the box, not started at its west edge: the box's
    # first column is the cell NEAREST that edge and can sit half a cell west of
    # it, which a frame starting at the edge would wrap 360 degrees east.
    ref = 0.5 * (region.lon[0] + region.lon[1]) - 180.0
    lats = grid.lat(gy)
    lons = (grid.lon(gx) - ref) % 360.0 + ref

    inside = np.zeros(GY.shape, bool)
    holes = region.holes or ((),) * len(region.polygon)
    for ring, cut in zip(region.polygon, holes, strict=True):
        part = _scanline(np.asarray(ring, dtype="float64"), lats, lons)
        for hole in cut:
            part &= ~_scanline(np.asarray(hole, dtype="float64"), lats, lons)
        inside |= part

    return GY[inside], GX[inside]


def _scanline(ring: np.ndarray, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Even-odd fill of one ring at the given cell centres, `(len(lats), len(lons))`.

    A scanline rather than a point-in-polygon test per cell, because the cost of
    the latter is cells x vertices: 55,533 x 4,573 for `pacific_bioregions` was
    milliseconds, but the North Atlantic is ~3 M cells against tens of
    thousands of vertices. Here each row costs one pass over the edges, then a
    `searchsorted` over the crossings — the same centre-in-ring rule, decided
    per row instead of per cell. No geometry library, for the reason
    matplotlib was used before it: one predicate is not worth a wheel in the
    image.

    Half-open in latitude (`y1 <= y < y2`), so a vertex exactly on a row is
    counted once, not twice.
    """
    if not np.array_equal(ring[0], ring[-1]):
        ring = np.vstack([ring, ring[:1]])
    x1, y1 = ring[:-1, 0], ring[:-1, 1]
    x2, y2 = ring[1:, 0], ring[1:, 1]
    out = np.zeros((len(lats), len(lons)), bool)
    for i, y in enumerate(lats):
        crosses = (y1 <= y) != (y2 <= y)
        if not crosses.any():
            continue
        a, b, c, d = x1[crosses], y1[crosses], x2[crosses], y2[crosses]
        xs = np.sort(a + (y - b) * (c - a) / (d - b))
        # Pairs of crossings bound the inside: (x0, x1), (x2, x3), ...
        lo = np.searchsorted(lons, xs[0::2], side="right")
        hi = np.searchsorted(lons, xs[1::2], side="left")
        row = np.zeros(len(lons) + 1, np.int32)
        np.add.at(row, lo, 1)
        np.add.at(row, hi, -1)
        out[i] = np.cumsum(row[:-1]) > 0
    return out
