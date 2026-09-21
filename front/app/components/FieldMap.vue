<template>
  <!-- Two elements, not one: Mapbox adds `.mapboxgl-map` to its container, and that
       unlayered `position: relative` beats a layered Tailwind `absolute` passed in by
       the host. On one element the compare map fell in below the primary, out of
       sight, and both halves of the divider showed the primary's date. -->
  <div>
    <div ref="container" class="size-full" />
  </div>
</template>

<script setup lang="ts">
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { useMainStore, type DomainMeta, type LayerName } from '~/stores/main'
import type { ColorStop } from '~/utils/colorScale'
import { GLOBE_VIEW, type CameraView, type ProjectionName } from '~/utils/mapView'

/**
 * One Mapbox map drawing the field for one date.
 *
 * Everything that decides WHAT is drawn except the date — variable, period,
 * colour range, the selected cell and region — is read from the store, so two
 * of these side by side (see `AnomalyMap`'s swipe compare) cannot disagree
 * about anything but the one thing they are there to compare. The date is a
 * prop for exactly that reason: it is the only input the two maps do not share.
 *
 * Framing the camera is the host's job, not this component's. In compare mode
 * the second map follows the first, and two components each deciding where to
 * fly would fight.
 */
const props = defineProps<{
  /** Bucket start to draw. `store.selectedDate` for the main map. */
  date: string | null
  projection: ProjectionName
  /** Where to open. Omitted, the projection's own default view. */
  initialView?: CameraView
  /** Registers the dev-only `window.__map` handle; the compare map does not. */
  primary?: boolean
}>()

const emit = defineEmits<{ ready: [map: mapboxgl.Map] }>()

const store = useMainStore()
const api = useApi()
const token = useRuntimeConfig().public.mapboxToken

const container = ref<HTMLElement | null>(null)
let map: mapboxgl.Map | null = null
let marker: mapboxgl.Marker | null = null
let resize: ResizeObserver | null = null

const SOURCE_ID = 'field-image'
const LAYER_ID = 'field-layer'

/**
 * The same frame, placed one world to the west — the globe's other half.
 *
 * Mercator draws world copies, so a single quad at 100..290 crosses the
 * antimeridian and is drawn whole. **The globe has no world copies**: measured
 * in Chromium, that quad clips dead at 180 and the entire eastern Pacific goes
 * missing. Placing the identical image a second time at -260..-70 puts the other
 * half where it belongs; each source draws only the part of itself that falls
 * inside -180..180, so the two abut at the dateline and never overlap.
 *
 * It is added on the globe only. In Mercator both quads resolve to the same
 * ground, and two layers at 0.85 opacity would double up into a darker box.
 */
const WEST_SOURCE_ID = 'field-image-west'
const WEST_LAYER_ID = 'field-layer-west'
const WORLD = 360

/**
 * The flat colour under the field layers, for a variable whose "no value" is a
 * class rather than a gap.
 *
 * `mhw` is the one that has one. Its WebP holds land, ice AND heatwave-free
 * ocean at **alpha 0** alike — `encode()` sees NaN for all three — so no code 0
 * ever reaches `raster-color` and the ramp has nothing to paint it with. The
 * source alpha also wins over the ramp's, so there is no expression that could
 * bring it back. A fill under the raster is what is left.
 *
 * It is exact only because the basemap's land sits ABOVE the field layers in
 * this style: the fill covers the whole image quad, and the land drawn over it
 * cuts it back to the ocean, which is the only place category 0 means anything.
 * Move the raster above the land layer and this paints the continents blue.
 *
 * One source, one layer, both quads: on the globe the field is drawn twice (see
 * `WEST_SOURCE_ID`), and the fill follows it as a second polygon in the same
 * FeatureCollection rather than a second layer to keep below.
 */
const BACKGROUND_SOURCE_ID = 'field-background'
const BACKGROUND_LAYER_ID = 'field-background-layer'

