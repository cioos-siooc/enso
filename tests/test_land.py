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


def test_box_resolves_on_the_land_grid(grid):
    """The one declared box, measured on the 0.5-degree grid: 250 x 380."""
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
    """Row 0 of the output is the box's SOUTHERN edge, out of a north-up file."""
    grid = domain.land_grid()
    lat, lon = _axes()
    # Each file row carries its own latitude as the value, so the output's
    # values say directly which row it came from.
    values = np.broadcast_to(lat[:, None], (grid.nlat, grid.nlon))[None, :, :]
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    dates, stack = fields.read_land_year("tmax", 2015)
    assert dates == [dt.date(2015, 1, 1)]
    assert stack.shape == (1, 250, 380)
    # Row 0 is -59.75, row 249 is 64.75 — ascending, i.e. flipped.
    assert stack[0, 0, 0] == pytest.approx(-59.75)
    assert stack[0, -1, 0] == pytest.approx(64.75)


def test_reader_does_not_roll_longitude(monkeypatch):
    """Column 0 is 100.25E. Rolling by half the grid would make it 280.25E."""
    grid = domain.land_grid()
    lat, lon = _axes()
    values = np.broadcast_to(lon[None, :], (grid.nlat, grid.nlon))[None, :, :]
    _patch(monkeypatch, _fake_dataset(lat, lon, values, [dt.date(2015, 1, 1)]))

    _, stack = fields.read_land_year("tmax", 2015)
    assert stack[0, 0, 0] == pytest.approx(100.25)
    assert stack[0, 0, -1] == pytest.approx(289.75)


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
