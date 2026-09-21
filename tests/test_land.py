"""The land grid, the land reader's two conventions, and the storage scales.

The CPC source gets both orientation rules wrong in the opposite direction to
CoralTemp — it is north-up (so it must be flipped) and already 0-360 (so it must
NOT be rolled) — and neither mistake produces an error, only a plausible map.
These pin both, plus the two quantisation choices, on synthetic arrays; no
NetCDF is read, matching `test_fields.py`.
"""

import datetime as dt

import numpy as np
import pytest

from shared import domain, fields


@pytest.fixture(scope="module")
def grid():
    return domain.land_grid()


# --- The grid ----------------------------------------------------------------


def test_land_grid_is_south_up_and_0_360(grid):
    """`domain.yml`'s land block matches CPC's grid, on the project's axes."""
    assert (grid.resolution, grid.nlat, grid.nlon) == (0.5, 360, 720)
    # South-up like `global`, though the FILES are north-up. That gap is the
    # flip, and it is the reader's job, not the grid's.
    assert grid.lat(0) == pytest.approx(-89.75)
    assert grid.lat(grid.nlat - 1) == pytest.approx(89.75)
    assert grid.lon(0) == pytest.approx(0.25)


def test_land_arrays_are_the_whole_grid():
    """Land is global: every array is the full CPC grid, not the ocean's box."""
    assert domain.land_shape() == (360, 720)
    assert domain.land_image() == {"south": -60.0, "north": 85.0}


def test_box_resolves_on_the_land_grid(grid):
    """The ocean's box, measured on the 0.5-degree grid: 250 x 380."""
    box = domain.subset()
    assert box.gy_range(grid) == (60, 309)
    assert box.gx_range(grid) == (200, 579)
    assert domain.subset_shape(grid) == (250, 380)
    # The box's own corners, so a wrong origin cannot pass by counting cells.
    assert grid.lat(60) == pytest.approx(-59.75)
    assert grid.lat(309) == pytest.approx(64.75)
    assert grid.lon(200) == pytest.approx(100.25)
    assert grid.lon(579) == pytest.approx(289.75)


def test_land_subset_shape_differs_from_the_ocean_one():
    """Same box, two grids, and `subset_shape` is what keeps them apart.

    `subset.nlat/nlon` in `domain.yml` are the OCEAN grid's answer. A land reader
    asserting against them would reject every file it ever saw.
    """
    assert domain.subset_shape(domain.global_grid()) == (2500, 3800)
    assert domain.subset_shape(domain.land_grid()) == (250, 380)


# --- The reader's two conventions --------------------------------------------


def _fake_dataset(lat, lon, values, dates):
    """A stand-in for `netCDF4.Dataset` as a context manager.

    Enough of the interface for `read_land_year`: `variables` with `lat`, `lon`,
    `time` (carrying `units`) and the data variable, which must accept
    `set_auto_maskandscale` and a 3-tuple slice.
    """

    class Var:
        def __init__(self, data, **attrs):
            self._data = data
            self.__dict__.update(attrs)

        def set_auto_maskandscale(self, flag):
            pass

        def __getitem__(self, key):
            return self._data[key]

    class Dataset:
        # A real `netCDF4.Dataset` is used as a context manager, and the dunder
        # lookup is on the TYPE — so this cannot be a SimpleNamespace with
        # attributes attached.
        def __init__(self, variables):
            self.variables = variables

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    epoch = dt.datetime(1900, 1, 1)
    hours = [
        (dt.datetime(d.year, d.month, d.day) - epoch).total_seconds() / 3600.0
        for d in dates
    ]
    return Dataset({
        "lat": Var(np.asarray(lat, dtype="float32")),
        "lon": Var(np.asarray(lon, dtype="float32")),
        "time": Var(np.asarray(hours, dtype="float64"),
                    units="hours since 1900-01-01 00:00:00"),
        "tmax": Var(np.asarray(values, dtype="float32")),
    })