const REGION_SOURCE_ID = 'region-box'
const REGION_FILL_ID = 'region-box-fill'
const REGION_LINE_ID = 'region-box-line'
/** Amber, matching the chart's MAP markLine — "where the app is looking". */
const REGION_COLOR = '#05df72'

/**
 * The land overlay: a second raster, over whichever ocean variable is showing.
 *
 * **Where it sits in the stack is not a free choice.** This style's only land
 * is `country-boundaries`, a FILL, and the ocean raster is inserted below it —
 * which is what clips the ocean to the coast and keeps `mhw`'s calm-ocean fill
 * off the continents. The land raster therefore has to go ABOVE that fill or it
 * is hidden, and below the boundary lines and labels. See `landBeforeId`.
 *
 * It does not overhang the sea despite its 0.5-degree cells, because its frames
 * are cut server-side to CoralTemp's own 0.05-degree coastline — the complement
 * of the ocean rasters' footprint, measured to overlap them in 0 pixels. So the
 * two tile exactly, and no ordering trick is needed between them.
 */
const LAND_SOURCE_ID = 'land-image'
const LAND_LAYER_ID = 'land-layer'

/**
 * Whether the style has finished loading and layers may be added.
 *
 * Tracked here rather than asked of Mapbox: `isStyleLoaded()` answers a
 * different question — whether every source has settled — and is routinely
 * false on a fully drawn map.
 */
let styleReady = false

/** Move (or create) the pin marking the selected cell. */
function showMarker(lat: number, lon: number) {
  if (!map) return
  marker ??= new mapboxgl.Marker({ color: '#05df72' })
  marker.setLngLat([lon, lat]).addTo(map)
}

/**
 * Corner coordinates for a Mapbox image source: TL, TR, BR, BL.
 *
 * `imageBounds.east` is **unwrapped** — the Pacific box ends at 290, not -70.
 * Mapbox accepts that and places the quad correctly across the antimeridian
 * (verified: `project([290,0])` and `project([-70,0])` return the same pixel).
 * Normalising it into -180..180 here would make west > east and collapse the
 * image to nothing.
 */
function imageCoordinates(offset = 0, bounds?: DomainMeta['imageBounds']): [[number, number], [number, number], [number, number], [number, number]] {
  const b = bounds ?? store.domain!.imageBounds
  return [
    [b.west + offset, b.north],
    [b.east + offset, b.north],
    [b.east + offset, b.south],
    [b.west + offset, b.south],
  ]
}

function currentUrl(): string | null {
  return props.date
    ? api.imageUrl(props.date, store.period, store.variable)
    : null
}

/**
 * Paint properties that turn a value-encoded WebP into a coloured map.
 *
 * `/image` ships DATA — the value packed into the RGB channels, land in alpha —
 * and Mapbox colours it here with `raster-color`. That is what keeps the
 * palette and the displayed range client-side: the daily NetCDF is pruned to a
 * retention window, so the cached image is eventually the only copy of that
 * field, and a pre-coloured one would have today's colormap baked in for good.
 *
 * `raster-resampling: nearest` is deliberate and load-bearing for `sst`, which
 * packs its value across two channels as `G*256 + B`. Linear filtering blends
 * the two channels independently, so a texel pair straddling a low-byte wrap
 * would decode ~2.56 degC away from either neighbour. Measured, nearest and
 * linear come out identical on the decode (median error 0.156 vs 0.159 degC,
 * both just texel quantisation) — and nearest is visibly cleaner at
 * single-pixel islands, which linear renders as coloured speckle.
 */
