# Ocean data: CoralTemp, Marine Heatwave and their baselines

The two Coral Reef Watch archives, the climatology, the orientation rules and the domain.

## Data Source

**NOAA Coral Reef Watch CoralTemp v3.1** (`coraltemp_v3.1_YYYYMMDD.nc`), one file per day
in `./data/sst/`, mounted at `/opt/data/sst/`. 1985-01-01 onward, ~10 MB each, ~153 GB for the
full archive.

Global 7200×3600 grid at **0.05°**. The variable taken is `analysed_sst` — `short` counts
of 0.01 °C with `_FillValue = -32768`. (`sea_ice_fraction` is also in the file and is not
ingested.) **There is no anomaly in the product**; it is derived, see below.

### The second daily product: Marine Heatwave category

**NOAA CRW Marine Heatwave v1.0.1** (`noaa-crw_mhw_v1.0.1_category_YYYYMMDD.nc`), one file
per day in `./data/MHW/`, mounted at `/opt/data/MHW/`. Same 1985-01-01 onward, ~640 KB
each, 9.7 GB for the full archive.

**A different product suite, not a sibling of `sst/` under the CoralTemp tree** — there is
no `mhw/` beside it. It is derived from CoralTemp v3.1 but versioned and published
separately, at `.../crw/data/marine_heatwave/v1.0.1/category/nc/{YYYY}/`.

**Both products publish at roughly one day's latency, and MHW lands about 90 minutes after
CoralTemp** — measured by HEAD, 2026-08-27 carried `Last-Modified` 14:52 UTC for SST and
15:20 UTC for MHW. So the gap is intra-day, not a day: a `run` scheduled in that window
sees SST published and MHW not. That is why the two are tracked and processed
independently rather than paired, and why the catch-up watermark is the earlier of the
two.

The variable is `heatwave_category`. Same 7200×3600 grid, **same latitude orientation as
the dailies** (`lat[0] = -89.975`, so no flip), same longitude roll. Verified: the box's
land mask matches `sst_daily` exactly at 7,477,923 ocean cells. (NOAA's own browse PNGs for
this product *are* north-up — a trap if the palette is ever re-derived from one.)

Four states, and only one of them is drawn:

| code | meaning | stored? | drawn? |
|---|---|---|---|
| -127 | land | no | transparent |
| -1 | ice | no | transparent |
| 0 | ocean, no heatwave | no | transparent |
| 1..5 | Moderate / Strong / Severe / Extreme / Beyond extreme | yes | NOAA's palette |

**NOAA re-encoded this variable on 2024-07-01, mid-archive, without changing the filename,
the `v1.0.1` version string or the URL.** The table above is the *old* encoding; land and
ice are no longer distinguishable in the file at all:

| | dtype | `_FillValue` | `valid_min` | land | ice |
|---|---|---|---|---|---|
| …2024-06-30 | `int8` | −127 | −2 | −127 | −1 |
| 2024-07-01… | `uint8` | **251** | 0 | 251 | 251 |

**`shared/fields.py`'s `mhw_valid_mask` therefore bounds the category range at both ends —
`1 <= raw <= 5` — and must keep doing so.** The obvious `raw >= 1` is correct on the first
encoding and catastrophic on the second, because 251 is a *positive* number: every land and
ice cell passes as a heatwave four times worse than Cat 5.

**Nothing about that failure is loud**, which is the part worth remembering. The ingest ran
clean, `/coverage` reported the archive complete, `mhw_daily` filled with 1.7 billion rows
of `cat = 251` (787 days, ~46% of the table), and every rendered frame from that date drew
land at Cat 5. It surfaced only as a region area mean of **62** on a 1–5 scale — which the
chart could not draw at all, because its y-axis is pinned to 0..5.

Testing `<= 5` rather than the file's own `_FillValue` is deliberate: 1..5 is fixed by the
product definition — it is the five names in the legend — so the rule survives both
encodings and whatever NOAA ships next. The fill value is what changed; the categories are
what did not.

**And there is a third failure of the same field, which the 1..5 bound cannot catch: every
29 February in the archive ships with land collapsed into ocean at category 5.** Not a
re-encoding — a bad file, in a product that is otherwise fine either side of it:

| | land as `-127` | land as `5` | `mask == 2` (land) |
|---|---|---|---|
| 2024-02-28 | 8,726,860 | — | 8,726,860 |
| **2024-02-29** | **0** | **8,731,446** | **0** |
| 2016-02-29 / 2020-02-29 | 0 | ~8,727,000 | 0 |