def _axes(north_up=True, zero_360=True):
    grid = domain.land_grid()
    lat = grid.lat(np.arange(grid.nlat))
    lon = grid.lon(np.arange(grid.nlon))
    if north_up:
        lat = lat[::-1]
    if not zero_360:
        lon = np.where(lon >= 180.0, lon - 360.0, lon)
    return lat, lon


def _patch(monkeypatch, ds, path_exists=True):
    monkeypatch.setattr(fields.netCDF4, "Dataset", lambda path: ds)
    if path_exists:
        monkeypatch.setattr(fields, "land_path", lambda v, y, d=None: __import__(
            "pathlib").Path(f"{v}.{y}.nc"))


def test_reader_flips_latitude(monkeypatch):
    """Row 0 of the output is the SOUTHERNMOST row, out of a north-up file."""
    grid = domain.land_grid()
    lat, lon = _axes()
    # Each file row carries its own latitude as the value, so the output's
    # values say directly which row it came from.
    values = np.broadcast_to(lat[:, None], (grid.nlat, grid.nlon))[None, :, :]
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    dates, stack = fields.read_land_year("tmax", 2015)
    assert dates == [dt.date(2015, 1, 1)]
    assert stack.shape == (1, 360, 720)
    # Row 0 is -89.75, row 359 is 89.75 — ascending, i.e. flipped.
    assert stack[0, 0, 0] == pytest.approx(-89.75)
    assert stack[0, -1, 0] == pytest.approx(89.75)


def test_reader_does_not_roll_longitude(monkeypatch):
    """Column 0 is 0.25E. Rolling by half the grid would make it 180.25E."""
    grid = domain.land_grid()
    lat, lon = _axes()
    values = np.broadcast_to(lon[None, :], (grid.nlat, grid.nlon))[None, :, :]
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    _, stack = fields.read_land_year("tmax", 2015)
    assert stack[0, 0, 0] == pytest.approx(0.25)
    assert stack[0, 0, -1] == pytest.approx(359.75)


def test_south_up_file_is_rejected(monkeypatch):
    """A file that is NOT north-up must raise, not quietly draw upside down."""
    grid = domain.land_grid()
    lat, lon = _axes(north_up=False)
    values = np.zeros((1, grid.nlat, grid.nlon), dtype="float32")
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    with pytest.raises(ValueError, match="latitudes"):
        fields.read_land_year("tmax", 2015)


def test_minus_180_file_is_rejected(monkeypatch):
    """A -180..180 file must raise. Silently accepting it draws the wrong ocean."""
    grid = domain.land_grid()
    lat, lon = _axes(zero_360=False)
    values = np.zeros((1, grid.nlat, grid.nlon), dtype="float32")
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    with pytest.raises(ValueError, match="longitudes"):
        fields.read_land_year("tmax", 2015)


# --- Missing data, which is not zero -----------------------------------------


def test_zero_is_a_reading_not_a_gap():
    """A dry day is 0.0 mm and belongs in the table; only the sentinel is absent.

    The easiest mistake in this whole layer: dropping the zeros would make an
    absent row mean "dry" or "outside the gauge analysis" indistinguishably.
    """
    raw = np.array([0.0, 0.1, -5.0, fields.LAND_MISSING, np.nan], dtype="float32")
    assert list(fields.land_valid_mask(raw)) == [True, True, True, False, False]


# --- The storage scales ------------------------------------------------------


def test_temperature_round_trips_at_a_hundredth():
    """0.01 degC into Int16, over the source's declared valid_range."""
    celsius = np.array([-90.0, -27.17, 0.0, 12.345, 48.03, 50.0])
    counts = fields.to_temp_counts(celsius)
    assert counts.dtype == np.int16
    assert np.allclose(counts * fields.LAND_TEMP_SCALE, celsius, atol=0.005)