function rasterPaint(name: LayerName): Record<string, unknown> {
  const meta = store.domain!.variables[name]!
  const enc = meta.encoding
  // Both go through the store rather than /domain directly: the displayed range
  // is a user setting, and `stopsFor` spreads the server's colours over it.
  const stops = store.stopsFor(name)

  const ramp: Array<unknown> = meta.categorical
    ? categoricalRamp(stops)
    : continuousRamp(stops, enc)

  return {
    'raster-opacity': 0.85,
    'raster-fade-duration': 0,
    'raster-resampling': 'nearest',
    'raster-color-mix': enc.mix,
    'raster-color-range': store.colorRangeFor(name),
    'raster-color': ramp,
  }
}

/**
 * A `step`, not an `interpolate`: there is no colour between Cat 2 and Cat 3
 * because there is no value between them. Interpolating would draw a gradient
 * across a boundary that does not exist and make a Cat 2 pixel next to a Cat 4
 * one read as a Cat 3.
 *
 * The thresholds are the class values themselves rather than midpoints, which
 * is exact only because the ramp is tabulated over the encoding's whole 0..255
 * range — entry k is code k, so a Cat 3 lands on the entry at 3 and nowhere
 * near 2.5. See `colorRangeFor` in the store.
 *
 * The output below the first threshold is the first class's own colour, which
 * covers codes 0 and 1. Code 0 never reaches the ramp — land, ice and
 * heatwave-free ocean are all alpha 0 — so nothing is drawn with it either way.
 */
function categoricalRamp(stops: ColorStop[]): Array<unknown> {
  if (!stops.length) return ['step', ['raster-value'], 'rgba(0,0,0,0)']
  const ramp: Array<unknown> = ['step', ['raster-value'], stops[0]!.color]
  for (const stop of stops.slice(1)) ramp.push(stop.value, stop.color)
  return ramp
}

function continuousRamp(
  stops: ColorStop[],
  enc: { sentinel: number | null, range: [number, number], scale: number },
): Array<unknown> {
  const ramp: Array<unknown> = ['interpolate', ['linear'], ['raster-value']]
  if (enc.sentinel !== null) {
    // Code 0 is ocean that has no value on this variable — the ice fringe with
    // no climatology. Flat grey: transparent would read as land, and any colour
    // on a diverging scale would read as a real anomaly near zero. It sits one
    // whole encoding step below the first real code, so the ramp cannot blend
    // the two.
    ramp.push(enc.range[0], store.domain!.noClimColor)
    // The anchor that ends the sentinel's flat grey and starts the scale. It is
    // skipped when the user has dragged vmin down onto it, because the first
    // real stop is then already at that value and already that colour —
    // `interpolate` rejects two entries with the same input, which took the
    // whole layer down rather than just the one pair.
    const anchor = enc.range[0] + enc.scale
    if (stops[0]!.value > anchor) ramp.push(anchor, stops[0]!.color)
  }
  for (const stop of stops) ramp.push(stop.value, stop.color)
  return ramp
}

/** The colour under the raster, or null for a variable that declares none. */
function backgroundColor(): string | null {
  return store.domain?.variables[store.variable]?.backgroundColor ?? null
}

/** The image quad as a polygon ring — the fill below covers exactly the frame. */
function backgroundRing(offset = 0): GeoJSON.Position[] {
  const corners = imageCoordinates(offset)
  return [...corners, corners[0]!] as GeoJSON.Position[]
}

/**
 * The quads the fill has to cover: one in Mercator, two on the globe.
 *
 * Kept as one FeatureCollection rather than a second layer for the westward
 * copy, so there is only ever one layer to keep underneath the field.
 */
function backgroundData(): GeoJSON.FeatureCollection {
  const offsets = props.projection === 'globe' ? [0, -WORLD] : [0]
  return {
    type: 'FeatureCollection',
    features: offsets.map(offset => ({
      type: 'Feature',
      properties: {},
      geometry: { type: 'Polygon', coordinates: [backgroundRing(offset)] },
    })),
  }
}

