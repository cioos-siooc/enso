# Map imagery

`shared/render.py`: value-encoded WebP frames, encoding and the categorical `mhw` layer.

## Map imagery (`shared/render.py`)

There is **no tile pyramid**. The Pacific box is one WebP, served as a Mapbox `image`
source with corner coordinates from `/domain`'s `imageBounds`.

**`imageBounds` longitudes are unwrapped**: the box's east edge is reported as **290, not
−70**. Mapbox accepts that and places the quad correctly across the antimeridian — verified
in Chromium, where `project([290,0])` and `project([-70,0])` return the same pixel.
Normalising east into −180…180 would make west > east and collapse the image source to
nothing. This is *not* the same question as the 0–360 storage convention; the box straddles
the antimeridian either way.

The source grid is linear in longitude but **not** in Mercator y, so `to_mercator()`
resamples the rows onto an evenly spaced Mercator axis. Linear blending propagates NaN from
either neighbour, which would erode a pixel of ocean along every coastline, so it falls
back to whichever side is real. The no-climatology mask is resampled **nearest-neighbour**
instead — it is categorical, and a blended edge has no sensible threshold.

### The images carry data, not colour

`/image` ships the **value packed into the RGB channels**, with land in alpha, and the
browser applies the colour ramp with Mapbox's `raster-color`. `shared/render.py`'s
`encode()` is the packer; `domain.yml`'s per-variable `encoding` block is the contract, and
`/domain` hands the frontend a ready-made `raster-color-mix` so the packing arithmetic is
written **once, in Python**, and never re-derived in TypeScript.

The reason is the retention window. The daily NetCDF is pruned, so a bucket's cached image
eventually becomes the only surviving copy of that field — and a pre-coloured cache would
have today's colormap and today's vmin/vmax welded into it permanently. Re-ranging the
anomaly from ±3 to ±4 would mean re-downloading the range. Value-encoded, the palette and
the displayed range are client-side settings for good.

| variable | channels | step | range | notes |
|---|---|---|---|---|
| `sst` | `G`,`B` → `G*256+B` | 0.01 °C | −5…650 | the source's own precision, lossless |
| `anom` | `R` | 0.1 °C | −12.8…+12.7 | code 0 = no climatology |
| `mhw` | `R` | 1 category | 0…255 | code == value; 0 and land both alpha 0 |

**Lossless WebP, necessarily** — lossy is YUV 4:2:0 and destroys packed data: measured at
q90 on a real frame, mean error 0.074 °C but **maximum 1.613 °C**, i.e. visible blotches.
It costs 2.3–2.7× the bytes (sst 1.14 MB, anom 0.50 MB at width 2048) and **decodes
slightly cheaper** than lossy — 41.8 ms vs 39.7 ms measured, no inverse DCT or YUV
conversion. Colouring is free: pan frame time is 16.6 ms with `raster-color` against
16.7 ms pre-coloured, both at the vsync ceiling under software rendering.

Three details that are load-bearing, all of which fail quietly:

- **`raster-resampling: nearest`, set in `AnomalyMap.vue`.** `sst` spans two channels, and
  linear filtering blends them *independently* — a texel pair straddling a low-byte wrap
  would decode ~2.56 °C away from either neighbour. Measured, nearest and linear are
  identical on the decode (median error 0.156 vs 0.159 °C, both just texel quantisation),
  and nearest is visibly cleaner at single-pixel islands, which linear renders as coloured
  speckle. So it costs nothing and removes the whole failure class.
- **Land is filled with nearby ocean values, not left at 0** (`_bleed()`). Mapbox filters
  the texture; a coastal texel blending ocean against a land 0 decodes to the bottom of the
  scale, giving a wrong-coloured fringe along every coastline. Land is cut by **alpha**,
  which is exact. Bleeding runs on the integer code, never the packed channels — averaging
  a low byte across a 255→0 wrap lands 256 counts out.
- **Values are clamped, never wrapped.** A uint8 overflow would redraw a record-warm cell as
  the coldest colour on the map. `anom`'s ±12.7 clips about **4 cells a day out of 7.5
  million** — measured over 60 days spanning the archive and the strong ENSO peaks, where
  the anomaly reaches −10.22…+14.05 °C — and every one of them is already saturated at the
  ±3 display range.