def test_precipitation_round_trips_at_a_tenth():
    """0.1 mm into UInt16, including the measured global maximum."""
    mm = np.array([0.0, 0.1, 108.4, 493.99, 666.69])
    counts = fields.to_precip_counts(mm)
    assert counts.dtype == np.uint16
    assert np.allclose(counts * fields.LAND_PRECIP_SCALE, mm, atol=0.05)


def test_precip_at_a_hundredth_would_have_clipped():
    """Why the precip scale is 0.1 mm and not 0.01 — the record of the choice.

    At 0.01 mm a UInt16 caps at 655.35 mm, below the 666.69 mm measured in the
    source. The scale is not a rounding preference; 0.01 would have silently
    clipped the wettest days, which is what a rainfall map is read for.
    """
    assert 666.69 / 0.01 > np.iinfo(np.uint16).max
    assert 666.69 / fields.LAND_PRECIP_SCALE < np.iinfo(np.uint16).max


def test_overflow_raises_rather_than_wrapping():
    """A wrapped value would come back as a plausible number, not an error."""
    with pytest.raises(ValueError, match="does not fit UInt16"):
        fields.to_precip_counts(np.array([9000.0]))
    with pytest.raises(ValueError, match="does not fit Int16"):
        fields.to_temp_counts(np.array([500.0]))


# --- The download guard ------------------------------------------------------
#
# `downloads.psl.noaa.gov` served a 497-byte nginx "currently unavailable" page
# in place of `tmin.2026.nc` during development, and a later request for the same
# URL returned the real 58 MB body. `.part`-and-rename alone would have promoted
# that page to a real filename, and the failure would have surfaced days later as
# an unreadable NetCDF, blaming the ingest.

NGINX_ERROR_PAGE = (
    b"<!DOCTYPE html>\n<html>\n<head>\n<title>Error</title>\n</head>\n<body>\n"
    b"<h1>An error occurred.</h1>\n<p>Sorry, the page you are looking for is "
    b"currently unavailable.<br/>Please try again later.</p>\n"
    b"<p><em>Faithfully yours, nginx.</em></p>\n</body>\n</html>\n"
)
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"