/**
 * Add, update or drop the flat colour under the field.
 *
 * Inserted below the LOWEST field layer present, which is the westward copy
 * when the globe is on — `syncWestCopy` adds that immediately below `LAYER_ID`,
 * so inserting before `LAYER_ID` here would sandwich the fill between the two
 * halves of the same frame and hide the eastern one.
 */
function syncBackground() {
  if (!map || !map.getLayer(LAYER_ID)) return
  const color = backgroundColor()
  const source = map.getSource(BACKGROUND_SOURCE_ID) as mapboxgl.GeoJSONSource | undefined

  if (!color) {
    if (map.getLayer(BACKGROUND_LAYER_ID)) map.removeLayer(BACKGROUND_LAYER_ID)
    if (source) map.removeSource(BACKGROUND_SOURCE_ID)
    return
  }

  if (source) {
    source.setData(backgroundData())
    map.setPaintProperty(BACKGROUND_LAYER_ID, 'fill-color', color)
    return
  }

  map.addSource(BACKGROUND_SOURCE_ID, { type: 'geojson', data: backgroundData() })
  map.addLayer({
    id: BACKGROUND_LAYER_ID,
    type: 'fill',
    source: BACKGROUND_SOURCE_ID,
    // The same 0.85 the raster carries, so heatwave-free ocean and a Cat 1 cell
    // sit on the basemap with the same weight — a fully opaque floor under a
    // translucent field would read as a different surface, not as the same map.
    paint: { 'fill-color': color, 'fill-opacity': 0.85, 'fill-antialias': false },
  }, map.getLayer(WEST_LAYER_ID) ? WEST_LAYER_ID : LAYER_ID)
}

/** The land frame's URL, or null when the overlay is off or cannot be drawn. */
function landUrl(): string | null {
  const layer = store.landVariable
  if (!props.date || !layer || store.landReasonAt(props.date)) return null
  return api.imageUrl(props.date, store.period, layer)
}

/**
 * The first layer ABOVE the style's land fill — where the land raster goes.
 *
 * Found by position rather than named, so a label or boundary layer added to
 * the style later still ends up on top of the land field rather than under it.
 * Undefined (the top of the stack) if the style has no `country-boundaries`.
 */
function landBeforeId(): string | undefined {
  const layers = map?.getStyle()?.layers ?? []
  const i = layers.findIndex(l => l.id === 'country-boundaries')
  if (i < 0) return undefined
  // Skip our own layers: after the first add, the land raster itself is the
  // layer above the fill, and inserting "before" it would be a no-op loop.
  const next = layers.slice(i + 1).find(l => l.id !== LAND_LAYER_ID)
  return next?.id
}

function removeLand() {
  if (!map?.getLayer(LAND_LAYER_ID)) return
  map.removeLayer(LAND_LAYER_ID)
  map.removeSource(LAND_SOURCE_ID)
}

/**
 * Add, update or REMOVE the land overlay to match the store.
 *
 * Removed, never left on its last frame, whenever it cannot be drawn: Mapbox's
 * image source silently keeps the previous image when a new one 404s, which
 * here would put last week's rain under this week's date with nothing to say
 * so. `store.landReasonAt` is what decides, and the legend prints its reason.
 *
 * One quad, in both projections: the land frame is global and sits just
 * inside -180..180 (`landImageBounds`), so unlike the Pacific box it never
 * crosses the antimeridian and the globe needs no westward copy. It must not:
 * Mapbox draws a 360-degree image source only in the world copy nearest the
 * camera, so a frame crossing 180 loses whatever falls outside that copy.
 */
