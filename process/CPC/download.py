"""Fetch CPC Global Unified year files from NOAA PSL.

    https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{YYYY}.nc
    https://downloads.psl.noaa.gov/Datasets/cpc_global_temp/{tmax,tmin}.{YYYY}.nc

Public domain, no login. The shape is `CRW/download.py`'s — stream to a `.part`,
rename on completion, keep the server's `(size, last-modified)` so a revision can
be noticed later — with three differences, all of them measured rather than
anticipated:

1. **A file is a YEAR, not a date.** A past year is immutable and fetched once:
   `tmax.2015.nc` was last modified in 2020. The CURRENT year's file is rewritten
   in place as days are appended (`history: Updated 2026-09-17`), so it is
   re-fetched every run and its `(size, last-modified)` is what says whether
   there is anything new in it.

2. **The host serves an error page with no error status.** One attempt during
   development wrote a **497-byte nginx "currently unavailable" page** in place of
   the file; a later attempt at the same URL returned the real 58 MB body. A
   `.part`-and-rename alone would have promoted that page to `tmin.2026.nc`, and
   the failure would have surfaced as an unreadable NetCDF days later, blaming
   the ingest. So a body is checked — magic bytes and length — BEFORE the rename.

3. **There is a second host.** `psl.noaa.gov/thredds/fileServer/Datasets/...`
   serves byte-identical files and answered when the primary timed out, so it is
   tried after the primary's retries are exhausted rather than left as folklore.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import LAND_DIR, YearFile

log = logging.getLogger(__name__)

PRIMARY_HOST = "https://downloads.psl.noaa.gov/Datasets"
# Byte-identical files, and the fallback when the primary times out.
FALLBACK_HOST = "https://psl.noaa.gov/thredds/fileServer/Datasets"

PRECIP_PATH = "cpc_global_precip"
TEMP_PATH = "cpc_global_temp"

# A year file is 55-90 MB and the server is not fast. Generous per-read timeout,
# no overall cap: a stalled read fails, a merely slow one does not.
TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)

RETRIES = 3
BACKOFF_SECONDS = 5.0

# What a real file starts with. These are netCDF4, i.e. HDF5 (`\x89HDF`);
# classic NetCDF (`CDF\x01`) is accepted too, since the source could re-encode
# and that would not be a reason to refuse the data.
MAGIC = (b"\x89HDF", b"CDF\x01", b"CDF\x02")


@dataclass(frozen=True)
class Product:
    """One land variable: where its files come from and where they land.

    Three exist. They share this module because the mechanics are identical, and
    they are separate values rather than a branch because the two temperature
    variables come from a different directory than precipitation and can be
    fetched and ingested independently.
    """

    key: str
    dataset_path: str
    directory: Path

    def filename(self, year: int) -> str:
        return f"{self.key}.{year}.nc"

    def url(self, year: int, host: str = PRIMARY_HOST) -> str:
        return f"{host}/{self.dataset_path}/{self.filename(year)}"


PRECIP = Product("precip", PRECIP_PATH, LAND_DIR)
TMAX = Product("tmax", TEMP_PATH, LAND_DIR)
TMIN = Product("tmin", TEMP_PATH, LAND_DIR)

PRODUCTS = {p.key: p for p in (PRECIP, TMAX, TMIN)}


def product(key: str) -> Product:
    try:
        return PRODUCTS[key]
    except KeyError:
        raise KeyError(f"unknown land product {key!r}; known: {sorted(PRODUCTS)}") from None


def new_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True)


def head(
    year: int, product: Product, client: httpx.Client | None = None
) -> tuple[int, str] | None:
    """`(content_length, last_modified)` for a year, or None if unavailable.

    None is the normal answer for a year the source has not reached. It is also
    what a transient host failure looks like, which is why nothing treats it as
    proof that a year does not exist — only `fetch` decides that, and only after
    its retries.
    """
    owned = client is None
    client = client or new_client()
    try:
        for host in (PRIMARY_HOST, FALLBACK_HOST):
            target = product.url(year, host)
            try:
                response = client.head(target)
            except httpx.HTTPError as exc:
                log.warning("HEAD %s failed: %s", target, exc)
                continue
            if response.status_code == 200:
                return (
                    int(response.headers.get("content-length") or 0),
                    response.headers.get("last-modified", ""),
                )
            log.warning("HEAD %s returned %d", target, response.status_code)
        return None
    finally:
        if owned:
            client.close()


def _looks_like_netcdf(path: Path) -> bool:
    with path.open("rb") as fh:
        return fh.read(4) in MAGIC


def _fetch_once(url: str, partial: Path, client: httpx.Client) -> None:
    """Download `url` into `partial`, raising unless the body is a real file."""
    with client.stream("GET", url) as response:
        response.raise_for_status()
        declared = int(response.headers.get("content-length") or 0)
        with partial.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=1 << 20):
                fh.write(chunk)

    size = partial.stat().st_size
    # Checked in this order deliberately: the magic bytes are what catch the
    # error page, which is a valid HTTP 200 of a plausible length, and the length
    # check is what catches a connection cut short mid-body.
    if not _looks_like_netcdf(partial):
        head_bytes = partial.read_bytes()[:200]
        raise ValueError(
            f"{url} returned {size} bytes that are not a NetCDF file — the host "
            f"serves an HTML error page in place of the data. First bytes: "
            f"{head_bytes!r}"
        )
    if declared and size != declared:
        raise ValueError(
            f"{url} returned {size} bytes, Content-Length said {declared} — "
            "the transfer was cut short"
        )


def fetch(
    year: int,
    product: Product,
    nc_dir: Path | None = None,
    client: httpx.Client | None = None,
) -> YearFile:
    """Download one year of one variable and return it as a `YearFile`.

    Streamed into a `.part` file, **validated**, and only then renamed. The
    validation is the part that is not in `CRW/download.py`: see this module's
    docstring for the 497-byte nginx page that motivated it. A killed or refused
    transfer leaves no `.nc` behind at all.
    """
    nc_dir = nc_dir or product.directory
    nc_dir.mkdir(parents=True, exist_ok=True)

    target = nc_dir / product.filename(year)
    partial = target.with_suffix(target.suffix + ".part")

    owned = client is None
    client = client or new_client()
    attempts: list[str] = []
    try:
        for host in (PRIMARY_HOST, FALLBACK_HOST):
            source = product.url(year, host)
            for attempt in range(1, RETRIES + 1):
                try:
                    log.info("downloading %s (attempt %d)", source, attempt)
                    _fetch_once(source, partial, client)
                except (httpx.HTTPError, ValueError) as exc:
                    partial.unlink(missing_ok=True)
                    attempts.append(f"{source}: {exc}")
                    log.warning("download failed: %s", exc)
                    if attempt < RETRIES:
                        time.sleep(BACKOFF_SECONDS * attempt)
                except BaseException:
                    partial.unlink(missing_ok=True)
                    raise
                else:
                    partial.replace(target)
                    log.info(
                        "downloaded %s (%.1f MB)", target.name, target.stat().st_size / 1e6
                    )
                    return YearFile(path=target, variable=product.key, year=year)
    finally:
        if owned:
            client.close()

    raise RuntimeError(
        f"could not download {product.filename(year)} from either host after "
        f"{RETRIES} attempts each:\n  " + "\n  ".join(attempts)
    )