The companion `mask` variable is wrong the same way — it reports water where land is — and
its ice count is byte-identical across 2016, 2020 and 2024, so the leap-day mask is frozen
boilerplate rather than that day's. 5 is a legal category, so nothing in the value can
reject it: it put **2,022,077 land cells a day at Cat 5** in `mhw_daily`, took the basin's
heatwave extent to **62.4%** on 2024-02-29 against ~30% either side, and drew the continents
in Cat 5's dark red on every leap-day frame. All ten leap days were affected.

`read_mhw_raw` therefore stops trusting the file's own land encoding: it asks the `mask`
variable whether the file carries **any** land — a global grid always does — and when it
does not, takes the land mask from the same date's CoralTemp file and rewrites those cells
to `MHW_LAND_CODE`. It **raises** if that file is not on disk rather than falling back,
which is why `shared/buckets.py` passes `sst_dir` alongside `mhw_dir`: on a leap day the
CoralTemp file is not a nicety, it is where land comes from. Repaired, 2024-02-29 reads
2,694,751 heatwave cells with 1,612 at Cat 5, against 02-28's 2,677,962 and 1,901.

**The `mask` variable's land code changed with the 2024-07-01 re-encoding as well**: 2
before, **1** after (`flag_meanings: valid-water land missing ice` = 0 1 2 4). The code is
read from the variable's own `flag_values`/`flag_meanings` (`_mhw_mask_land_code`), with 2
only as the fallback. Until 2026-10-08 it was hard-coded at 2, so every post-2024 file
looked like a leap-day file and was "repaired" from CoralTemp: the same output (251 is
outside 1..5 anyway), but an extra 10 MB read per MHW day and a hard failure whenever
that day's CoralTemp file was missing.

`CRW.cli repair-mhw-land` is the remediation, and it is a range rather than one file for
the same reason `render` is: a weekly frame is a max over seven days, so re-rendering it
with only the leap day on disk would replace a good seven-day max with a one-day one. Per
date it fetches the CoralTemp file plus every MHW file the leap day's week and month span,
re-ingests, re-renders the three `mhw` buckets and rebuilds `region_daily` for that date.

## Two baselines, and they are not reconcilable

**`anom` and `mhw` are measured against different climatologies, and nothing in
either number says so.** This is the one thing about the dashboard a reader is
most likely to get wrong, because the natural assumption — that a big anomaly is
roughly a high category — is false and looks true.

| | `anom` | `mhw` |
|---|---|---|
| years | **1991-2020** (30) | **1985-2012** (28) |
| window | 1 day (`window-01day`) | **11 days**, centred on the day of year |
| statistic | mean | mean **and 90th percentile** |
| leap day | its own file, `day0229` (366 files) | excluded; derived as the mean of Feb 28 and Mar 1 (**365** files) |
| computed | here, from `sst_clim` | by NOAA, before we see the file |

The MHW climatology lives at `.../marine_heatwave/v1.0.1/climatology/nc/` as
`noaa-crw_mhw_v1.0_climatology_{001..365}.nc`, carrying `sst_clim_mean` and
`sst_clim_ninetieth_percentile_variable`. **Nothing in this repo downloads it** —
`download.py` fetches only `category/nc/{YYYY}/` — and it should stay that way:
we ingest the finished category, not a temperature, so the baseline is a fact
about the incoming file rather than a choice.

**Re-basing `anom` onto 1985-2012 to "match" would not work, and the numbers say
why.** Cat 1 is `SST > P90`, an *exceedance*, and the P90-minus-mean departure it
represents is a different number in every cell: measured over this box for day
001, **+1.02 degC mean, +0.60 at p5, +1.62 at p95**. The two baselines' means
differ by only **+0.104 degC** over the same cells (median +0.110, sd 0.116;
1991-2020 is the warmer one). So the shift is ~10% of the spread that would have
to close, and no anomaly value maps to a category under any baseline. Three
further costs, if it is ever proposed again: 1991-2020 is the WMO normal the
ONI-style index in `/state` needs; `has_clim` is a stored column in
`sst_daily`, so the valid mask changing means a **full re-ingest**; and all
~17.9 k cached `anom` frames encode the anomaly value, with only the retention
window's NetCDF left on disk to re-render from.

One real point in the other direction, recorded so it is not rediscovered as a
bug: the MHW climatology covers **7,477,923 cells in this box against 1991-2020's
7,261,562** (Jan 1) — every ocean cell, with sensible ice-fringe values around
-1.2..-1.8 degC. Adopting it would retire the `NO_CLIM_RGBA` grey third state.
It is also **south-up**, like the dailies, where the ct5km climatology is
north-up.