function syncLand() {
  if (!map || !styleReady) return
  const url = landUrl()
  const layer = store.landVariable
  if (!url || !layer) {
    removeLand()
    return
  }

  const paint = rasterPaint(layer)
  const coordinates = imageCoordinates(0, store.domain!.landImageBounds)
  const source = map.getSource(LAND_SOURCE_ID) as mapboxgl.ImageSource | undefined
  if (source) {
    // Repaint BEFORE swapping the image, as the ocean raster does: the six
    // layers pack their values differently, so a frame decoded with the
    // previous layer's mix is nonsense for the flicker it is on screen.
    for (const [key, value] of Object.entries(paint)) {
      map.setPaintProperty(LAND_LAYER_ID, key as never, value as never)
    }
    source.updateImage({ url, coordinates })
    return
  }
  map.addSource(LAND_SOURCE_ID, { type: 'image', url, coordinates })
  map.addLayer({ id: LAND_LAYER_ID, type: 'raster', source: LAND_SOURCE_ID, paint }, landBeforeId())
}

/** A land range change is a repaint and nothing more — see `applyPaint`. */
function applyLandPaint() {
  const layer = store.landVariable
  if (!map || !layer) return
  if (!map.getLayer(LAND_LAYER_ID)) return
  for (const [key, value] of Object.entries(rasterPaint(layer))) {
    map.setPaintProperty(LAND_LAYER_ID, key as never, value as never)
  }
}

function addRaster() {
  const url = currentUrl()
  if (!map || !url || map.getSource(SOURCE_ID)) return

  map.addSource(SOURCE_ID, { type: 'image', url, coordinates: imageCoordinates() })
  map.addLayer({
    id: LAYER_ID,
    type: 'raster',
    source: SOURCE_ID,
    paint: rasterPaint(store.variable),
  }, 'country-boundaries')
  syncWestCopy()
  syncBackground()
}

/** Add or drop the westward copy so it exists exactly on the globe. */
function syncWestCopy() {
  const url = currentUrl()
  if (!map || !map.getLayer(LAYER_ID)) return

  const wanted = props.projection === 'globe'
  const present = Boolean(map.getSource(WEST_SOURCE_ID))
  if (wanted === present) return

  if (wanted && url) {
    map.addSource(WEST_SOURCE_ID, { type: 'image', url, coordinates: imageCoordinates(-WORLD) })
    map.addLayer({
      id: WEST_LAYER_ID,
      type: 'raster',
      source: WEST_SOURCE_ID,
      paint: rasterPaint(store.variable),
    }, LAYER_ID)
  }
  else if (present) {
    map.removeLayer(WEST_LAYER_ID)
    map.removeSource(WEST_SOURCE_ID)
  }

  // The fill sits below the lowest field layer, and which layer that is has just
  // changed. Dropping and re-adding it is what re-seats it in the stack —
  // `moveLayer` would do as well, and this keeps one definition of where it goes.
  if (map.getLayer(BACKGROUND_LAYER_ID)) {
    map.removeLayer(BACKGROUND_LAYER_ID)
    map.removeSource(BACKGROUND_SOURCE_ID)
  }
  syncBackground()
}

/** Every field layer currently on the map, with the offset its quad sits at. */
function fieldLayers(): Array<{ layer: string, source: string, offset: number }> {
  const layers = [{ layer: LAYER_ID, source: SOURCE_ID, offset: 0 }]
  if (map?.getLayer(WEST_LAYER_ID)) layers.push({ layer: WEST_LAYER_ID, source: WEST_SOURCE_ID, offset: -WORLD })
  return layers
}

