# Land data: NOAA CPC Global Unified

The land archive, its tables, climatology, rendering and the frontend overlay.

## The land archive: NOAA CPC Global Unified

**A fourth archive, from a different NOAA program**, added so the dashboard can show what
an El Niño does *on land* beside what it does to the ocean — a dry Indonesia and northern
Australia, a wet Peru and Ecuador, a warm winter in western Canada. It is the Climate
Prediction Center's gauge-and-station analysis, not Coral Reef Watch's, which is why it
lives in its own package (`process/CPC/`, `python -m CPC.cli`) rather than under `CRW`.

```
https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{YYYY}.nc
https://downloads.psl.noaa.gov/Datasets/cpc_global_temp/{tmax,tmin}.{YYYY}.nc
```

Public domain, no login. `psl.noaa.gov/thredds/fileServer/Datasets/...` serves
byte-identical files and is the fallback host.

**ONE NETCDF PER YEAR, not per date**, and that is the structural difference everything
else follows from. `precip.2015.nc` holds all 365 days as `(time, lat, lon)` float32, ~63 MB;
`tmax`/`tmin` are ~58–90 MB. So `CPC.cli` takes **years** where `CRW.cli` takes dates,
`shared.fields.read_land_year` opens a file once and the ingest slices days out of the
resulting stack, and `run` has **no catch-up watermark**: "what is new" is simply the dates
in the current year's file that status does not have, so a missed run, a late publication
and a normal day are one code path with no argument.

**The year files are a staging area, not an archive.** Every map frame is pre-rendered and
the API never renders, so a file is needed only until its days are in ClickHouse and every
frame they feed is in the image cache. `CPC.cli prune` (and the end of every `run`) deletes
a `(product, year)` only once **both are checked**: status has every day in the file, and
the cache has every bucket of every layer the product feeds, at each declared period,
including the week that starts in the previous December and the anomaly layers. So nothing
is pruned before `clim` has been built and rendered from. A kept year is logged with its
first missing day or frame. `CPC/prune.py` holds the check.

