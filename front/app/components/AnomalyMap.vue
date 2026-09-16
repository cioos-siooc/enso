<template>
  <div ref="root" class="relative size-full overflow-hidden">
    <FieldMap
      v-if="mounted"
      :date="store.selectedDate"
      :projection="projection"
      primary
      class="absolute inset-0"
      @ready="onPrimaryReady"
    />

    <!-- Swipe compare. The second map is stacked on the first and clipped to the
         right of the divider; `clip-path` clips hit-testing too, so each half
         takes the clicks and drags for the map it shows. Mounted only while
         compare is on — a second map is a second WebGL context. -->
    <template v-if="mounted && store.compareDate && token">
      <FieldMap
        :date="store.compareDate"
        :projection="projection"
        :initial-view="compareOpensAt"
        class="absolute inset-0"
        :style="{ clipPath: `inset(0 0 0 ${split}%)` }"
        @ready="onCompareReady"
      />

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Compare divider"
        :aria-valuenow="Math.round(split)"
        aria-valuemin="0"
        aria-valuemax="100"
        tabindex="0"
        class="absolute inset-y-0 z-10 flex w-8 -translate-x-1/2 cursor-col-resize touch-none items-center justify-center focus-visible:outline-none"
        :style="{ left: `${split}%` }"
        @pointerdown="startDrag"
        @keydown.left.prevent="setSplit(split - SPLIT_STEP)"
        @keydown.right.prevent="setSplit(split + SPLIT_STEP)"
      >
        <div class="h-full w-0.5 bg-white/80 shadow" />
        <div class="absolute flex size-8 items-center justify-center rounded-full border border-default bg-elevated text-default shadow-lg">
          <UIcon name="i-mdi-arrow-left-right" class="size-4" />
        </div>
      </div>

      <!-- Each half names its bucket, pinned against the divider so the label
           travels with the half it describes. -->
      <span
        class="pointer-events-none absolute top-2 z-10 mr-6 whitespace-nowrap rounded bg-elevated/90 px-2 py-0.5 text-xs font-medium text-highlighted shadow"
        :style="{ right: `${100 - split}%` }"
      >{{ leftLabel }}</span>
      <span
        class="pointer-events-none absolute top-2 z-10 ml-6 whitespace-nowrap rounded bg-elevated/90 px-2 py-0.5 text-xs font-medium text-highlighted shadow"
        :style="{ left: `${split}%` }"
      >{{ rightLabel }}</span>
    </template>

    <!-- Everything that changes what the map is showing, in one column: how it
         is projected, then what is being read off it. Stacked with a gap rather
         than positioned individually so neither has to know the other's height. -->
    <div class="absolute left-2 top-2 z-20 flex flex-col items-start gap-2">
      <UFieldGroup v-if="token" size="xs" class="rounded-lg shadow-lg">
        <UButton
          v-for="item in PROJECTIONS"
          :key="item.value"
          :icon="item.icon"
          :label="item.label"
          :color="projection === item.value ? 'primary' : 'neutral'"
          :variant="projection === item.value ? 'solid' : 'subtle'"
          :title="item.title"
          @click="setProjection(item.value)"
        />
      </UFieldGroup>

      <ScopeControl />
    </div>

    <div
      v-if="!token"
      class="absolute inset-0 z-10 flex items-center justify-center bg-elevated/90 p-6 text-center text-sm text-muted"
    >
      Set <code class="text-highlighted">NUXT_PUBLIC_MAPBOX_TOKEN</code> in
      <code class="text-highlighted">.env.dev</code> to show the basemap.
    </div>
  </div>
</template>

<script setup lang="ts">
import type mapboxgl from 'mapbox-gl'
import { useMainStore } from '~/stores/main'
import type { CameraView, ProjectionName } from '~/utils/mapView'
import { bucketLabel } from '~/utils/periods'

/**
 * The map pane: one field map, or two in swipe compare, plus the controls over
 * them.
 *
 * All drawing is `FieldMap`'s. This component owns what the two maps share and
 * must not each decide for themselves — the projection, the camera, and the
 * divider between them.
 */