`raster-color` tabulates its ramp at **256 uniformly spaced steps over `raster-color-range`**,
so `/domain` sends a different range per variable — `Variable.color_range()` owns the
decision and `store.colorRangeFor` mirrors it. A variable whose *codes* must land one per
ramp entry tabulates its whole encoding range: `anom` (−12.8…12.7) so its sentinel gets a
slot of its own, and `mhw` (0…255) so that entry k is code k. Tabulating mhw's five classes
over 1…5 instead would put code 2 at entry 63.75, where a **Cat 2 picks up Cat 1's colour**.
`sst` has neither constraint and spends all 256 entries on the −2…32 display range.

### `mhw` is categorical, and three things follow

None of them fails loudly if it is skipped, which is why `domain.yml` declares
`categorical: true` and everything reads that flag rather than testing the name:

1. **The Mercator resample is nearest, not bilinear** (`to_mercator(..., nearest=True)`).
   Blending a Cat 2 against a Cat 4 invents a Cat 3 along every edge. Measured on
   2023-10-01 at width 2048: bilinear mis-categorises 3,072 cells (0.28% of shared ocean),
   but the bigger cost is that it **invents 42,088 heatwave pixels** — 3.9% more than exist
   — by blending a real category against the NaN of heatwave-free ocean and letting the
   NaN-fallback make the result opaque.
2. **The ramp is a `step`, not an `interpolate`** (`categoricalRamp` in `AnomalyMap.vue`),
   and the chart's `visualMap` is `piecewise` for the same reason. There is no colour
   between two classes because there is no value between them.
3. **The displayed range is not the user's.** The stops *are* the classes, so `ColorLegend`
   shows a named key instead of a gradient and a slider, `setScale` refuses a categorical
   variable outright (a stale `localStorage` entry must not be honoured), and `stopsFor`
   skips the re-spreading — which is currently the identity, and is skipped explicitly so
   it stays correct when a class is added.

**The palette is NOAA's own, measured rather than guessed.** Extracted from NOAA's plain
PNG for 2023-10-01 by matching every pixel against that date's NetCDF: all five categories
matched **100%**, as did the three non-heatwave classes (land `#969696`, ice `#ffffff`,
no-heatwave `#b3f2ff`) — which this project draws transparent instead. `domain.yml` lists
them as `colors` rather than naming a colormap; matplotlib has no say, because the point of
these five is that people already recognise them from NOAA's maps.

| cat | | colour |
|---|---|---|
| 1 | Moderate | `#ffff80` |
| 2 | Strong | `#ffb333` |
| 3 | Severe | `#ff8000` |
| 4 | Extreme | `#cc4d00` |
| 5 | Beyond extreme | `#991a00` |

Exact values remain the timeseries endpoints' job; this raster is for looking at.

`DEFAULT_WIDTH` is **2048**, and `front/app/composables/useApi.ts`'s `IMAGE_WIDTH` mirrors
it. The cache is keyed by (variable, period, bucket start, width), so **a width mismatch is
a 404 and a blank map, not a slower render** — there is no NetCDF left to render a
historical bucket from.

Renders are cached under `OISST_IMAGE_DIR` as
`{variable}/{period}/YYYY/{bucket-start}_w{width}.webp`.

**Colour ranges live in `domain.yml`**: `sst` is **sequential** (`turbo`, −2…32) and `anom`
**diverging** (`RdBu_r`, ±3). That distinction is not cosmetic — an absolute temperature has
no meaningful midpoint, so a diverging map would invent one at 15 °C and read as a signed
field. Since the images carry data rather than colour, changing either range or colormap now
only needs an API restart — **the image cache is not invalidated by a palette change.**

`vmin`/`vmax` are only where the scale **opens**: the displayed range is adjustable in the
browser (see the colour range control below), and `domain.yml`'s pair is the default and
what Reset returns to. The colormap is not adjustable — the ramp is matplotlib's, evaluated
server-side.

**`limits` is the span the user may drag that range over, and it is deliberately not the
encoding's.** `sst` packs into two bytes at 0.01 °C and can therefore represent −5…650 °C,
which is arithmetic rather than oceanography — a control bounded by it would spend 95% of
its travel above the boiling point. So `sst` declares `limits: [-2, 36]` (the freezing point
of seawater; 36 clears the warmest ocean SST anywhere, and this box peaks near 32) and
`anom` omits the key and falls back to its encoding, ±12.7, which is already physical.
`Variable.range_limits()` clips whatever is declared to what is encodable, and `/domain`
ships the result as `encoding.limits`.