/**
 * A BOX region's outline, as a densified GeoJSON polygon.
 *
 * Not used for a masked region — `regionOutline()` above fetches the real ring
 * for those. This stays the only definition of a rectangle's outline, which is
 * why `/region/{key}/geometry` 404s for a box rather than synthesising one.
 *
 * TWO THINGS HERE ARE NOT DECORATION.
 *
 * 1. **The edges are densified.** A region box is a rectangle in lat/lon, not in
 *    any projection: its north and south edges follow a parallel, which is a
 *    curve on the globe and on Mercator both. The PDO domain spans 70 degrees of
 *    longitude, so a four-corner polygon would be drawn as a straight chord and
 *    bow off the parallel by a visible margin — putting the box somewhere other
 *    than the data it summarises. A vertex every `EDGE_STEP` degrees keeps it on
 *    the parallel.
 *
 * 2. **Longitudes stay unwrapped**, matching the image source and `/domain`'s own
 *    convention. Every region's east edge is above 180 and three of the eight
 *    cross the antimeridian outright (Nino 4 at 160..210, the Bering Sea at
 *    180..200, the PDO box at 180..250). Normalising east into -180..180 would
 *    make west > east — the same collapse `imageCoordinates()` documents.
 *
 *    **Verified in Chromium, both projections**, because the raster needed a
 *    second westward quad to survive the globe and there was no reason to
 *    assume a polygon would not: Nino 4 and the PDO box each draw as ONE
 *    continuous box across the dateline on the globe and on Mercator. No split
 *    ring, no MultiPolygon, no second copy. Splitting them at 180 was tried and
 *    is not needed.
 *
 *    Do not re-derive that from `queryRenderedFeatures`: on the globe it returns
 *    0 for a box that is plainly drawn on screen. Screenshot it, as CLAUDE.md
 *    says for the canvas.
 */
const EDGE_STEP = 2

function densify(from: number, to: number, at: (v: number) => [number, number]): Array<[number, number]> {
  const steps = Math.max(1, Math.ceil(Math.abs(to - from) / EDGE_STEP))
  return Array.from({ length: steps }, (_, i) => at(from + ((to - from) * i) / steps))
}

/**
 * A polygon region's real outline, fetched once and kept.
 *
 * Only a masked region has one — `/domain`'s `masked` flag says which — and
 * `/region/{key}/geometry` 404s for a box, whose outline is `regionPolygon()`
 * below. The ring is 104 KB for `pacific_bioregions`, which is why it is not in `/domain`:
 * most sessions never select it, and the ones that do pay for it once.
 *
 * Longitudes arrive UNWRAPPED on the 0-360 frame, like every other region bound
 * here, and are handed to Mapbox as they are. See `regionPolygon` for why.
 */
const outlines = new Map<string, GeoJSON.Feature>()

async function regionOutline(key: string): Promise<GeoJSON.Feature | null> {
  const held = outlines.get(key)
  if (held) return held
  try {
    const feature = await api.get<GeoJSON.Feature>(`/region/${key}/geometry`)
    outlines.set(key, feature)
    return feature
  }
  catch {
    // A missing outline must not take the map down with it. The region's numbers
    // are unaffected — they come off the rollup, which was built from the mask —
    // so the honest failure is no box rather than a rectangle that says the
    // region is something it is not.
    return null
  }
}

function regionPolygon(region: { lat: [number, number], lon: [number, number] }) {
  const [south, north] = [...region.lat].sort((a, b) => a - b)
  const [west, east] = [...region.lon].sort((a, b) => a - b)
  const ring = [
    ...densify(west, east, lon => [lon, north]),
    ...densify(north, south, lat => [east, lat]),
    ...densify(east, west, lon => [lon, south]),
    ...densify(south, north, lat => [west, lat]),
  ]
  ring.push(ring[0]!)
  return { type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [ring] } }
}

/**
 * Draw the region the app is currently reading, or nothing.
 *
 * Only ONE box is ever on the map, and only in region scope — the box is the
 * visual half of what the numbers panel is showing, so the two are the same
 * selection seen twice rather than two independent controls. Clicking a point
 * moves the app to point scope and the box goes with it.
 */
