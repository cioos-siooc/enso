"""A cell is in a polygon region when its centre is."""

from shared import domain
from shared.domain import Region
from shared.mask import cells_in


def test_cell_centre_rule():
    grid = domain.global_grid()
    ring = ((200.0, 0.0), (200.1, 0.0), (200.1, 0.1), (200.0, 0.1), (200.0, 0.0))
    region = Region(key="t", label="t", lat=(0.0, 0.1), lon=(200.0, 200.1), polygon=(ring,))

    gy, gx = cells_in(region, grid)
    lat, lon = grid.lat(gy), grid.lon(gx)
    assert len(gy) == 4
    assert ((lat > 0.0) & (lat < 0.1) & (lon > 200.0) & (lon < 200.1)).all()


def test_box_region_returns_its_box():
    grid = domain.global_grid()
    region = Region(key="t", label="t", lat=(0.0, 1.0), lon=(200.0, 201.0))
    gy, gx = cells_in(region, grid)
    (gy0, gy1), (gx0, gx1) = region.gy_range(grid), region.gx_range(grid)
    assert len(gy) == (gy1 - gy0 + 1) * (gx1 - gx0 + 1)


def test_stored_polygon_is_much_smaller_than_its_box():
    """`pacific_bioregions` covers well under its bounding box (26,222 of 55,533)."""
    grid = domain.global_grid()
    region = domain.regions()["pacific_bioregions"]
    gy, _ = cells_in(region, grid)
    (gy0, gy1), (gx0, gx1) = region.gy_range(grid), region.gx_range(grid)
    box_cells = (gy1 - gy0 + 1) * (gx1 - gx0 + 1)
    assert 0.3 < len(gy) / box_cells < 0.7


def test_wrapping_polygon_keeps_both_sides_of_the_meridian():
    """A ring across 0 written continuous (-1..1) selects cells either side."""
    grid = domain.global_grid()
    ring = ((-1.0, 0.0), (1.0, 0.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, 0.0))
    region = Region(key="t", label="t", lat=(0.0, 1.0), lon=(-1.0, 1.0), polygon=(ring,))
    gy, gx = cells_in(region, grid)
    lon = grid.lon(gx)
    assert len(gy) == 20 * 40
    assert ((lon < 1.0) | (lon > 359.0)).all()
    assert (lon < 1.0).sum() == (lon > 359.0).sum()


def test_cell_half_a_step_west_of_the_ring_is_not_wrapped_in():
    """The box's first column can sit just west of the ring's west edge.

    Shifting longitudes onto a frame STARTING at that edge sent this cell 360
    degrees east, past the ring's far side, where the scanline counted it.
    """
    grid = domain.global_grid()
    ring = ((200.04, 0.0), (200.3, 0.0), (200.3, 0.3), (200.04, 0.3), (200.04, 0.0))
    region = Region(key="t", label="t", lat=(0.0, 0.3), lon=(200.04, 200.3), polygon=(ring,))
    _, gx = cells_in(region, grid)
    assert (grid.lon(gx) > 200.04).all()


def test_hole_is_cut_out():
    """A stored interior ring is water the region does not cover."""
    grid = domain.global_grid()
    ring = ((200.0, 0.0), (200.3, 0.0), (200.3, 0.3), (200.0, 0.3), (200.0, 0.0))
    hole = ((200.1, 0.1), (200.2, 0.1), (200.2, 0.2), (200.1, 0.2), (200.1, 0.1))
    whole = Region(key="t", label="t", lat=(0.0, 0.3), lon=(200.0, 200.3), polygon=(ring,))
    cut = Region(key="t", label="t", lat=(0.0, 0.3), lon=(200.0, 200.3), polygon=(ring,),
                 holes=((hole,),))
    gy, gx = cells_in(cut, grid)
    lat, lon = grid.lat(gy), grid.lon(gx)
    assert len(cells_in(whole, grid)[0]) - len(gy) == 4
    assert not ((lat > 0.1) & (lat < 0.2) & (lon > 200.1) & (lon < 200.2)).any()


def test_saint_pierre_et_miquelon_is_not_canadian_water():
    """It is a hole in the Newfoundland-Labrador Shelves, not an island to drop."""
    grid = domain.global_grid()
    spm = (grid.gy(46.3), grid.gx(-56.4 % 360))
    gy, gx = cells_in(domain.regions()["nl_shelves"], grid)
    assert spm not in set(zip(gy.tolist(), gx.tolist()))
