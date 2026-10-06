"""The orientation rules and the MHW category guards, on synthetic arrays.

Every failure these guard against produces a believable map rather than an
error, which is why they are pinned here rather than trusted.
"""

import datetime as dt

import numpy as np
import pytest

from shared import domain, fields


@pytest.fixture(scope="module")
def grid():
    return domain.global_grid()


@pytest.fixture(scope="module")
def box_index(grid):
    box = domain.subset()
    gy0, _ = box.gy_range(grid)
    gx0, _ = box.gx_range(grid)
    return gy0, gx0, box


def test_longitude_roll(grid, box_index):
    """A file column c lands at project gx (c + 3600) % 7200."""
    gy0, gx0, box = box_index
    raw = np.broadcast_to(np.arange(grid.nlon, dtype="int16"), (grid.nlat, grid.nlon))
    out = fields._to_project_frame(raw, flip_lat=False)
    expected_file_col = (gx0 + np.arange(box.nlon) - grid.nlon // 2) % grid.nlon
    assert np.array_equal(out[0], expected_file_col)


@pytest.mark.parametrize("flip", [False, True])
def test_latitude_orientation(grid, box_index, flip):
    """Row 0 of the output is the box's southern edge, flipped input or not."""
    gy0, _, box = box_index
    rows = np.arange(grid.nlat, dtype="int16")
    raw = np.broadcast_to((rows[::-1] if flip else rows)[:, None], (grid.nlat, grid.nlon))
    out = fields._to_project_frame(raw, flip_lat=flip)
    assert np.array_equal(out[:, 0], gy0 + np.arange(box.nlat))


def test_wrong_grid_shape_raises():
    with pytest.raises(ValueError):
        fields._to_project_frame(np.zeros((10, 10), "int16"), flip_lat=False)


def test_mhw_valid_mask_is_bounded_at_both_ends():
    """251 is the post-2024-07-01 land and ice fill, and it is positive."""
    before = np.array([-127, -1, 0, 1, 2, 3, 4, 5], dtype="int8")
    after = np.array([251, 0, 1, 5, 6], dtype="uint8")
    assert fields.mhw_valid_mask(before).tolist() == [False, False, False, True, True, True, True, True]
    assert fields.mhw_valid_mask(after).tolist() == [False, False, True, True, False]
    assert np.isnan(fields.as_category(after)[[0, 1, 4]]).all()


def test_leap_day_land_comes_from_coraltemp(monkeypatch, tmp_path, grid, box_index):
    """A file with no land gets land from the same date's SST file."""
    _, _, box = box_index
    fill = domain.variable("sst").fill_value
    sst_file = tmp_path / "coraltemp.nc"
    sst_file.touch()

    sst = np.full((grid.nlat, grid.nlon), 2000, dtype="int16")
    sst[:, : grid.nlon // 4] = fill
    mhw = np.full((grid.nlat, grid.nlon), 5, dtype="int8")

    def fake_read_raw(path, *, squeeze_time, var_name=fields.VARIABLE_NAME):
        if var_name == fields.MHW_MASK_NAME:
            return np.zeros((grid.nlat, grid.nlon), "int8")
        return mhw if var_name == fields.MHW_VARIABLE_NAME else sst

    monkeypatch.setattr(fields, "_read_raw", fake_read_raw)
    monkeypatch.setattr(fields, "daily_path", lambda date, nc_dir=None: sst_file)

    out = fields.read_mhw_raw(dt.date(2024, 2, 29))
    land = ~fields.valid_mask(fields._to_project_frame(sst, flip_lat=False))
    assert land.any() and (~land).any()
    assert (out[land] == fields.MHW_LAND_CODE).all()
    assert (out[~land] == 5).all()
    assert not fields.mhw_valid_mask(out[land]).any()


def test_leap_day_without_coraltemp_raises(monkeypatch, tmp_path, grid):
    def fake_read_raw(path, *, squeeze_time, var_name=fields.VARIABLE_NAME):
        return np.full((grid.nlat, grid.nlon), 5 if var_name == fields.MHW_VARIABLE_NAME else 0, "int8")

    monkeypatch.setattr(fields, "_read_raw", fake_read_raw)
    monkeypatch.setattr(fields, "daily_path", lambda date, nc_dir=None: tmp_path / "missing.nc")
    with pytest.raises(FileNotFoundError):
        fields.read_mhw_raw(dt.date(2024, 2, 29))


def test_check_orientation_catches_a_flip():
    fill = domain.variable("sst").fill_value
    daily = np.full((4, 4), 1000, dtype="int16")
    daily[:2] = fill                    # southern half is land
    clim = np.full((4, 4), 1000, dtype="int16")
    clim[2:] = fill                     # the climatology put it in the north
    with pytest.raises(ValueError, match="latitude flip"):
        fields.check_orientation(daily, clim)

    clim_ok = daily.copy()
    clim_ok[3, 3] = fill                # a strict subset is fine
    fields.check_orientation(daily, clim_ok)