**The current year's file is rewritten in place** as days are appended (`history: Updated
2026-09-17`), at ~2 days' latency. A past year is immutable — `tmax.2015.nc` was last
modified in 2020. So `run` downloads the current year afresh each day (~60–90 MB a
variable), plus the previous one while the recheck window's week or month still reaches
into it, and deletes them again at the end.

**What pruning costs:** rebuilding the climatology needs 1991–2020 back on disk, and
re-rendering old history (a palette-independent change such as the encoding or the coastline
cut) needs its years. Both are a re-fetch, ~9.5 GB for the whole record. The
`climatology/*.clim.nc` files are never pruned.

### Its two orientation conventions are the opposite of CoralTemp's

Both are applied in `shared/fields.py`, like the ocean's, and `_check_land_axes` verifies
both against the **file's own `lat`/`lon` variables on every read** rather than trusting
either. That is exact where the ocean side's `check_orientation()` is heuristic, and it is
warranted, because these two are easy to get backwards:

1. **Longitude: already 0–360** (`lon 0.25 … 359.75`). This is the one source in the project
   that must **not** be rolled. Copying the habit every other reader here has would draw the
   Pacific over Africa.
2. **Latitude: north-up** (`lat[0] = +89.75`), so it **must** be flipped — the same flip the
   CoralTemp climatology files get, and the opposite of the CoralTemp dailies.

The grid is `domain.yml`'s **third** block, `land`: 0.5°, 360×720, south-up on the project's
convention. **Land is global; the Pacific `subset` is the ocean's box and does not apply.**
The tables, the climatology and every array `shared/fields.py` returns cover the whole grid
(`domain.land_shape()`); only the land **image** is cropped, by `land_image` (60°S–85°N).

Measured globally: **~62,900 cells/day carry temperature (55°S–83°N) and ~93,000 carry
precipitation**, a quarter of it Antarctica, which is stored and not drawn. The two are not
the same land — Darwin has rainfall and no temperature — which is why there are two tables
and not one. (It was the Pacific box until 2026-09-18: 20,878 and 22,952.)

**Some days are empty, and that is the source, not a bug.** Measured over 1985–2026:
temperature has **16 days with no cells at all** (10 in 1985, 5 in 1986, 1992-07-31), and on
those same days rain drops from ~93,000 cells to ~15,600. Rain is empty on one day,
2007-02-26. They ingest as `success_ingest` with `n_rows = 0` (or few), so `prune`'s
status check passes, and their daily frames render **fully transparent**: the layer shows
nothing and no reason is printed. Weekly and monthly means simply average the days present.
`render._bleed` returns zeros for a frame with nothing opaque; it used to take the median of
an empty set and kill the whole render pool on 1985-01-01.

### `land_temp_daily` and `land_precip_daily`

**`gy`/`gx` in these two tables index the LAND grid, not the global 0.05° one.** Same column
names, entirely different meaning: `gy = 60` is 59.75°S here and 86.975°S in `sst_daily`.
This is the most likely way for someone to read them wrong. Nothing joins a land table to an
ocean one and nothing should.

| | |
|---|---|
| `land_temp_daily` | `tmax_raw`, `tmin_raw` Int16 at 0.01 °C; `tmean` ALIAS `(tmax_raw + tmin_raw) * 0.005` |
| `land_precip_daily` | `precip_raw` UInt16 at **0.1 mm** |
| rows | **1.00 B and 1.41 B** over 1985→ (global), against `sst_daily`'s 113.7 B |
| on disk | **3.14 GiB and 629 MiB** — 3.8 GiB together, against 1.3 GiB for the Pacific box |
| ingest cost | ~40 s per year for temperature, ~75 s for rain with a render running; a full `backfill --fresh` was ~85 min |

**Both temperature columns are stored and the mean is derived.** An ALIAS costs no storage,
`tmin` has to be downloaded to compute a mean anyway, and the two questions ENSO actually
raises on land are a `tmin` one (a warm winter in western Canada) and a `tmax` one (a heat
extreme) — neither survives the average. Temperature ingests only cells valid in **both**;
measured, the two masks are byte-identical on every day checked, and a day where they
diverge is logged rather than half-stored.

**Precip is 0.1 mm in a UInt16, deliberately not 0.01.** At 0.01 mm a UInt16 caps at
**655.35 mm** against a measured global maximum of **666.69 mm** and a declared `valid_range`
of 1000 — it would have clipped real values, at exactly the extremes a rainfall map is read
for. `to_precip_counts` raises on an overflow rather than clipping, for the same reason
`shared/render.py` clamps rather than wraps.

**Both tables are dense, and a stored 0 is a real reading.** A dry day over Darwin is 0.0 mm
and belongs in the table. A sparse precip table would save about half the rows (42–56% of
land cells are wet on a given day, measured) and would buy that by making an absent row mean
"dry", "outside the gauge network" or "never ingested" indistinguishably — `mhw_daily`'s
trap, with no `sst_daily` equivalent to LEFT JOIN against for the answer.

**Unlike CoralTemp, `remote_size`/`remote_modified` in `land_*_status` describe the YEAR
FILE**, not the date's own file. Every date in 2026 shares one pair, and that pair changes
daily. They answer "is this year worth fetching again", not "was this date revised" — a
revision inside an unchanged-length year file is invisible to them, which is what
`run --recheck-days` (default 14) exists for.

### The download host fails at HTTP 200

`downloads.psl.noaa.gov` served a **497-byte nginx "currently unavailable" page** in place of
`tmin.2026.nc` during development; the next request for the same URL returned the real 58 MB
body. `raise_for_status()` does not catch that, and `.part`-and-rename alone would have
promoted the page to a real filename, where it would have surfaced days later as an
unreadable NetCDF blaming the ingest. So `CPC/download.py` **validates the body before the
rename** — HDF5/NetCDF magic bytes, then length against `Content-Length` — retries with a
backoff, and falls back to the THREDDS host. These files are HDF5 (`\x89HDF`), not classic
NetCDF.

### The land overlay: seven layers, drawn over the ocean

**A map overlay, not a fourth ocean variable.** It is drawn over whichever ocean variable
is showing, with its own legend, so El Niño's ocean anomaly and its land response are on one
map. The stats and rankings stay ocean. **The chart does not**: with the overlay on, a pin
on land plots the overlay's layer at that cell from `POST /landTimeseries` (see below).
`/timeseries?variable=land_*` still 422s by design (`LandVariable` is its own Literal).

| layer | source | bucket | encoding | periods |
|---|---|---|---|---|
| `land_tmax` / `land_tmin` | tmax / tmin | mean of the dailies | G,B · 0.01 °C · −100 | d/w/m |
| `land_precip` | precip | mean **mm/day** | G,B · 0.01 mm · 0 | d/w/m |
| `land_tmax_anom` / `land_tmin_anom` | tmax / tmin | mean of (value − normal) | G,B · 0.01 °C · −327.68 | d/w/m |
| `land_precip_ratio` | precip | **log2(mean ÷ normal)** | R · 1/32 · −4, sentinel 0 | **w/m** |
| `land_precip_anom` | precip | mean of (value − normal), mm/day | G,B · 0.01 mm · −327.68 | **w/m** |

**What a layer is made of is declared, not coded.** `domain.yml` gives each `grid: land`,
`source`, `transform` (`none` | `difference` | `log2_ratio`), `periods`, `resampling:
nearest`, and for the ratio `min_normal` and `display: log2_percent`. `shared/buckets.py`
reads those fields, so there's no name table to drift. `_check_layer` in `shared/domain.py`
rejects a declaration that would fail far away: an unknown transform, a land layer with no
source, a ratio with no sentinel.

Decisions, each measured first (see ROADMAP.md B6 for the numbers):

- **Rain's anomaly is log2(actual ÷ normal), printed as percent** (`utils/land.ts`:
  −1 → 50%, +1 → 200%). The absolute departure's middle 50% is −17…+12 mm/month with a tail
  to 7,812 mm, so no one scale works. Linear percent squeezes every drought into 0–100%. A
  bone-dry bucket is floored at 2⁻⁴, not sent to −∞.
- **A normal below 0.1 mm/day draws the sentinel grey**, 7% of the box's land in January.
  It's the ocean's `NO_CLIM_RGBA` third state, and it means the same thing: a value exists,
  a meaningful departure doesn't. `noValueLabel` in `/domain` says which reason applies,
  because the colour is shared.
- **Precipitation has two anomalies, and the ratio is the default.** The Layers card offers
  `% of normal` and `mm vs normal` beside `Value` (`landMode` `anomaly` / `difference`; a
  temperature has only the first, and `landModeFor` maps `difference` onto it). The ratio says
  how unusual a bucket is for that place; the mm departure says how much water went missing,
  which the ratio hides in a desert at 300% of almost nothing. Measured, a month's departure is
  within ±1.6 mm/day over 90% of land cells, so it opens at ±3.
- **It is precipitation, not rain**, in every label: CPC's gauge analysis counts snow as its
  liquid-water equivalent.
- **Precipitation anomalies are weekly and monthly only.** A daily rainfall anomaly is noise; a daily
  temperature anomaly (a heatwave day) isn't. `/image` answers **400** for a period outside
  `periods`, not 404, because it's a request error rather than a missing frame.
- **Land anomalies are wider than the ocean's**: ±8 by default against ±3. The within-month
  spread of tmax is ~5 °C north of 45°N. Two legends, never one.

### The land climatology: computed here, smoothed, and self-describing

`CPC.cli clim` builds `data/land/climatology/{tmax,tmin,precip}.clim.nc` from the year
files for 1991–2020. It never reads ClickHouse, and it takes minutes. **It needs those 30
years on disk, so build it before `prune`**, which refuses anyway while anomaly frames are
missing. The shape is `(366 MMDD keys incl. 0229, 360, 720)`, south-up, ~80–106 MB a file,
~100 s for all three.

- **Smoothed over the day of year**, by each layer's `baseline.window_days`: **15 for
  tmax/tmin, 7 for rain**. Temperature needs it because a raw per-calendar-day mean over 30
  years flickers into every daily anomaly. Rain is only drawn weekly and monthly, where the
  bucket already smooths, so 7 days blurs a month's normal by only ±3 days and a monsoon onset
  keeps its month.
- **Sums and counts are windowed separately**, so the mean is sample-weighted: 0229 has 8
  years of data, not 30. The window is circular, so 31 December's window reaches January.
- **A missing baseline year raises.** A 29-year "1991–2020" is a different baseline under
  the same label.
- **The file records its period and window, and `read_land_clim` raises on a mismatch** with
  `domain.yml`. Edit a window, rebuild with `CPC.cli clim`, then re-render. Otherwise the
  anomaly layers refuse to render rather than serve the old normal under the new label.
  `/coverage.land.layers` reports each anomaly layer as not ready until the file matches, and
  the frontend disables the button.

### The land frames are cut to CoralTemp's coastline

**This is how the land and ocean rasters avoid overlapping.** Layer order can't do it. The
Mapbox style is `background → country-boundaries → boundary lines → labels`, and
`country-boundaries` is a **fill**: the style's only land. The ocean raster sits below it,
which is what clips the ocean to the coast and keeps `mhw`'s calm-ocean fill off the
continents. The land raster has to sit **above** it or it's hidden (`landBeforeId()` puts it
directly above, below the lines and labels). There, its 0.5° blocks would paint ~55 km out to
sea along every coast, and on open water under `mhw`.

So `render.encode()` ANDs a land layer's alpha with CoralTemp's own land at 0.05°, and inside
the Pacific box with **the complement of the ocean rasters' own footprint** too. Both come
from `shared/masks/coraltemp_ocean.npz`, a committed **global** artifact (116 KB, 17,193,140
ocean cells, of which the box's 7,477,923 are bit-identical to the old box-only mask), rebuilt
by `CPC.cli ocean-mask`. CoralTemp's land is constant (byte-identical across three days
checked), so one day's mask is every day's. It's committed rather than computed because land
frames are rendered long after the CoralTemp dailies have been pruned.

**The footprint, not a nearest-sampled mask.** The continuous ocean layers resample
bilinearly with a fallback that keeps the real neighbour, so their coast sits one pixel
landward. A nearest cut overlapped them in **11,987 pixels**; the footprint cut overlaps in
**0**, measured on real frames under both `sst` and `mhw`. `mhw`'s nearest footprint leaves a
one-pixel seam of basemap land, which reads as a coastline, not an overlap.

### The land frame is the ocean frame's pixel grid, carried round the globe

`render.land_canvas()` builds it: the ocean frame's pixel width in degrees, its Mercator row
pitch and its south edge, stepped out to just inside ±180° and up to just under 85°N. At
`w2048` that's **3,880 × 2,747 px**, `landImageBounds` in `/domain` (−179.99…179.97,
−60…84.995). The cache key's width is the **ocean** frame's, so a `w2048` land frame is 3,880
px wide. The land field is sampled nearest onto it (`land_to_canvas`), so 0.5° cells draw as
blocks.

**Why the grids have to agree:** the no-overlap cut works pixel for pixel, and west of the
dateline the two grids are the same grid, so the cut tiles the rasters exactly (0 overlap).

**Why the frame stops at ±180° anyway, and what that costs.** The obvious design, the ocean
frame extended in both directions to ~−30…330°, keeps the grids identical everywhere, but
**Mapbox draws a 360°-wide image source only in the world copy nearest the camera** —
measured in flat projection: with the camera on Asia the Americas were missing, and explicit
copies at ±360 changed nothing. A frame inside ±180 draws whole everywhere and needs no globe
west copy. But 360° isn't a whole number of the ocean's pixels, so **east of the dateline the
two grids are offset by a fixed fraction of a pixel**. There `_land_cut` makes a land pixel
clear **both** ocean pixels it straddles, leaving at most a one-pixel strip of basemap land
along the Americas' Pacific coast. Not visible at zoom 5 over Peru. `test_land.py` checks the
no-overlap rule geometrically, column by column.

### The frontend overlay

- **Controls: the map's top-left Layers card (`LayerControl.vue`)** holds the ocean
  variable and the land overlay as two rows, so both "what is drawn" choices sit together;
  the time bar holds only "when", plus swipe compare's second date. The second place (B)
  sits beside the scope control on the map.
- **State**: `store.landLayer` (`tmax` | `tmin` | `precip` | null) and `store.landMode`
  (`value` | `anomaly` | `difference`), independent of `store.variable`. `landVariable` maps the pair to a
  layer name (`utils/land.ts`). `landReasonAt(date)` says why a bucket can't be drawn: the
  period isn't declared, the climatology isn't built, or the date is past **that product's**
  coverage, since temperature and rain end on different days.
- **When a bucket can't be drawn, the layer is REMOVED, not left on its last frame.**
  Mapbox's image source keeps the previous image on a 404, which would show last week's rain
  under this week's date. The land legend prints the reason in its place.
- **`Match ocean` puts land on the ocean's colour range** (the land legend's link toggle,
  `store.scaleLink`, remembered as `enso.scale.link`). Offered only where `scalesLinkable`
  holds — same units, both continuous, **identical served stop colours** — so today
  `sst` ↔ `land_tmax`/`land_tmin` and `anom` ↔ `land_t*_anom`, never precipitation. Every
  scale getter resolves through `scaleOwner()`, so the map, both legends and the chart's
  land line follow it together; while linked the land popover edits the ocean's range
  (bounded by the ocean's `limits`), and the land layer's own override is kept for when
  the link is turned off. Event `color_scale_linked` (`on`, `land`, `ocean`).
- **`ColorLegend` takes a `variable` prop.** The land instance is labelled "Land", formats
  `log2_percent` ticks and number fields as percent while ranging in log2, and reads its grey
  row's text from `noValueLabel`. The scale machinery takes `LayerName`, so each land layer
  has its own remembered range (`enso.scale.land_*`).
- **Playback awaits the land frame as well as the ocean's.** URL keys are `land=` and `lm=`.
  `View`/`applyView` carry them, so a link can set the overlay. Swipe compare needs
  nothing: each `FieldMap` draws its own land for its own date.
- **One quad in both projections.** The land frame sits inside ±180, so it never needs the
  ocean raster's globe west copy, and must not cross 180 (see above).
- **Cost, measured** (global): reduce 0.01–0.5 s, encode ~0.5–2 s alone, **~120 KB (rain) to
  ~190 KB (temperature)** a frame. The whole archive, measured: **92,230 frames, 16 GB, 6 h**
  on 24 workers (with the global re-ingest running for the first hour and a half). For the
  Pacific box it was 27–56 KB a frame.

### Charting a land cell

**`POST /landTimeseries`** (`api/modules/land.py`) takes the overlay's layer name and
returns a point series on the **land** grid. Three things about it:

- **"Land" is CoralTemp's land at 0.05°**, via `global_ocean_mask()`, not "a CPC cell with
  data". A click on drawn sea answers 200 with no values and `surface: "ocean"`, even where
  a 0.5° block overhangs it. So a click's ocean and land series partition it: exactly one
  has values, and the frontend fetches both and plots whichever came back.
- **A bucket is `_land_bucket`'s, cell for cell** (mean, mean of differences, log2 of the
  ratio of means with the floor and the `min_normal` null), reduced in Python because the
  normal lives in the `.clim.nc` file, not ClickHouse. Verified against `bucket_field` on
  four layer/period cases, equal to the layer's precision. `read_land_clim_cell` reads one
  column of the file; it is chunked a day per chunk, so a cold cell is ~0.9 s and the API
  caches 512 cells per worker.
- **An undeclared period or an unbuilt climatology is a 400** with the reason in `detail`;
  the store's `landChartReason` says the same without the request.

In the store, `landPins.{a,b}` hold each pin's land series, refreshed by `refreshLand()`
from every path that refreshes the ocean ones plus the land control. `TimeseriesChart`
draws land on a **right-hand y-axis** (`Land °C`, `Land mm/day`, `Land % of normal`),
ocean on the left, and only the right one when every line is land. One line is coloured by
its own layer's ramp; two are coloured by pin, as before.

**Not built yet on the land side:** land stats cards and rankings, a `land_clim` table,
region rollups, SPI, the 1979 extension, and a more compact two-legend layout on a
phone, where the pair covers about half the map. See ROADMAP.md B6.
