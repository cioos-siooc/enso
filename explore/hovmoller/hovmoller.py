"""Preview Hovmöller diagrams from the dev ClickHouse. Throwaway; not part of the app.

Run in the process image with this directory mounted at /work (writes out/ and cache/ here):
    docker compose ... run --rm -e PYTHONPATH=/app -v $PWD/explore/hovmoller:/work process python /work/hovmoller.py [plot ...]
"""
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import numpy as np

from shared import ch, domain

OUT = Path("/work/out")
CACHE = Path("/work/cache")
OUT.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

G = domain.global_grid()
ANOM = domain.variable("anom")
MHW = domain.variable("mhw")
client = ch.get_client()

LAT = f"({G.lat0} + gy * {G.resolution})"
LON = f"({G.lon0} + gx * {G.resolution})"
W = f"cos(radians({LAT}))"
MMDD = "toMonth(date) * 100 + toDayOfMonth(date)"


def cached(key: dict, fn):
    h = hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:12]
    path = CACHE / f"{key['kind']}_{h}.npz"
    if path.exists():
        z = np.load(path, allow_pickle=False)
        return {k: z[k] for k in z.files}
    t = time.time()
    res = fn()
    print(f"  {key['kind']} {key.get('start')}..{key.get('end')}: {time.time() - t:.1f}s", flush=True)
    np.savez_compressed(path, **res)
    return res


def _mmdd_index(dates: np.ndarray) -> np.ndarray:
    d = dates.astype("datetime64[D]").astype(object)
    return np.array([x.month * 100 + x.day for x in d])


def _grid(rows, dates, nbins):
    """rows of (date, bin, value) -> (ndates, nbins) array."""
    idx = {d: i for i, d in enumerate(dates)}
    a = np.full((len(dates), nbins), np.nan)
    for d, b, v in rows:
        if 0 <= b < nbins:
            a[idx[d], b] = v
    return a


def _dates(start, end):
    return np.arange(np.datetime64(start), np.datetime64(end) + np.timedelta64(1, "D"), dtype="datetime64[D]")


# --- Axis-aligned band: bins along longitude, averaged over a latitude band ---

def band_anom(lat_s, lat_n, lon_w, lon_e, bin_deg, start, end):
    key = dict(kind="band_anom", lat=(lat_s, lat_n), lon=(lon_w, lon_e), bin=bin_deg, start=start, end=end)

    def run():
        gy0, gy1 = int(G.gy(lat_s + G.resolution / 2)), int(G.gy(lat_n - G.resolution / 2))
        gx0, gx1 = int(G.gx(lon_w + G.resolution / 2)), int(G.gx(lon_e - G.resolution / 2))
        binw = int(round(bin_deg / G.resolution))
        nb = (gx1 - gx0 + 1) // binw
        where = f"gy BETWEEN {gy0} AND {gy1} AND gx BETWEEN {gx0} AND {gx1}"
        daily = client.query(f"""
            SELECT date, intDiv(gx - {gx0}, {binw}) AS b,
                   sum(sst_raw * 0.01 * {W}) / sum({W})
            FROM sst_daily
            WHERE {where} AND has_clim = 1 AND date BETWEEN '{start}' AND '{end}'
            GROUP BY date, b""").result_rows
        clim = client.query(f"""
            SELECT mmdd, intDiv(gx - {gx0}, {binw}) AS b, sum(clim_raw * 0.01 * {W}) / sum({W})
            FROM sst_clim WHERE {where} GROUP BY mmdd, b""").result_rows
        dates = _dates(start, end)
        sst = _grid([(np.datetime64(d), b, v) for d, b, v in daily], dates, nb)
        mm = sorted({m for m, _, _ in clim})
        ci = {m: i for i, m in enumerate(mm)}
        c = np.full((len(mm), nb), np.nan)
        for m, b, v in clim:
            if b < nb:
                c[ci[m], b] = v
        rows = np.array([ci.get(m, -1) for m in _mmdd_index(dates)])
        anom = sst - np.where(rows[:, None] >= 0, c[rows], np.nan)
        lons = lon_w + bin_deg * (np.arange(nb) + 0.5)
        return dict(dates=dates, x=lons, v=anom)

    return cached(key, run)