class _FakeResponse:
    def __init__(self, body, declared=None):
        self._body = body
        self.headers = {"content-length": str(declared if declared is not None else len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=None):
        yield self._body


class _FakeClient:
    """Serves one body per call, so a retry can be given a different one."""

    def __init__(self, *bodies):
        self._bodies = list(bodies)
        self.calls = 0

    def stream(self, method, url):
        self.calls += 1
        body = self._bodies[min(self.calls - 1, len(self._bodies) - 1)]
        return body if isinstance(body, _FakeResponse) else _FakeResponse(body)


@pytest.fixture
def no_backoff(monkeypatch):
    from CPC import download

    monkeypatch.setattr(download.time, "sleep", lambda s: None)
    return download


def test_error_page_is_refused_and_leaves_no_file(tmp_path, no_backoff):
    """An HTML body at HTTP 200 must not become a `.nc`, and must not linger."""
    download = no_backoff
    client = _FakeClient(NGINX_ERROR_PAGE)

    with pytest.raises(RuntimeError, match="could not download"):
        download.fetch(2026, download.TMIN, nc_dir=tmp_path, client=client)

    assert list(tmp_path.iterdir()) == [], "a refused download left files behind"


def test_truncated_body_is_refused(tmp_path, no_backoff):
    """A body shorter than Content-Length is a cut transfer, not a short file."""
    download = no_backoff
    body = HDF5_MAGIC + b"\x00" * 100
    client = _FakeClient(_FakeResponse(body, declared=len(body) + 5000))

    with pytest.raises(RuntimeError, match="could not download"):
        download.fetch(2026, download.TMAX, nc_dir=tmp_path, client=client)
    assert list(tmp_path.iterdir()) == []


def test_a_retry_recovers(tmp_path, no_backoff):
    """The error page is transient: the next attempt gets the real body.

    This is what was actually observed, and it is why `fetch` retries rather
    than giving up on a first refusal.
    """
    download = no_backoff
    good = HDF5_MAGIC + b"\x00" * 1024
    client = _FakeClient(NGINX_ERROR_PAGE, good)

    result = download.fetch(2026, download.PRECIP, nc_dir=tmp_path, client=client)

    assert result.path.name == "precip.2026.nc"
    assert result.path.read_bytes() == good
    assert client.calls == 2


# --- Rendering: grid-agnostic resampling and the coastline cut ---------------


def test_to_mercator_spacing_matches_the_old_ocean_formula():
    """The shape-derived spacing IS the old subset-derived one, on the ocean grid.

    `to_mercator` used to read `subset().nlat` and `lat_min`; it now derives both
    from the field's shape and the image edges. Measured byte-identical on a
    random 2500x3800 field at two widths, both resamplings — this pins the
    arithmetic that makes it so.
    """
    from shared import render

    box = domain.subset()
    edges = render.bounds()
    old_res = (box.lat_max - box.lat_min) / (box.nlat - 1)
    new_res = (edges["north"] - edges["south"]) / box.nlat
    assert new_res == pytest.approx(old_res, abs=1e-12)
    assert edges["south"] + 0.5 * new_res == pytest.approx(box.lat_min, abs=1e-12)


def _ocean_pixel_centres(width):
    """Where `to_mercator` puts the ocean frame's pixel centres."""
    from shared import render

    e = render.bounds()
    y_top, y_bot = render._merc_y(e["north"]), render._merc_y(e["south"])
    h = int(round(width * (y_top - y_bot) / np.radians(e["east"] - e["west"])))
    y = y_top + (np.arange(h) + 0.5) / h * (y_bot - y_top)
    lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    lon = e["west"] + (np.arange(width) + 0.5) * (e["east"] - e["west"]) / width
    return lat, lon


def test_land_canvas_shares_the_ocean_frame_grid():
    """Rows coincide everywhere; columns exactly, west of the dateline."""
    from shared import render

    for width in (512, 2048):
        c = render.land_canvas(width)
        lat, lon = _ocean_pixel_centres(width)
        h = len(lat)
        assert c.ocean_shape == (h, width)
        np.testing.assert_allclose(c.lat[c.row0 : c.row0 + h], lat, atol=1e-9)
        # Whole ocean columns west of the dateline (the one straddling it is not).
        west = lon[lon + 0.5 * c.px <= 180 + 1e-9]
        col0 = int(np.argmin(np.abs(c.lon - west[0])))
        np.testing.assert_allclose(c.lon[col0 : col0 + len(west)], west, atol=1e-9)


def test_land_canvas_stays_inside_the_dateline():
    """Mapbox draws a 360-degree image only in one world copy, so +-180 it is."""
    from shared import render

    c = render.land_canvas(2048)
    assert -180 <= c.west < -180 + c.px and 180 - c.px < c.east <= 180
    # 60S exactly — the ocean frame's own south edge — and just under 85N.
    assert c.south == pytest.approx(-60, abs=1e-9)
    assert 84.9 < c.north <= 85


def test_land_cut_never_overlaps_the_ocean_raster():
    """Checked geometrically: a land pixel is opaque only clear of every ocean
    pixel its extent touches — exactly one west of the dateline, two east of it."""
    from shared import render

    width = 512
    c = render.land_canvas(width)
    cut = render._land_cut(width)
    ocean = np.where(fields.ocean_mask(), 0.0, np.nan).astype("float32")
    footprint = np.isfinite(render.to_mercator(ocean, width, nearest=False))
    h = c.ocean_shape[0]
    band = cut[c.row0 : c.row0 + h]
    west = render.bounds()["west"]
    for k in range(c.shape[1]):
        lo = np.mod(c.lon[k] - 0.5 * c.px - west, 360.0)
        hi = lo + c.px
        j0, j1 = int(np.floor(lo / c.px + 1e-6)), int(np.ceil(hi / c.px - 1e-6))
        touched = [j for j in range(j0, j1) if 0 <= j < width]
        if touched:
            assert not (band[:, k][:, None] & footprint[:, touched]).any(), k


def test_land_to_canvas_picks_the_cell_under_each_pixel():
    from shared import render

    grid = domain.land_grid()
    lat_field = np.broadcast_to(grid.lat(np.arange(grid.nlat))[:, None], domain.land_shape())
    lon_field = np.broadcast_to(grid.lon(np.arange(grid.nlon))[None, :], domain.land_shape())
    c = render.land_canvas(512)
    got_lat = render.land_to_canvas(lat_field, 512)[:, 0]
    got_lon = render.land_to_canvas(lon_field, 512)[0]
    assert np.all(np.abs(got_lat - c.lat) <= 0.25 + 1e-9)
    assert np.all(np.abs((got_lon - c.lon % 360 + 180) % 360 - 180) <= 0.25 + 1e-9)


def test_land_frames_tile_the_ocean_exactly():
    """The land cut is the complement of the ocean rasters' own footprint.

    Cut with a nearest-sampled mask instead, the two rasters overlapped in
    11,987 pixels of a real frame (the ocean's bilinear coast sits a pixel
    landward); cut with the footprint, measured 0 under both `sst` and `mhw`.
    """
    from shared import render

    width = 512
    land = render._fine_land(width)
    ocean = np.where(fields.ocean_mask(), 0.0, np.nan).astype("float32")
    footprint = np.isfinite(render.to_mercator(ocean, width, nearest=False))
    assert not (land & footprint).any()
    assert (land | footprint).all()
    # And where the grids coincide (west of the dateline), the global cut IS it.
    c = render.land_canvas(width)
    h = c.ocean_shape[0]
    lon = _ocean_pixel_centres(width)[1]
    n = int((lon + 0.5 * c.px <= 180 + 1e-9).sum())
    col0 = int(np.argmin(np.abs(c.lon - lon[0])))
    assert np.array_equal(render._land_cut(width)[c.row0 : c.row0 + h, col0 : col0 + n], land[:, :n])


def test_ocean_mask_is_the_measured_one():
    """The committed mask is global; its box decodes to 7,477,923 ocean cells."""
    assert fields.global_ocean_mask().shape == (3600, 7200)
    mask = fields.ocean_mask()
    assert mask.shape == (2500, 3800)
    assert int(mask.sum()) == 7_477_923


# --- Buckets: what each declared transform does -------------------------------


@pytest.fixture
def land_days(monkeypatch):
    """Serve a synthetic stack as the land archive, and a synthetic normal.

    Returns a setter: `set(values, normal)` where `values` is (ndays, 250, 380)
    and `normal` is one (250, 380) field used for every calendar day.
    """
    state = {}

    def read_days(source, first, last, nc_dir=None):
        n = (last - first).days + 1
        values = state["values"][:n]
        return [first + dt.timedelta(days=i) for i in range(len(values))], values

    def read_clim(source, mmdds, *, period, window_days, clim_dir=None):
        return np.broadcast_to(state["normal"], (len(mmdds), *state["normal"].shape)).copy()

    monkeypatch.setattr(fields, "read_land_days", read_days)
    monkeypatch.setattr(fields, "read_land_clim", read_clim)

    def set_(values, normal=None):
        state["values"] = np.asarray(values, dtype="float32")
        state["normal"] = (
            np.asarray(normal, dtype="float32") if normal is not None
            else np.zeros(state["values"].shape[1:], dtype="float32")
        )
    return set_


def _stack(n, fill):
    return np.full((n, 250, 380), fill, dtype="float32")


def test_absolute_bucket_is_the_mean_of_the_dailies(land_days):
    from shared.buckets import bucket_field

    values = _stack(7, fields.LAND_MISSING)
    values[:, 10, 10] = [1, 2, 3, 4, 5, 6, 7]
    values[:3, 20, 20] = [10, 20, 30]  # only three days of data at this cell
    land_days(values)
    field, no_value, n = bucket_field(dt.date(2015, 7, 6), "weekly", "land_tmax")
    assert n == 7 and no_value is None
    assert field[10, 10] == pytest.approx(4.0)
    assert field[20, 20] == pytest.approx(20.0)  # over the days present
    assert np.isnan(field[0, 0])


def test_difference_is_mean_departure_from_normal(land_days):
    from shared.buckets import bucket_field

    values = _stack(7, fields.LAND_MISSING)
    values[:, 10, 10] = 25.0
    normal = np.full((250, 380), np.nan, dtype="float32")
    normal[10, 10] = 22.5
    land_days(values, normal)
    field, _, _ = bucket_field(dt.date(2015, 7, 6), "weekly", "land_tmax_anom")
    assert field[10, 10] == pytest.approx(2.5)


def test_ratio_is_log2_of_mean_over_normal(land_days):
    from shared.buckets import bucket_field

    values = _stack(7, fields.LAND_MISSING)
    values[:, 10, 10] = 4.0      # double the normal
    values[:, 11, 11] = 1.0      # half
    values[:, 12, 12] = 0.0      # bone dry: floored, not -inf
    values[:, 13, 13] = 0.5      # too dry a normal to divide by
    normal = np.full((250, 380), np.nan, dtype="float32")
    normal[10, 10] = normal[11, 11] = normal[12, 12] = 2.0
    normal[13, 13] = 0.05        # under min_normal
    land_days(values, normal)
    field, too_dry, _ = bucket_field(dt.date(2015, 7, 6), "weekly", "land_precip_ratio")
    assert field[10, 10] == pytest.approx(1.0)
    assert field[11, 11] == pytest.approx(-1.0)
    assert field[12, 12] == pytest.approx(-4.0)
    assert np.isnan(field[13, 13]) and too_dry[13, 13]
    assert not too_dry[10, 10] and not too_dry[0, 0]


def test_ratio_does_not_exist_daily(land_days):
    from shared.buckets import bucket_field

    land_days(_stack(1, 1.0))
    with pytest.raises(ValueError, match="not drawn at the daily period"):
        bucket_field(dt.date(2015, 7, 6), "daily", "land_precip_ratio")


# --- The climatology: window, weighting, file contract -----------------------


def test_window_is_circular_and_sample_weighted():
    from CPC.climatology import windowed_mean

    n = len(fields.MMDD_KEYS)
    sums = np.zeros((n, 1, 1))
    counts = np.zeros((n, 1, 1), dtype="int32")
    # 30 samples a day at value 10, except 0229, which exists in only 8 years
    # and is set to 100. A plain moving average of the per-day means would give
    # that one key the weight of a full 30 years.
    counts[:] = 30
    sums[:] = 30 * 10.0
    k = fields.MMDD_KEYS.index(229)
    counts[k] = 8
    sums[k] = 8 * 100.0

    out = windowed_mean(sums, counts, 3)
    expected = (30 * 10 + 8 * 100 + 30 * 10) / (30 + 8 + 30)
    assert out[k, 0, 0] == pytest.approx(expected)
    # Circular: 1 January's window reaches back to 31 December.
    sums[-1] = 30 * 40.0
    out = windowed_mean(sums, counts, 3)
    assert out[0, 0, 0] == pytest.approx((30 * 40 + 30 * 10 + 30 * 10) / 90)


def test_window_must_be_odd():
    from CPC.climatology import windowed_mean

    with pytest.raises(ValueError, match="odd"):
        windowed_mean(np.zeros((366, 1, 1)), np.zeros((366, 1, 1)), 4)


def test_climatology_file_refuses_a_different_window(tmp_path):
    """Editing a window in domain.yml without rebuilding must fail, not serve stale."""
    from CPC.climatology import write

    normal = np.zeros((366, 360, 720), dtype="float32")
    normal[fields.MMDD_KEYS.index(101)] = 1.0
    normal[fields.MMDD_KEYS.index(229)] = 2.0
    write("tmax", normal, period="1991-2020", window_days=15, clim_dir=tmp_path)

    got = fields.read_land_clim(
        "tmax", [229, 101, 229], period="1991-2020", window_days=15, clim_dir=tmp_path
    )
    assert got.shape == (3, 360, 720)
    assert got[0, 0, 0] == 2.0 and got[1, 0, 0] == 1.0 and got[2, 0, 0] == 2.0

    with pytest.raises(ValueError, match="15-day window"):
        fields.read_land_clim("tmax", [101], period="1991-2020", window_days=7, clim_dir=tmp_path)
    with pytest.raises(ValueError, match="1991-2020"):
        fields.read_land_clim("tmax", [101], period="1981-2010", window_days=15, clim_dir=tmp_path)


# --- Declarations ------------------------------------------------------------


def test_every_land_layer_declares_what_buckets_needs():
    land = {n: v for n, v in domain.variables().items() if v.grid == "land"}
    assert sorted(land) == sorted([
        "land_tmax", "land_tmin", "land_precip",
        "land_tmax_anom", "land_tmin_anom", "land_precip_ratio",
    ])
    for v in land.values():
        assert v.resampling == "nearest"
        if v.transform != "none":
            assert v.baseline and v.baseline.computed_by == "here"
    assert domain.variable("land_precip_ratio").periods == ("weekly", "monthly")
    # The encoding puts normal (log2 = 0) on an exact code, not between two.
    enc = domain.variable("land_precip_ratio").encoding
    assert (0.0 - enc.offset) / enc.scale == 128


def test_layer_validation_rejects_what_would_fail_far_away():
    import dataclasses

    good = domain.variable("land_precip_ratio")
    for bad in (
        {"grid": "sea"},
        {"transform": "ratio"},
        {"periods": ("hourly",)},
        {"source": None},
        {"min_normal": None},
    ):
        with pytest.raises(ValueError):
            domain._check_layer(dataclasses.replace(good, **bad))
    # An ocean variable may not claim a land source.
    with pytest.raises(ValueError, match="land-only"):
        domain._check_layer(dataclasses.replace(domain.variable("sst"), source="tmax"))


def test_render_range_skips_periods_a_layer_does_not_have():
    from CRW import imaging

    counts = imaging.render_range(
        dt.date(2015, 1, 1), dt.date(2015, 12, 31),
        variables=("land_precip_ratio",), dry_run=True, force=True,
    )
    weeks = len(imaging.closed_buckets("weekly", dt.date(2015, 1, 1), dt.date(2015, 12, 31)))
    assert counts["pending"] == weeks + 12  # no daily frames at all


def test_every_netcdf_read_takes_the_process_lock():
    """No `netCDF4.Dataset(` outside `_open` in `shared/fields.py`.

    Two threads inside HDF5 at once deadlock the whole API process — found when
    swipe compare asked for two uncached land frames at the same instant, and
    reproduced with three concurrent requests. The lock is what fixed it; this
    is what stops a new reader quietly opening a file around it.
    """
    import inspect

    source = inspect.getsource(fields)
    body = source.replace(inspect.getsource(fields._open), "")
    assert "netCDF4.Dataset(" not in body


# --- Pre-render only: /image never renders, and year files go once used -----


def test_image_serves_the_cache_and_never_renders(tmp_path, monkeypatch):
    """A cache miss is None (a 404), even with every source file on disk."""
    import importlib
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "api"))
    api_render = importlib.import_module("modules.render")
    monkeypatch.setattr(api_render, "cache_path", lambda *a, **k: tmp_path / "x.webp")
    assert api_render.render(dt.date(2015, 7, 1), period="weekly", variable_name="land_tmax") is None
    (tmp_path / "x.webp").write_bytes(b"RIFF")
    assert api_render.render(dt.date(2015, 7, 1)) == b"RIFF"


