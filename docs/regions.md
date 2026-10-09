# Regions

The named regions: boxes, polygons, provenance and the masks.

## The first polygon region: `pacific_bioregions`

Fifteen named regions are polygons now (see "The global regions" and "Canadian waters" below). This one came first
and set the rules. Like the others, **`pacific_bioregions`** declares a
`polygon:` and no bounds — `shared/domain.py` derives its box from the ring, so a
hand-written box cannot go stale behind a changed geometry, and `shared/mask.py` cuts that
box down to the 26,222 cells actually inside. See `region_cells` below for the cost
of not doing this, and `shared/mask.py` for how a cell is decided.

**Provenance matters here in a way it does not for a Niño box, and it is why this region is
not called an EEZ.** A Niño index box is a convention anyone can write down; a maritime
limit is a legal instrument, and Canada and the United States do not agree about two pieces
of Canada's Pacific one — the Dixon Entrance A–B line in the north and the wedge off Juan
de Fuca in the south. The geometry is **Fisheries and Oceans Canada's `Federal Marine
Bioregions`** (open.canada.ca record `23eb8b56-dac8-4efc-be7c-b8fa11ba62e9`), the union of
the four bioregions it marks `OCEAN_E = Pacific`: **Offshore Pacific, Northern Shelf,
Southern Shelf, Strait of Georgia**. Reprojected from Canada Albers Equal Area Conic
(NAD83) to WGS84; the file records its own source, retrieval date and simplification.

**It was the Flanders Marine Institute's (VLIZ) Marine Regions v12 EEZ (mrgid 8493) until
2026-09-15**, which is the widely cited marine-science rendering and *not* the Canadian
authority. The two footprints agree almost everywhere and disagree exactly where the states
do — measured, cell by cell:

| | VLIZ v12 EEZ | DFO bioregions |
|---|---|---|
| mask cells | 26,158 | 26,222 |
| cells in common | 25,968 (99.3% / 99.0%) | |
| outer-ring area | 511,063 km² | 512,340 km² |
| bbox lat | 46.57…56.01 | 46.53…55.13 |
| Dixon Entrance N of the A–B line | **excluded** | **included** (152 cells at 54–55°N) |
| seaward of Juan de Fuca, past the median line | excluded | **included** (1,152 km², measured 2026-10-07) |

So the swap buys the Canadian reading of Dixon Entrance and costs a north-coast sliver
above 55°N plus an offshore edge near Haida Gwaii (190 cells in all). The DFO layer stops
at 55.13°N where the EEZ runs to 56.01°N, because a bioregion's seaward edge follows the
zone only where the zone is what bounds it.

**The catch, and it is the reason the label reads `Pacific Bioregions (DFO)` rather than
`BC EEZ`: this is a marine-planning framework, not a published maritime limit.** The
dataset's own description calls its boundaries fuzzy and revisable on ecosystem grounds.
Naming it for the zone would put a bioregion behind a legal instrument's name, which is the
same class of misattribution as crediting NOAA with the Hobday definition. (The earlier
note here that "DFO's Open Maps does not publish the limit as a standalone vector" still
stands — it does not. This is not that limit; it is the closest Canadian-authority
footprint of the same water.)

Two things about the stored file. It carries **outer rings only** — the 362 interior
rings are islands (Vancouver Island at 31,840 km² and Graham Island at 6,499 km² the
largest), and land is cut by `sst_daily` holding ocean cells, not by the geometry, which
also keeps the outline clean on the map. And it is **Douglas–Peucker simplified at 0.002°**,
a twenty-fifth of a grid cell: measured, that moves **15 of 26,223 cells** against the
unsimplified ring, and takes 11,131 vertices to 4,573 (104 KB). The union is a
**MultiPolygon of two** parts — the second is a 20-vertex sliver of Boundary Bay at
49.0–49.09°N, detached from the main body by the Point Roberts peninsula.

## The global regions (added 2026-10-02)

Twelve regions came with the global grid, and nine Canadian ones after it (see "Canadian
waters" below). There are 29 in all, listed in the region menu under five headings that `domain.yml`'s `region_groups` declares; each region names its
heading in `group:`, and `regions()` raises on a heading that isn't declared.

| group | box (a convention, so a box by definition) | polygon (a published outline) |
|---|---|---|
| Ocean basins | `global`, `southern` (S of 60°S) | `pacific`, `n_atlantic`, `indian` — Marine Regions *Global Oceans and Seas* v1 |
| ENSO and its relatives | `iod_west`, `iod_east` (Saji 1999), `atl3` (20°W–0, 3°S–3°N) | |
| Marine heatwave hotspots | `w_australia` (Ningaloo Niño, 22–32°S 108–116°E) | `tasman_sea`, `mediterranean` (IHO S-23 via Marine Regions), `gulf_of_maine` (SeaVoX), `coral_triangle` (MEOW) |
| Canadian waters | | `pacific_bioregions` and seven more — DFO *Federal Marine Bioregions* |

The rule is the one `pacific_bioregions` set: an index box is a convention anyone can write
down, so it is a box; a named sea is someone's outline, so it is a polygon whose file records
its source, licence, retrieval date and simplification, and whose label names that source.

- **`southern` is a box although GOaS publishes it.** GOaS's Southern Ocean is everything
  between 60°S and the Antarctic coast, and the coast is land, which `sst_daily` already
  excludes. The polygon would select the same cells, and its ring is cut at the antimeridian.
- **`mediterranean` is nine IHO sea areas unioned**: the Western and Eastern Basins plus
  Alboran, Balearic, Ligurian, Tyrrhenian, Adriatic, Ionian and Aegean. GOaS's
  "Mediterranean Region" was not used because it includes the Black Sea.
- **`coral_triangle` is not the Coral Triangle Initiative's boundary.** Neither the Veron
  et al. scientific boundary nor the CTI implementation area is published as a downloadable
  polygon. This is the union of MEOW's (Spalding et al. 2007) Western and Eastern Coral
  Triangle provinces, which are shelf bioregions, so it omits the deep basins inside the
  triangle. That is why the label says `(MEOW)`. **MEOW's licence was not checked**; the
  file says so.
- **The outlines are simplified at 0.05° for the two basins and 0.005–0.01° for the seas.**
  The cells that moves, measured against the unsimplified ring, are 0.25% (North Atlantic),
  0.12% (Indian) and ≤0.2% elsewhere, mostly coastal. Each file's properties record the
  tolerance and the count. Without API gzip the North Atlantic outline is 200 KB.
- **The masks were cross-checked against shapely**: `CRW.cli mask`'s counts (n_atlantic
  1,703,875, indian 2,823,600, coral_triangle 286,146, tasman_sea 140,617, mediterranean
  106,240, gulf_of_maine 4,213) equal shapely's `contains_xy` on the same rings, cell for
  cell. There is no build script in the repo; the scratch script that made the files is
  described by their `properties`.

**Rollup cost, measured on dev (NVMe):** `rollup --clim --fresh` took 33 min for all
twelve new regions, 21 of them for `global` alone, which scans all 262 B `sst_daily` rows.
The small boxes take seconds each and the two basin polygons 3–5 min. One date across all
22 regions, which is what `run` appends daily, takes **9.4 s** including container start.
Expect the full rebuild to be much slower on the production HDD.

**That per-date figure grew with the year, and the cause was the sort key**: `ORDER BY (gy,
gx, date)` cannot prune a single date, so each region's one-date rollup read its share of the
whole current-year partition (the `global` region alone: 4.64 B rows, 34.6 GiB uncompressed,
for 17.2 M). By 2026-10-08 it was **33.5 s** a date on dev for the 29 regions. The fix is the
`*_recent` tables below: **5.0 s**, identical rows.

### A region can cross the prime meridian, and its longitudes then wrap

**`Region.gx_range()` returns `(west, east)`, not a sorted pair, and `west > east` means
two column ranges.** The Mediterranean (−5.4…36.2) and the North Atlantic (−98…12) cross
0°. While every region was Pacific, `gx_range` sorted its pair, and for these it would
have **selected the complement**: every longitude the region does *not* cover, as a
plausible-looking area mean. So:

- **Longitudes are written unwrapped, west before east** (`-6..36`, not `354..36`), and
  `regions()` raises on a pair that runs the wrong way, so a typo can't pass as a wrap.
- **`region.gx_sql(grid)` writes the `gx` half of every region `WHERE`**:
  `gx BETWEEN` for a normal box, `(gx >= west OR gx <= east)` for a wrapping one. Use it,
  never a bare BETWEEN. ClickHouse turns either into key ranges within each `gy`.
- `gx_columns()` lists the columns west to east across the wrap. That is what
  `shared/mask.py` meshes over.
- **`atl3`'s east edge is 359.975, not 360.0.** 360.0 rounds to gx 0 and would wrap the
  box one column across the meridian.
- Verified on 2023-07-25 for `mediterranean`: the rollup's 28.151 °C, 102,752 cells and
  91.4% heatwave extent equal a direct query with no `gx` prefilter at all, and 3,794 of
  those cells are west of 0°.

**`shared/mask.py` is a scanline fill, not matplotlib's `contains_points`.** The old test
costs cells × vertices, which was milliseconds for `pacific_bioregions` and would have
been hours for the North Atlantic (3 M cells, ~9,000 vertices). The scanline gives the same
centre-in-ring answer, decided per row; it matches the matplotlib result exactly on all
four outlines it was compared on. **Its longitude frame is centred on the box, not started
at the west edge.** The box's first column can sit half a cell west of the ring, and a frame
starting at the edge wrapped that cell 360° east. That made `pacific_bioregions` 26,224
cells instead of 26,222 until it was fixed.

**Every region must say why it is there, and cite it.** Each declares `about: {why,
definition, references}` in `domain.yml`, and `regions()` raises on a missing block, an
empty field, no references, or a reference without an https URL. A polygon region's outline
source is read from its GeoJSON `properties`, not restated. An info button beside
the region menu (`ScopeControl.vue`) opens it in a popover (`RegionNote.vue`), fetched on
first open from `/region/{key}/about`, because the ~20 KB of text would nearly double `/domain`. Every DOI was
checked against Crossref on 2026-10-05. Where a box is this project's own rather than a
published index (`ne_pacific`, `gulf_of_alaska`, `bering_sea`), its `definition` says so,
and `pdo_north_pacific`'s says its mean is not the PDO index.

**Whole-circle boxes (`global`, `southern`) draw no meridian edge.** Their west and east
sides meet, so `FieldMap.regionPolygon` keeps the polygon for the fill and outlines only the
parallels. Without that, a seam was drawn down one meridian.

## Canadian waters (added 2026-10-07)

**Eight regions under the `canada` heading, all from DFO's *Federal Marine Bioregions***, the
same dataset `pacific_bioregions` came from (Open Government Licence – Canada):
`pacific_bioregions` (moved here from North Pacific), `scotian_shelf`, `gulf_st_lawrence`,
`nl_shelves`, `hudson_bay`, `eastern_arctic`, `western_arctic`, `arctic_basin`. Three of
the dataset's thirteen are not here:

- **Arctic Archipelago**, removed at the user's request. It is ice on every day of the
  1991–2020 climatology (no anomaly ever) and has never had a heatwave day, so it showed
  only a flat SST near −1.7 °C.
- **A union of all twelve** (`canada`), also removed at the user's request. It would need
  its own ~260 KB outline and held ~10,400 ocean cells none of its parts did, on Arctic
  islands a bioregion boundary cuts in two.
- **The Great Lakes**: CoralTemp counts all of them as land (Superior, Michigan, Erie and
  Winnipeg checked in the ocean mask).

**Where a boundary is disputed, the regions follow Canada's position, and DFO's file
already draws it that way.** Measured against Marine Regions' EEZ layer, which splits each
unsettled Canada–US stretch on a median line of its own:

| | DFO outline | measured |
|---|---|---|
| Beaufort Sea | the 141°W meridian, Canada's claim | covers 21,581 km² of the 24,772 km² overlapping-claim area; the rest lies beyond Canada's own 200 nm limit |
| Dixon Entrance | the A–B line | water north of it included |
| seaward of Juan de Fuca | past the median line | 1,152 km² of Marine Regions' US side included |
| Machias Seal Island, North Rock | inside `scotian_shelf` | 416 km² of the grey zone included |

The region notes in `domain.yml` say so for each one. **Do not swap in an outline that
splits these on a median.** Two places where DFO draws *less* than Marine Regions are not
disputes. Seaward of Dixon Entrance (1,679 km²), Marine Regions' line is its own
placeholder median, not a US claim. In the Lincoln Sea (1,433 km²), the Canada–Denmark
agreement of June 2022 settled the boundary, and DFO's file (last modified 2022-04-20)
predates it.

- **Saint-Pierre et Miquelon is a hole, not an island**, and it is why `Region.holes`
  exists. That boundary is settled (1992 arbitration). The convention of dropping every
  interior ring would have put France's zone (590 ocean cells, its corridor included)
  inside `nl_shelves`. The loader honours whatever interior rings a file stores, and the
  build stores only that one. Every other file stores none.
- **Built** with the Pacific file's method: reprojected from Canada Albers with the edges
  densified at 2 km first, island holes dropped, parts holding no cell centre dropped,
  simplified at **0.005°**. That moves 0.07–0.37% of cells; each file's properties record
  the tolerance and the count. The masks equal shapely's `contains_xy` on the stored
  rings, holes included, cell for cell.
- **Ocean cells** (CoralTemp's own, from the rollup): arctic_basin 152,614 · hudson_bay
  84,083 · eastern_arctic 76,232 · western_arctic 56,998 · nl_shelves 54,901 ·
  scotian_shelf 18,365 · gulf_st_lawrence 12,174.
- **The Arctic regions barely have an anomaly.** The 1991–2020 climatology has nothing under
  ice, so `anom` there averages only the few ice-free cells, on the days there are any:
  days a year with a climatology are 366 for scotian_shelf and nl_shelves, 278
  gulf_st_lawrence, 234 eastern_arctic, 152 hudson_bay, 67 western_arctic (127 cells on
  average) and 2 arctic_basin.
- **`mhw` extent is diluted by ice**, since ice is in the denominator: arctic_basin has had
  5 heatwave days and western_arctic 652.
- **Rollup cost on dev:** `rollup --clim --fresh` for all of them took about a minute.
- **No build script is in the repo**; the files' `properties` describe how they were made.