const store = useMainStore()
const token = useRuntimeConfig().public.mapboxToken

const root = ref<HTMLElement | null>(null)
/** The main map. Framing flights go to it; the compare map follows. */
let primary: mapboxgl.Map | null = null
let secondary: mapboxgl.Map | null = null

const PROJECTIONS = [
  { value: 'globe' as const, icon: 'i-mdi-earth', label: 'Globe', title: 'Globe — true areas, the basin as it sits on the planet' },
  { value: 'mercator' as const, icon: 'i-mdi-map-outline', label: 'Flat', title: 'Mercator — the whole box flat and visible at once' },
]

/** Remembered across sessions, like the dock width and the colour ranges. */
const PROJECTION_KEY = 'enso.map.projection'

const projection = ref<ProjectionName>('globe')

/**
 * The field maps are created only once this is true, i.e. after the saved
 * projection has been read. Reading it during setup would render the projection
 * buttons differently on the server and in the browser (a hydration mismatch),
 * and a child `FieldMap` builds its Mapbox instance in its own `onMounted`,
 * which runs before this component's — so it would open on the wrong projection
 * and have to be switched. Mapbox is client-only anyway.
 */
const mounted = ref(false)

onMounted(() => {
  try {
    const saved = localStorage.getItem(PROJECTION_KEY)
    if (saved === 'globe' || saved === 'mercator') projection.value = saved
  }
  catch { /* private mode — open on the default */ }
  mounted.value = true
})

/** Frame the box the way the current projection wants to be framed. */
function frame(animate = true) {
  const map = primary
  if (!map) return
  if (projection.value === 'globe') {
    const options = { ...GLOBE_VIEW }
    if (animate) map.easeTo({ ...options, duration: 600 })
    else map.jumpTo(options)
    return
  }
  // The whole box, no clipping. The old INITIAL_NORTH workaround existed
  // because the OISST domain ran to 90N and the 70-90 strip dominated a
  // Mercator fit; this box stops at 65N, so it fits without a sliver.
  const b = store.domain!.imageBounds
  map.fitBounds([[b.west, b.south], [b.east, b.north]], {
    padding: 20,
    duration: animate ? 600 : 0,
  })
}

/**
 * Fly to the active region's box.
 *
 * The box is the visual half of what the numbers panel is reading, so selecting
 * a region moves the camera to it rather than leaving the user to find an amber
 * rectangle somewhere on a 190-degree-wide basin — Nino 1+2 is 10 degrees wide
 * on a box that spans 190, i.e. about 3% of its width.
 *
 * Longitudes stay **unwrapped**, as everywhere else here: three regions cross
 * the antimeridian (Nino 4 at 160..210, the Bering Sea at 180..200, the PDO box
 * at 180..250) and normalising east into -180..180 would make west > east, which
 * `fitBounds` reads as a bounds running the long way round the planet. Mapbox
 * projects 250 the same way it projects the polygon's vertices and wraps the
 * resulting centre itself.
 *
 * `fitBounds` is used on the globe too — unlike `frame()`, which cannot use it
 * because the whole domain is 190 degrees wide and half of it is behind the limb
 * at any zoom that fits it. A region box is at most 70 degrees (the PDO domain),
 * which fits on the visible face.
 *
 * `maxZoom` is what stops the smallest boxes from filling the screen: Nino 1+2
 * fitted exactly would leave no coastline around it to say where it is, and the
 * point of the flight is context, not magnification.
 */
const REGION_PADDING = 60
const REGION_MAX_ZOOM = 4.5

function frameRegion(animate = true) {
  const map = primary
  const region = store.scope === 'region' ? store.activeRegionMeta : null
  if (!map || !region) return

  const [south, north] = [...region.lat].sort((a, b) => a - b)
  const [west, east] = [...region.lon].sort((a, b) => a - b)
  map.fitBounds([[west, south], [east, north]], {
    padding: REGION_PADDING,
    maxZoom: REGION_MAX_ZOOM,
    duration: animate ? 1200 : 0,
  })
}

