"""`domain.yml` validation, and the grid arithmetic every cell identity rests on."""

import pytest
import yaml

from shared import domain

from conftest import ROOT


def _clear():
    for fn in (domain._raw, domain.global_grid, domain.subset, domain.variables,
               domain.quantities, domain.regions):
        fn.cache_clear()


@pytest.fixture
def edited_domain(tmp_path, monkeypatch):
    """Load a copy of the real `domain.yml` with an edit applied."""
    def load(edit):
        raw = yaml.safe_load((ROOT / "shared/domain.yml").read_text())
        edit(raw)
        path = tmp_path / "domain.yml"
        path.write_text(yaml.safe_dump(raw))
        monkeypatch.setenv("ENSO_DOMAIN_YML", str(path))
        _clear()
        return domain
    yield load
    monkeypatch.delenv("ENSO_DOMAIN_YML", raising=False)
    _clear()


def test_real_domain_loads():
    _clear()
    assert {"sst", "anom", "mhw"} <= set(domain.variables())
    assert "pacific_bioregions" in domain.regions()


def test_preset_outside_limits_raises(edited_domain):
    def edit(raw):
        raw["variables"]["sst"]["presets"].append({"label": "Boiling", "vmin": 20.0, "vmax": 120.0})
    with pytest.raises(ValueError, match="Boiling"):
        edited_domain(edit).variables()


@pytest.mark.parametrize("field, value", [
    ("statistic", "median"),
    ("computed_by", "someone"),
    ("window_days", 10),
])
def test_bad_baseline_raises(edited_domain, field, value):
    def edit(raw):
        raw["variables"]["anom"]["baseline"][field] = value
    with pytest.raises(ValueError, match="anom"):
        edited_domain(edit).variables()


def test_polygon_region_with_bounds_raises(edited_domain):
    def edit(raw):
        raw["regions"]["pacific_bioregions"]["lat"] = [40, 60]
    with pytest.raises(ValueError, match="both a polygon"):
        edited_domain(edit).regions()


def test_antimeridian_cells_coincide():
    """180.025E and -179.975E are one cell; 179.975E is its western neighbour."""
    grid = domain.global_grid()
    assert grid.gx(180.025) == grid.gx(-179.975)
    assert grid.gx(179.975) == grid.gx(180.025) - 1


def test_grid_round_trip():
    grid = domain.global_grid()
    for lat, lon in [(0.025, 200.025), (-59.975, 100.025), (64.975, 289.975)]:
        assert grid.lat(grid.gy(lat)) == pytest.approx(lat)
        assert grid.lon(grid.gx(lon)) == pytest.approx(lon)


def test_subset_shape_matches_declared():
    grid, box = domain.global_grid(), domain.subset()
    gy0, gy1 = box.gy_range(grid)
    gx0, gx1 = box.gx_range(grid)
    assert (gy1 - gy0 + 1, gx1 - gx0 + 1) == (box.nlat, box.nlon)


def test_mix_decodes_packed_bytes():
    """`raster-color-mix` applied to normalised bytes recovers the value."""
    enc = domain.variable("sst").encoding
    code = 3456
    hi, lo = code >> 8, code & 0xFF
    r, g, b, offset = enc.mix()
    idx = {"R": 0, "G": 1, "B": 2}
    channels = [0.0, 0.0, 0.0]
    channels[idx[enc.channels[0].upper()]] = hi / 255
    channels[idx[enc.channels[1].upper()]] = lo / 255
    value = r * channels[0] + g * channels[1] + b * channels[2] + offset
    assert value == pytest.approx(code * enc.scale + enc.offset)
