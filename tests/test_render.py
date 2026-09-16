"""`encode()`: the images carry data, so the packing has to round-trip."""

import io

import numpy as np
import pytest
from PIL import Image

from shared import domain, render

WIDTH = 256


def _decode(payload: bytes, variable_name: str) -> tuple[np.ndarray, np.ndarray]:
    """Codes and alpha out of a rendered WebP, the way the ramp reads them."""
    enc = domain.variable(variable_name).encoding
    rgba = np.asarray(Image.open(io.BytesIO(payload)).convert("RGBA")).astype("int64")
    idx = {"R": 0, "G": 1, "B": 2}
    codes = np.zeros(rgba.shape[:2], "int64")
    for channel in enc.channels:
        codes = codes * 256 + rgba[..., idx[channel.upper()]]
    return codes, rgba[..., 3]


def _field(value: float) -> np.ndarray:
    box = domain.subset()
    return np.full((box.nlat, box.nlon), value, dtype="float32")


def test_sst_round_trip_is_lossless_at_the_encoding_step():
    box = domain.subset()
    rng = np.random.default_rng(0)
    field = rng.uniform(-2, 32, (box.nlat, box.nlon)).astype("float32")
    enc = domain.variable("sst").encoding

    codes, alpha = _decode(render.encode(field, WIDTH, "sst"), "sst")
    expected = np.round((render.to_mercator(field, WIDTH) - enc.offset) / enc.scale)
    assert (alpha == 255).all()
    assert np.array_equal(codes, expected.astype("int64"))


@pytest.mark.parametrize("value, end", [(40.0, "high"), (-40.0, "low")])
def test_anomaly_clamps_rather_than_wraps(value, end):
    enc = domain.variable("anom").encoding
    codes, _ = _decode(render.encode(_field(value), WIDTH, "anom"), "anom")
    want = enc.depth - 1 if end == "high" else enc.low_code
    assert (codes == want).all()


def test_no_climatology_cells_get_the_sentinel():
    box = domain.subset()
    field = _field(1.0)
    no_clim = np.zeros((box.nlat, box.nlon), bool)
    no_clim[: box.nlat // 2] = True
    field[no_clim] = np.nan

    codes, alpha = _decode(render.encode(field, WIDTH, "anom", no_clim=no_clim), "anom")
    enc = domain.variable("anom").encoding
    assert (alpha == 255).all()
    assert (codes == enc.sentinel).any()
    assert (codes[alpha == 255] != enc.sentinel).any()


def test_land_is_alpha_zero():
    """Land is cut by alpha, exactly.

    The value channels *under* that alpha are not asserted. `_bleed()` fills them
    with nearby ocean values, but lossless WebP without `exact=True` is free to
    rewrite fully transparent pixels. Measured on a cached 1996 frame, 1,784 of
    23,279 coastal land texels came back as code 0. `raster-resampling: nearest`
    keeps that from reaching the screen. `_bleed` itself is tested below.
    """
    box = domain.subset()
    field = _field(20.0)
    field[:, : box.nlon // 2] = np.nan

    _, alpha = _decode(render.encode(field, WIDTH, "sst"), "sst")
    assert (alpha[:, : WIDTH // 2 - 1] == 0).all()
    assert (alpha[:, WIDTH // 2 + 1 :] == 255).all()


def test_bleed_works_on_codes_across_a_byte_wrap():
    """Averaging 255 and 256 as codes gives 255, not a low byte of ~128."""
    codes = np.array([[255, 0, 256]], dtype="int64")
    known = np.array([[True, False, True]])
    out = render._bleed(codes, known)
    assert out[0, 1] == 255


def test_categorical_resample_invents_no_class():
    box = domain.subset()
    field = np.full((box.nlat, box.nlon), np.nan, dtype="float32")
    field[: box.nlat // 2] = 2.0
    field[box.nlat // 2 :] = 4.0

    codes, alpha = _decode(render.encode(field, WIDTH, "mhw"), "mhw")
    assert set(np.unique(codes[alpha == 255])) <= {2, 4}