def band_mhw_extent(lat_s, lat_n, lon_w, lon_e, bin_deg, start, end):
    key = dict(kind="band_mhw", lat=(lat_s, lat_n), lon=(lon_w, lon_e), bin=bin_deg, start=start, end=end)

    def run():
        gy0, gy1 = int(G.gy(lat_s + G.resolution / 2)), int(G.gy(lat_n - G.resolution / 2))
        gx0, gx1 = int(G.gx(lon_w + G.resolution / 2)), int(G.gx(lon_e - G.resolution / 2))
        binw = int(round(bin_deg / G.resolution))
        nb = (gx1 - gx0 + 1) // binw
        where = f"gy BETWEEN {gy0} AND {gy1} AND gx BETWEEN {gx0} AND {gx1} AND date BETWEEN '{start}' AND '{end}'"
        den = client.query(f"""
            SELECT date, intDiv(gx - {gx0}, {binw}) AS b, sum({W})
            FROM sst_daily WHERE {where} GROUP BY date, b""").result_rows
        num = client.query(f"""
            SELECT date, intDiv(gx - {gx0}, {binw}) AS b, sum({W})
            FROM mhw_daily WHERE {where} AND cat BETWEEN 1 AND 5 GROUP BY date, b""").result_rows
        dates = _dates(start, end)
        d = _grid([(np.datetime64(a), b, v) for a, b, v in den], dates, nb)
        n = _grid([(np.datetime64(a), b, v) for a, b, v in num], dates, nb)
        n = np.where(np.isnan(n) & ~np.isnan(d), 0.0, n)
        return dict(dates=dates, x=lon_w + bin_deg * (np.arange(nb) + 0.5), v=100 * n / d)

    return cached(key, run)


# --- Arbitrary straight line: bins along it, averaged across it ---

def line_anom(a, b, step_km, half_km, start, end):
    """a, b: (lat, lon 0-360). Local equirectangular projection about the line's mid-latitude."""
    key = dict(kind="line_anom", a=a, b=b, step=step_km, half=half_km, start=start, end=end)

    def run():
        (la, oa), (lb, ob) = a, b
        k = np.cos(np.radians((la + lb) / 2))
        dx, dy = (ob - oa) * k * 111.32, (lb - la) * 110.57
        L = float(np.hypot(dx, dy))
        nb = int(L // step_km)
        pad = half_km / 100
        gy0, gy1 = int(G.gy(min(la, lb) - pad)), int(G.gy(max(la, lb) + pad))
        gx0, gx1 = int(G.gx(min(oa, ob) - pad / k)), int(G.gx(max(oa, ob) + pad / k))
        x = f"(({LON} - {oa}) * {k * 111.32})"
        y = f"(({LAT} - {la}) * 110.57)"
        s = f"(({x} * {dx} + {y} * {dy}) / {L})"
        d = f"abs(({x} * {dy} - {y} * {dx}) / {L})"
        where = f"gy BETWEEN {gy0} AND {gy1} AND gx BETWEEN {gx0} AND {gx1} AND {d} <= {half_km} AND {s} >= 0 AND {s} < {nb * step_km}"
        bexp = f"toUInt32(floor({s} / {step_km}))"
        daily = client.query(f"""
            SELECT date, {bexp} AS bin, sum(sst_raw * 0.01 * {W}) / sum({W})
            FROM sst_daily WHERE {where} AND has_clim = 1 AND date BETWEEN '{start}' AND '{end}'
            GROUP BY date, bin""").result_rows
        clim = client.query(f"""
            SELECT mmdd, {bexp} AS bin, sum(clim_raw * 0.01 * {W}) / sum({W})
            FROM sst_clim WHERE {where} GROUP BY mmdd, bin""").result_rows
        dates = _dates(start, end)
        sst = _grid([(np.datetime64(dd), bb, v) for dd, bb, v in daily], dates, nb)
        mm = sorted({m for m, _, _ in clim})
        ci = {m: i for i, m in enumerate(mm)}
        c = np.full((len(mm), nb), np.nan)
        for m, bb, v in clim:
            c[ci[m], bb] = v
        rows = np.array([ci.get(m, -1) for m in _mmdd_index(dates)])
        anom = sst - np.where(rows[:, None] >= 0, c[rows], np.nan)
        return dict(dates=dates, x=step_km * (np.arange(nb) + 0.5), v=anom)

    return cached(key, run)


# --- Plotting ---

def weekly(r):
    """Mean over Monday-start weeks, labelled by the Monday (shared/periods.py's rule)."""
    d = r["dates"]
    monday = d - ((d.astype("datetime64[D]").view("int64") - 4) % 7)  # 1970-01-01 was a Thursday
    weeks, inv = np.unique(monday, return_inverse=True)
    out = np.full((len(weeks), r["v"].shape[1]), np.nan)
    for i in range(len(weeks)):
        with np.errstate(all="ignore"):
            out[i] = np.nanmean(r["v"][inv == i], axis=0)
    return dict(dates=weeks, x=r["x"], v=out)


def anom_cmap():
    return matplotlib.colormaps[ANOM.colormap], ANOM.vmin, ANOM.vmax


def lon_label(v, _=None):
    v = v % 360
    if v == 0 or v == 180:
        return f"{v:.0f}°"
    return f"{v:.0f}°E" if v < 180 else f"{360 - v:.0f}°W"


def draw(ax, r, cmap, vmin, vmax, norm=None, xfmt=lon_label, nino=True):
    d = r["dates"].astype("datetime64[D]")
    t0, t1 = mdates.date2num(d[0].astype(object)), mdates.date2num((d[-1] + np.timedelta64(1, "D")).astype(object))
    x = r["x"]
    half = (x[1] - x[0]) / 2
    im = ax.imshow(
        r["v"], aspect="auto", origin="upper", interpolation="nearest",
        extent=(x[0] - half, x[-1] + half, t1, t0),
        cmap=cmap, norm=norm, **({} if norm else dict(vmin=vmin, vmax=vmax)),
    )
    ax.yaxis_date()
    if xfmt:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(xfmt))
    if nino:
        for lon in (190, 240, 270):
            ax.axvline(lon, color="k", lw=0.5, ls=":", alpha=0.6)
    ax.set_facecolor("#bbbbbb")
    return im