function syncRegionBox() {
  // NOT `map.isStyleLoaded()`. That reports whether every source in the style
  // has settled, not whether layers can be added, and it stays false long after
  // 'load' has fired and the raster layers are up — measured at 10 s into a
  // loaded page. Guarding on it silently skipped the box forever. `styleReady`
  // is set in the 'load' handler, which is the actual precondition.
  if (!map || !styleReady) return
  const region = store.scope === 'region' ? store.activeRegionMeta : null

  if (!region) {
    if (map.getLayer(REGION_FILL_ID)) map.removeLayer(REGION_FILL_ID)
    if (map.getLayer(REGION_LINE_ID)) map.removeLayer(REGION_LINE_ID)
    if (map.getSource(REGION_SOURCE_ID)) map.removeSource(REGION_SOURCE_ID)
    return
  }

  if (region.masked) {
    // Nothing is drawn until the real outline is in. Drawing the bounding box
    // first and swapping it for the zone a moment later reads as a bug, and the
    // box is 2.1x the region's area for `pacific_bioregions` — it would be claiming the
    // numbers cover Alaskan and high-seas water they do not.
    void regionOutline(region.key).then((feature) => {
      // The selection can move while this is in flight.
      if (feature && store.scope === 'region' && store.activeRegion === region.key) {
        drawRegion(feature)
      }
    })
    return
  }
  drawRegion(regionPolygon(region))
}

/** Put one GeoJSON outline on the map, creating the source and layers once. */
function drawRegion(data: GeoJSON.Feature) {
  if (!map) return
  const existing = map.getSource(REGION_SOURCE_ID) as mapboxgl.GeoJSONSource | undefined
  if (existing) {
    existing.setData(data)
    return
  }

  map.addSource(REGION_SOURCE_ID, { type: 'geojson', data })
  // A wash rather than a tint: the field underneath is the thing being read, and
  // a fill heavy enough to notice would shift every colour inside the box.
  map.addLayer({
    id: REGION_FILL_ID,
    type: 'fill',
    source: REGION_SOURCE_ID,
    paint: { 'fill-color': REGION_COLOR, 'fill-opacity': 0.07 },
  })
  map.addLayer({
    id: REGION_LINE_ID,
    type: 'line',
    source: REGION_SOURCE_ID,
    paint: { 'line-color': REGION_COLOR, 'line-width': 2, 'line-opacity': 0.9 },
  })
}

/** The ramp, mix and range all change with the variable, not just the URL. */
function applyPaint() {
  if (!map || !map.getLayer(LAYER_ID)) return
  // The floor under the field is the variable's too — `mhw` declares one, the
  // continuous variables do not — so it is swapped on the same gesture.
  syncBackground()
  const paint = rasterPaint(store.variable)
  for (const { layer } of fieldLayers()) {
    for (const [key, value] of Object.entries(paint)) {
      map.setPaintProperty(layer, key as never, value as never)
    }
  }
}

onMounted(() => {
  if (!token || !container.value || !store.domain) return

  mapboxgl.accessToken = token
  const b = store.domain.imageBounds
  const globe = props.projection === 'globe'

  map = new mapboxgl.Map({
    container: container.value,
    // style: 'mapbox://styles/mapbox/dark-v11',
    style: 'mapbox://styles/taimazb/cmu1ilr2t000401r223kb2ghd?fresh=true',
    minZoom: 1,
    maxZoom:6,
    // Globe by default, opened on the North Pacific. `bounds` and `center`/`zoom`
    // are alternatives, not both — see `AnomalyMap`'s `frame()` for why each projection gets
    // its own.
    ...(props.initialView
      ?? (globe
        ? GLOBE_VIEW
        : { bounds: [[b.west, b.south], [b.east, b.north]] as [[number, number], [number, number]], fitBoundsOptions: { padding: 20 } })),
    projection: { name: props.projection },
  })

  map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'top-right')

  // Dev-only handle for browser verification. The map cannot be checked by
  // reading its canvas — it runs with `preserveDrawingBuffer: false`, so
  // `drawImage` yields a blank frame — so a driven browser needs the instance
  // itself to query layers and rendered features. Stripped from production by
  // `import.meta.dev`.
  if (import.meta.dev) {
    const w = window as unknown as { __map?: mapboxgl.Map, __compareMap?: mapboxgl.Map, __store?: typeof store }
    if (props.primary) w.__map = map
    else w.__compareMap = map
    w.__store = store
  }

  // The ranks dock takes width from the map, and its drag handle takes it
  // continuously — the canvas has to follow the container rather than the window.
  resize = new ResizeObserver(() => map?.resize())
  resize.observe(container.value)

  // The style may already be loaded by the time this runs (a warm style cache),
  // in which case 'load' has fired and would never fire again.
  const draw = () => { styleReady = true; addRaster(); syncLand(); syncRegionBox() }
  if (map.isStyleLoaded()) draw()
  else map.once('load', draw)

  map.on('click', (event) => {
    const { lat, lng } = event.lngLat
    store.selectPoint(Number(lat.toFixed(4)), Number(lng.toFixed(4)))
    showMarker(lat, lng)
  })

  // The store opens on a default cell, so the pin has to be there before the
  // first click or the chart would be describing an unmarked point.
  if (store.selectedPoint) showMarker(store.selectedPoint.lat, store.selectedPoint.lon)

  emit('ready', map)
})