@pytest.fixture
def prune_env(tmp_path, monkeypatch):
    """A precip year file on disk and an empty image cache, both in tmp."""
    from CPC import config, prune

    nc_dir, img_dir = tmp_path / "land", tmp_path / "images"
    nc_dir.mkdir()
    monkeypatch.setattr(config, "land_path", lambda name, year, d=None: nc_dir / f"{name}.{year}.nc")
    monkeypatch.setattr(prune, "land_file_last_date", lambda name, year: dt.date(year, 3, 10))
    real = prune.cache_path
    monkeypatch.setattr(prune, "cache_path", lambda *a: real(*a, image_dir=img_dir))
    (nc_dir / "precip.2026.nc").write_bytes(b"")
    return prune, nc_dir, img_dir


def _render_all(prune, img_dir, first, last):
    from CPC import ingest

    for frame in prune.missing_frames(ingest.PRECIP_TARGET, first, last):
        name, period, day = frame.split("/")
        path = prune.cache_path(dt.date.fromisoformat(day), 2048, period, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def test_prune_keeps_a_year_until_every_frame_exists(prune_env):
    from CPC import ingest

    prune, nc_dir, img_dir = prune_env
    first, last = dt.date(2026, 1, 1), dt.date(2026, 3, 10)
    days = {first + dt.timedelta(days=n) for n in range((last - first).days + 1)}

    assert "not ingested" in prune.check(ingest.PRECIP_TARGET, 2026, days - {last})
    assert "not rendered" in prune.check(ingest.PRECIP_TARGET, 2026, days)

    frames = prune.missing_frames(ingest.PRECIP_TARGET, first, last)
    # The week containing 1 January starts in the previous December, and the
    # ratio has no daily frames at all.
    assert "land_precip/weekly/2025-12-29" in frames
    assert not any(f.startswith("land_precip_ratio/daily/") for f in frames)
    assert "land_precip_ratio/monthly/2026-03-01" in frames  # the open month too

    _render_all(prune, img_dir, first, last)
    assert prune.check(ingest.PRECIP_TARGET, 2026, days) is None


def test_prune_deletes_only_what_passes(prune_env, monkeypatch):
    from CPC import ingest, status

    prune, nc_dir, img_dir = prune_env
    first, last = dt.date(2026, 1, 1), dt.date(2026, 3, 10)
    days = {first + dt.timedelta(days=n) for n in range((last - first).days + 1)}
    monkeypatch.setattr(status, "ingested_dates", lambda client, table: days)

    assert prune.prune(None, ingest.PRECIP_TARGET, [2026]) == (0, 1)
    assert (nc_dir / "precip.2026.nc").exists()

    _render_all(prune, img_dir, first, last)
    assert prune.prune(None, ingest.PRECIP_TARGET, [2026], dry_run=True) == (1, 0)
    assert (nc_dir / "precip.2026.nc").exists()
    assert prune.prune(None, ingest.PRECIP_TARGET, [2026]) == (1, 0)
    assert not (nc_dir / "precip.2026.nc").exists()


def test_an_empty_land_day_encodes_as_a_blank_frame():
    """CPC has whole days with no temperature (1985-01-01 among them)."""
    from io import BytesIO

    from PIL import Image

    from shared import render

    blank = np.full(domain.land_shape(), np.nan, dtype="float32")
    img = Image.open(BytesIO(render.encode(blank, 256, "land_tmax")))
    assert np.asarray(img.convert("RGBA"))[..., 3].max() == 0