def plot_overview():
    r = weekly(band_anom(-5, 5, 120, 280, 1.0, "1985-01-01", "2026-10-03"))
    cmap, vmin, vmax = anom_cmap()
    fig, ax = plt.subplots(figsize=(7, 22))
    im = draw(ax, r, cmap, vmin, vmax)
    ax.yaxis.set_major_locator(mdates.YearLocator(1))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xticks(range(120, 281, 20))
    ax.set_title("SST anomaly, 5°S–5°N, weekly, 1985–2026\n(dotted: Niño 3.4 edges at 170°W/120°W, Niño 3 east edge 90°W)", fontsize=9)
    fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.02, fraction=0.015, label="°C vs 1991–2020 daily mean")
    fig.tight_layout()
    fig.savefig(OUT / "1_overview_1985_2026.png", dpi=110)
    plt.close(fig)
    return r


def plot_events():
    wins = [
        ("1997-98 (eastern-Pacific El Niño)", "1997-01-01", "1998-12-31"),
        ("2009-10 (central-Pacific El Niño)", "2009-01-01", "2010-12-31"),
        ("2015-16", "2015-01-01", "2016-12-31"),
        ("2023-24", "2023-01-01", "2024-12-31"),
        ("2025-now", "2025-01-01", "2026-10-03"),
    ]
    cmap, vmin, vmax = anom_cmap()
    fig, axes = plt.subplots(1, len(wins), figsize=(22, 9), sharey=False)
    for ax, (title, s, e) in zip(axes, wins):
        r = band_anom(-5, 5, 120, 280, 1.0, s, e)
        im = draw(ax, r, cmap, vmin, vmax)
        ax.yaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.tick_params(labelsize=7)
        ax.set_xticks(range(120, 281, 40))
        ax.set_title(title, fontsize=10)
    fig.suptitle("SST anomaly along the equator (5°S–5°N mean), daily, 1° bins", fontsize=12)
    fig.colorbar(im, ax=axes, orientation="horizontal", pad=0.06, fraction=0.025, label="°C vs 1991–2020 daily mean")
    fig.savefig(OUT / "2_event_windows.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def plot_bandwidth():
    bands = [("0° only (2 rows, 0.1°)", 0.05), ("±1°", 1), ("±2°", 2), ("±5°", 5)]
    cmap, vmin, vmax = anom_cmap()
    fig, axes = plt.subplots(1, len(bands), figsize=(18, 8), sharey=True)
    stats = []
    for ax, (title, h) in zip(axes, bands):
        r = band_anom(-h, h, 120, 280, 1.0, "2015-01-01", "2015-12-31")
        im = draw(ax, r, cmap, vmin, vmax)
        ax.yaxis.set_major_locator(mdates.MonthLocator())
        ax.yaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.set_xticks(range(120, 281, 40))
        ax.tick_params(labelsize=7)
        # day-to-day noise: median absolute first difference in time
        noise = np.nanmedian(np.abs(np.diff(r["v"], axis=0)))
        stats.append((title, noise))
        ax.set_title(f"{title}\nmedian |day-to-day change| {noise:.2f} °C", fontsize=9)
    fig.suptitle("2015, same line, different averaging width across it", fontsize=12)
    fig.colorbar(im, ax=axes, orientation="horizontal", pad=0.06, fraction=0.03, label="°C vs 1991–2020 daily mean")
    fig.savefig(OUT / "3_band_width_2015.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return stats


def plot_mhw():
    r = band_mhw_extent(-5, 5, 120, 280, 1.0, "2023-01-01", "2024-12-31")
    fig, ax = plt.subplots(figsize=(8, 10))
    im = draw(ax, r, matplotlib.colormaps["inferno"], 0, 100)
    ax.yaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_xticks(range(120, 281, 20))
    ax.set_title("Marine heatwave extent along the equator, 2023–24\nshare of each 1° bin's ocean (5°S–5°N) at Cat ≥ 1", fontsize=10)
    fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.05, fraction=0.03, label="% of ocean area in a heatwave")
    fig.tight_layout()
    fig.savefig(OUT / "4_mhw_extent_2023_24.png", dpi=110)
    plt.close(fig)


def plot_tiw():
    r = band_anom(0, 5, 190, 270, 0.25, "2010-06-01", "2010-12-31")
    v = r["v"]
    # Zonal high-pass: subtract a 10° running mean along longitude, leaving the ~1000 km ripples.
    k = 40
    pad = np.pad(v, ((0, 0), (k // 2, k // 2)), mode="edge")
    smooth = np.stack([np.nanmean(pad[:, i:i + k + 1], axis=1) for i in range(v.shape[1])], axis=1)
    hp = dict(r, v=v - smooth)
    fig, axes = plt.subplots(1, 2, figsize=(14, 9), sharey=True)
    cmap, vmin, vmax = anom_cmap()
    im0 = draw(axes[0], r, cmap, vmin, vmax, nino=False)
    axes[0].set_title("SST anomaly, 0–5°N, 0.25° bins, daily", fontsize=10)
    im1 = draw(axes[1], hp, cmap, -1.5, 1.5, nino=False)
    axes[1].set_title("same, minus a 10° running mean along longitude\n(westward-sloping ripples = tropical instability waves)", fontsize=10)
    for ax in axes:
        ax.yaxis.set_major_locator(mdates.MonthLocator())
        ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.set_xticks(range(190, 271, 10))
        ax.tick_params(labelsize=7)
    fig.colorbar(im0, ax=axes[0], orientation="horizontal", pad=0.05, fraction=0.03, label="°C")
    fig.colorbar(im1, ax=axes[1], orientation="horizontal", pad=0.05, fraction=0.03, label="°C")
    fig.suptitle("Tropical instability waves, Jun–Dec 2010 (La Niña)", fontsize=12)
    fig.savefig(OUT / "5_tiw_2010.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def plot_linep():
    a, b = (48.58, 360 - 124.75), (50.0, 360 - 145.0)   # Juan de Fuca -> Station Papa
    r = line_anom(a, b, 25, 28, "2013-01-01", "2016-12-31")
    rw = weekly(r)
    cmap, vmin, vmax = anom_cmap()
    fig, (ax, axm) = plt.subplots(1, 2, figsize=(12, 10), gridspec_kw=dict(width_ratios=(3, 1)))
    im = draw(ax, rw, cmap, vmin, vmax, xfmt=None, nino=False)
    ax.set_xlabel("km from Juan de Fuca along Line P → Station Papa")
    ax.yaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(labelsize=7)
    ax.set_title("SST anomaly along Line P, weekly, 2013–2016\n25 km bins, ±28 km across the line", fontsize=10)
    fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.06, fraction=0.03, label="°C vs 1991–2020 daily mean")
    # inset map of the line
    axm.plot([a[1] - 360, b[1] - 360], [a[0], b[0]], "k-", lw=2)
    axm.plot(a[1] - 360, a[0], "go"); axm.plot(b[1] - 360, b[0], "ro")
    axm.annotate("Juan de Fuca (0 km)", (a[1] - 360, a[0]), fontsize=7, xytext=(-60, -15), textcoords="offset points")
    axm.annotate("Station Papa", (b[1] - 360, b[0]), fontsize=7, xytext=(0, 8), textcoords="offset points")
    axm.set_xlim(-150, -120); axm.set_ylim(44, 56); axm.set_aspect(1 / np.cos(np.radians(50)))
    axm.set_title("where the line is", fontsize=9); axm.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "6_line_p_2013_2016.png", dpi=110)
    plt.close(fig)


def spot_check(r):
    """Nino 3.4 = bins whose centres are in 190..240, for the API to compare against."""
    sel = (r["x"] > 190) & (r["x"] < 240)
    for d in ("2015-11-23", "2023-12-04", "2010-11-01"):
        i = np.where(r["dates"] == np.datetime64(d))[0][0]
        print(f"  Nino 3.4 week of {d}: {np.nanmean(r['v'][i, sel]):.3f}")


if __name__ == "__main__":
    which = set(sys.argv[1:]) or {"1", "2", "3", "4", "5", "6"}
    if "1" in which:
        spot_check(plot_overview())
    if "2" in which:
        plot_events()
    if "3" in which:
        for t, n in plot_bandwidth():
            print(f"  band {t}: median |daily change| {n:.3f}")
    if "4" in which:
        plot_mhw()
    if "5" in which:
        plot_tiw()
    if "6" in which:
        plot_linep()
    print("done")