**The method is not NOAA's, and the UI says so.** NOAA Coral Reef Watch applies
the algorithm and publishes the product; the definition and the five category
names are **Hobday et al. 2016** (Prog. Oceanogr. 141, 227-238), **Hobday et al.
2018** (Oceanography 31(2)) and **Oliver et al. 2018** (Nat. Commun. 9, 1324).
Asked for by a user, and it is a real misattribution rather than a missing
nicety.

**Where this is said, and it is said once.** `domain.yml` declares a `baseline`
block per variable — `period`, `statistic` (`mean` | `p90`), `window_days`,
`label`, `computed_by` (`here` | `noaa`), `note`, `references` — validated by
`shared/domain.py`'s `_check_baseline()` and shipped through `/domain`. The
string used to be a constant in `api/modules/state.py`, another in
`api/modules/timeseries.py`, and a literal in `ranking.ts`, `AboutDialog.vue`
and `app.vue`; all five now read the declaration. `statistic` is the
load-bearing field: it picks the preposition, so a `p90` baseline is phrased as
something the value **exceeds** rather than something it departs from.

**The climatology is a second archive**: 366 files in `./data/climatology/`, mounted at
`/opt/data/climatology/`, one per MMDD **including `day0229`** — so there is no leap-day
mapping rule to invent. Baseline 1991–2020. 1.6 GB, static, and **kept forever**: image
rendering reads it straight off disk.

They come from a **different tree than the dailies** — not `5km/v3.1_op/`, whose
`climatology/` holds only one combined file on the older baseline:

```
.../crw/data/5km/v3.1-clim19912020-v1/climatology/nc/
    ct5km_v3.1_clim-sst-mean-daily-window-01day-01grid-source19912020_day{MMDD}.nc
```

There is no download code for them; they are fetched once by hand. **"Kept forever" is not
the same as "safe"** — see the bit-rot gotcha below.

## Two orientation conventions, both of which fail silently

`shared/fields.py` is the only place either is applied. Both produce output that looks
entirely plausible when wrong, which is why `check_orientation()` raises rather than warns.

1. **Longitude.** Source files run −179.975…179.975. This project indexes on **0–360**
   (`domain.yml`'s `lon0: 0.025`), applied as a roll of half the grid,
   `gx_project = (gx_file + 3600) % 7200`. The reason is that the Pacific box straddles
   the antimeridian: on the native grid it is two wrapping `gx` ranges and every
   `WHERE gx BETWEEN` in the codebase would have to know. Get the roll wrong and the map
   draws the Pacific over the Atlantic, convincingly.

2. **Latitude.** The daily files are **south-up** (`lat[0] = −89.975`). The climatology
   files are **north-up** and must be flipped. Subtracting them unflipped yields an
   anomaly field spanning about ±18 °C instead of ±5 — wrong in every cell, and it renders
   as a believable map. The diagnostic that catches it: correctly oriented, climatology
   valid cells are a strict *subset* of daily valid cells (13.31 M of 17.19 M globally);
   flipped, the overlap collapses to 9.17 M.

## The domain: a Pacific box, not the globe

**60°S–65°N, 100°E–290°E** — `gy` 600..3099 (2500 rows), `gx` 2000..5799 (3800 cols).

- **7,477,923 ocean cells/day**, of which **7,240,513 (96.8%) have a climatology**.
- 100°E rather than 120°E because CoralTemp is a coral-reef product and 120 clips the
  Coral Triangle and the Java/Banda seas.
- 65°N/60°S captures the Blob, the PDO domain, the Bering Sea, and the ACC at Pacific
  longitudes. Cutting the poles is also what lifts climatology coverage from 77.4%
  (global) to 96.8%.
- **All four Niño boxes are inside it** — 1+2, 3, 3.4, 4. The old OISST box was clipped at
  the equator and could not compute any of them; the repo is finally named for what it does.

Widening it needs no re-ingest: `gy`/`gx` index the *global* grid, so only `domain.yml`'s
`subset` block changes.

## The third state: ocean with no anomaly

About **3.2% of the box's ocean has SST but no climatology** — the seasonal ice fringe,
which the source flags explicitly (`mask` = 4). Those cells are neither land nor
zero-anomaly, and all three have to look different:

- land → **transparent** (the dark basemap shows through)
- no climatology → **flat grey** (`render.NO_CLIM_RGBA`, surfaced as `/domain`'s `noClimColor`)
- everything else → the variable's colour scale

Transparent would read as land; any scale colour would read as a real near-zero anomaly.