async function setProjection(name: ProjectionName) {
  if (name === projection.value) return
  projection.value = name
  // The field maps apply the projection in their own watchers; the frame has to
  // wait for that, or it fits the box for the projection being left.
  await nextTick()
  // Re-frame after the swap: a view that fits the box flat is not a view that
  // shows it on a sphere, and vice versa. In region scope the region is what is
  // being read, so the swap keeps looking at it rather than pulling back out to
  // the whole basin.
  if (store.scope === 'region' && store.activeRegionMeta) frameRegion()
  else frame()
  try {
    localStorage.setItem(PROJECTION_KEY, name)
  }
  catch { /* private mode — the choice still applies this session */ }
}

function onPrimaryReady(map: mapboxgl.Map) {
  primary = map
  // A deep link or a story can pick a region before the map exists.
  if (store.scope === 'region') frameRegion(false)
  if (secondary) link()
}

// --- Swipe compare -----------------------------------------------------------

/** Divider position, percent of the pane from the left. */
const split = ref(50)
const SPLIT_STEP = 5

function setSplit(value: number) {
  split.value = Math.min(100, Math.max(0, value))
}

let stopDrag: (() => void) | null = null

function startDrag(event: PointerEvent) {
  event.preventDefault()
  const onMove = (e: PointerEvent) => {
    const rect = root.value?.getBoundingClientRect()
    if (rect && rect.width) setSplit(((e.clientX - rect.left) / rect.width) * 100)
  }
  const onUp = () => stopDrag?.()
  stopDrag = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    stopDrag = null
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const leftLabel = computed(() => store.selectedDate ? bucketLabel(store.selectedDate, store.period) : '')
const rightLabel = computed(() => store.compareDate ? bucketLabel(store.compareDate, store.period) : '')

function cameraOf(map: mapboxgl.Map): CameraView {
  const c = map.getCenter()
  return { center: [c.lng, c.lat], zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() }
}

/**
 * Where the compare map opens: wherever the main map is looking right now.
 * Read once, when compare is switched on; after that the two are linked.
 */
const compareOpensAt = ref<CameraView | undefined>()
watch(() => Boolean(store.compareDate), (on) => {
  if (on && primary) compareOpensAt.value = cameraOf(primary)
}, { immediate: true })

/**
 * Keep the two cameras locked, in both directions: either half can be dragged.
 *
 * `jumpTo` fires the other map's own `move` synchronously, so without the guard
 * each move would bounce back and forth forever.
 */
let syncing = false
const unlinks: Array<() => void> = []

function follow(from: mapboxgl.Map, to: mapboxgl.Map) {
  const handler = () => {
    if (syncing) return
    syncing = true
    to.jumpTo(cameraOf(from))
    syncing = false
  }
  from.on('move', handler)
  unlinks.push(() => from.off('move', handler))
}

function link() {
  if (!primary || !secondary) return
  secondary.jumpTo(cameraOf(primary))
  follow(primary, secondary)
  follow(secondary, primary)
}

function unlink() {
  while (unlinks.length) unlinks.pop()!()
}

function onCompareReady(map: mapboxgl.Map) {
  secondary = map
  link()
}

watch(() => Boolean(store.compareDate), (on) => {
  if (on) return
  unlink()
  secondary = null
})

// --- Camera requests ---------------------------------------------------------

// The box follows the scope and the chosen region together, and the camera
// follows the box. Leaving point scope deliberately moves nothing: the pin is
// already where the user clicked, so a flight there would be a jolt with no
// destination.
watch(() => [store.scope, store.activeRegion], () => frameRegion())

// A view someone else chose, a story step. The compare map follows through the link.
watch(() => store.cameraRequest, (view) => {
  if (!view || !primary) return
  primary.flyTo({
    center: view.center,
    zoom: view.zoom,
    bearing: view.bearing ?? 0,
    pitch: view.pitch ?? 0,
    duration: 1200,
  })
})

onBeforeUnmount(() => {
  stopDrag?.()
  unlink()
  primary = null
  secondary = null
})
</script>