// Swapping the URL in place keeps the layer and its paint properties, so
// stepping through days — or switching to a weekly/monthly mean — does not
// flash the basemap between frames.
watch(() => [props.date, store.period, store.variable], () => {
  const url = currentUrl()
  if (!map || !url) return
  if (map.getSource(SOURCE_ID)) {
    // Repaint before swapping the image: the two encodings pack their value
    // differently, so a frame drawn with the previous variable's mix would
    // decode to nonsense for the one flicker it is on screen.
    applyPaint()
    for (const { source, offset } of fieldLayers()) {
      const image = map.getSource(source) as mapboxgl.ImageSource | undefined
      image?.updateImage({ url, coordinates: imageCoordinates(offset) })
    }
  }
  // `styleReady`, not `map.isStyleLoaded()` — see `syncRegionBox`.
  else if (styleReady) addRaster()
})

// A range change is a repaint and nothing more — deliberately separate from the
// watcher above, which also swaps the image. The frame on screen carries the
// value, not the colour, so re-ranging never needs another byte from /image;
// calling updateImage here would flash the basemap and refetch a frame the
// browser already has, for a result identical to setting the paint property.
watch(() => store.activeScale, applyPaint, { deep: true })

// The land overlay follows its own choice, the date and period it shares with
// the ocean, and coverage — which is what can make a date undrawable. One
// watcher: every one of these can flip it between drawn and removed.
watch(
  () => [props.date, store.period, store.landVariable, store.coverage?.land],
  syncLand,
)

// Its colour range is the land layer's own, independent of the ocean's.
watch(
  () => (store.landVariable ? store.scaleFor(store.landVariable) : null),
  applyLandPaint,
  { deep: true },
)

// The box follows the scope and the chosen region together — it is one
// selection drawn twice, not a layer with a toggle of its own. Flying the camera
// to it is the host's job (`AnomalyMap.frameRegion`).
watch(() => [store.scope, store.activeRegion], syncRegionBox)

// The pin follows the selected cell however it was chosen. A click moves it
// directly, but a deep link, a story step or the other map in compare mode
// change the selection without a click on THIS map.
watch(() => store.selectedPoint, (point) => {
  if (point) showMarker(point.lat, point.lon)
})

// Changing projection re-seats the westward copy, which exists only on the
// globe. Re-framing afterwards is the host's decision.
watch(() => props.projection, (name) => {
  map?.setProjection({ name })
  syncWestCopy()
  syncLand()
})

onBeforeUnmount(() => {
  if (import.meta.dev && !props.primary) {
    delete (window as unknown as { __compareMap?: mapboxgl.Map }).__compareMap
  }
  resize?.disconnect()
  resize = null
  marker?.remove()
  map?.remove()
  map = null
})
</script>
