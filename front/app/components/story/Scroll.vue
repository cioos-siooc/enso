<template>
  <!-- A story told over the live map: cards scroll past a fixed globe, and each
       step switches the map to its own view and flies the camera there. The
       pattern is Mapbox's storytelling template; the map is the app's own
       `FieldMap`, so every frame is the real one and every step is a link. -->
  <div class="story-map relative h-full overflow-hidden bg-[#0b0d12] font-serif text-[1.0625rem] leading-[1.6]">
    <!-- The scroller covers the map whole, so the wheel scrolls the story and
         never zooms the map; the camera is the story's to move. -->
    <ClientOnly>
      <FieldMap
        :date="mapDate"
        projection="globe"
        :initial-view="cameraFor(steps[0]!)"
        class="absolute inset-0"
        @ready="onReady"
      />
    </ClientOnly>
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_45%,rgb(0_0_0/0.55))]" />

    <!-- What the map is showing right now: the date, large, and its key.
         Under the scroller, so a passing card covers them rather than the
         other way round. Left off title steps, whose type would run into it. -->
    <div v-if="steps[active]?.align !== 'center'" class="pointer-events-none absolute right-4 top-4 z-[5] flex flex-col items-end gap-1 text-right md:right-8 md:top-6">
      <span class="font-display text-[clamp(1.6rem,4.4vw,3.2rem)] font-[800] leading-none tabular-nums text-white [font-stretch:115%] [text-shadow:0_2px_12px_rgb(0_0_0/0.7)]">
        {{ dateLabel }}
      </span>
      <span class="font-data text-[0.7rem] uppercase tracking-wider text-white/75 [text-shadow:0_1px_6px_rgb(0_0_0/0.8)]">{{ layerLabel }}</span>
    </div>

    <!-- The key, read from the store: the range in force, and a second row
         for the land overlay when one is on. -->
    <div v-if="keys.length" class="pointer-events-none absolute bottom-10 left-4 z-[5] flex w-56 flex-col gap-2 rounded-lg bg-black/55 px-3 py-2 font-data text-[0.7rem] text-white/85 backdrop-blur md:bottom-6 md:left-8">
      <div v-for="k in keys" :key="k.label">
        <div v-if="keys.length > 1" class="mb-1 text-white/65">{{ k.label }}</div>
        <div v-if="k.classes" class="flex gap-1">
          <i v-for="c in k.classes" :key="c" class="h-2 flex-1 rounded-sm" :style="{ background: c }" />
        </div>
        <i v-else class="block h-2 rounded-full" :style="{ background: k.gradient }" />
        <div class="mt-1 flex justify-between"><span>{{ k.lo }}</span><span v-if="k.mid">{{ k.mid }}</span><span>{{ k.hi }}</span></div>
      </div>
    </div>

    <!-- Where the reader is: one dot per step. -->
    <nav class="absolute right-3 top-1/2 z-30 hidden -translate-y-1/2 flex-col gap-2.5 md:flex" aria-label="Chapters">
      <button
        v-for="(s, i) in steps"
        :key="s.id"
        type="button"
        :aria-label="s.title"
        :title="s.title"
        class="size-2.5 rounded-full ring-1 ring-white/60 transition-all"
        :class="i === active ? 'scale-125 bg-white' : 'bg-white/10 hover:bg-white/50'"
        @click="goTo(i)"
      />
    </nav>

    <div ref="scroller" class="absolute inset-0 z-10 overflow-y-auto overscroll-contain" @scroll.passive="onScroll">
      <div class="relative">
        <section
          v-for="(s, i) in steps"
          :key="s.id"
          :ref="el => { stepEls[i] = el as HTMLElement }"
          class="relative flex px-4 md:px-12"
          :class="[
            s.scrub ? 'h-[420dvh] items-start' : 'min-h-dvh items-center',
            s.align === 'center' ? 'justify-center' : s.align === 'right' ? 'justify-end' : 'justify-start',
          ]"
        >
          <!-- Titles, intro and outro: type on the map, no card. -->
          <div v-if="s.align === 'center'" class="relative isolate flex max-w-3xl flex-col items-center gap-6 py-24 text-center text-white">
            <!-- A soft dark pool under the type: over a pale stretch of globe
                 (ice, a cool anomaly) white text alone would vanish. -->
            <div class="pointer-events-none absolute inset-x-[-4rem] inset-y-12 -z-10 rounded-[50%] bg-black/60 blur-3xl" />
            <span class="font-data text-xs uppercase tracking-[0.2em] text-white/85 [text-shadow:0_1px_4px_rgb(0_0_0/0.9)]">{{ s.eyebrow }}</span>
            <component
              :is="i === 0 ? 'h1' : 'h2'"
              class="font-display text-[clamp(2.6rem,7.5vw,5.6rem)] font-extrabold leading-[0.98] text-balance [font-stretch:120%] [text-shadow:0_2px_4px_rgb(0_0_0/0.5),0_4px_30px_rgb(0_0_0/0.7)]"
            >
              {{ s.title }}
            </component>
            <p v-for="(p, k) in s.body" :key="k" class="max-w-xl text-lg text-white [text-shadow:0_1px_3px_rgb(0_0_0/0.9),0_1px_12px_rgb(0_0_0/0.8)]">{{ p }}</p>
            <span v-if="i === 0" class="mt-10 flex flex-col items-center gap-1 font-data text-xs uppercase tracking-wider text-white/70">
              Scroll
              <UIcon name="i-mdi-chevron-down" class="size-5 animate-bounce" />
            </span>
            <slot v-if="s.outro" name="outro" />
          </div>

          <article
            v-else
            class="my-[30dvh] w-full rounded-2xl border border-white/10 bg-[#0f1219]/85 p-5 text-white/90 shadow-2xl backdrop-blur-md transition-all duration-700 md:p-7"
            :class="[
              s.wide ? 'max-w-2xl' : 'max-w-md',
              s.scrub ? 'sticky top-[20dvh]' : '',
              i === active ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-40',
            ]"
          >
            <figure v-if="s.photo" class="-mx-5 -mt-5 mb-5 overflow-hidden rounded-t-2xl md:-mx-7 md:-mt-7">
              <img :src="withAppBase(s.photo.src)" :alt="s.photo.alt" class="max-h-32 w-full object-cover md:max-h-52" loading="lazy">
              <figcaption class="bg-black/40 px-4 py-1.5 font-data text-[0.65rem] text-white/60">
                <a :href="s.photo.href" target="_blank" rel="noopener" class="underline-offset-2 hover:underline">{{ s.photo.credit }}</a>
              </figcaption>
            </figure>
            <span class="font-data text-xs uppercase tracking-wider text-orange-300">{{ s.eyebrow }}</span>
            <h2 class="mt-2 font-display text-[clamp(1.6rem,3vw,2.2rem)] font-[750] leading-[1.05] text-balance text-white [font-stretch:112%]">
              {{ s.title }}
            </h2>
            <div v-if="s.readout" class="mt-4 flex items-baseline gap-3 border-y border-white/10 py-3">
              <span class="shrink-0 whitespace-nowrap font-display text-[2.6rem] font-[800] leading-none tabular-nums [font-stretch:110%]" :style="{ color: s.readout.color }">
                {{ shown(i) }}
              </span>
              <span class="font-data text-xs leading-snug text-white/65">{{ s.readout.label }}</span>
            </div>
            <p v-for="(p, k) in s.body" :key="k" class="mt-4">{{ p }}</p>
            <div v-if="s.figure" class="mt-5">
              <slot :name="s.figure" />
            </div>
            <blockquote v-if="s.quote" class="mt-5 border-l-2 border-orange-300 pl-4 italic text-white">
              “{{ s.quote.text }}”
              <footer class="mt-1 font-data text-xs not-italic text-white/60">{{ s.quote.cite }}</footer>
            </blockquote>
            <div v-if="s.scrub" class="mt-5 h-1 overflow-hidden rounded-full bg-white/10">
              <div class="h-full bg-orange-300" :style="{ width: `${scrubProgress * 100}%` }" />
            </div>
            <p v-if="s.refs?.length" class="mt-4 font-data text-[0.7rem] leading-relaxed text-white/55">
              {{ s.refs.length > 1 ? 'Sources' : 'Source' }}:
              <template v-for="(k, n) in s.refs" :key="k">
                <template v-if="n"> · </template>
                <a :href="references[k]?.url" :title="references[k]?.full" target="_blank" rel="noopener" class="text-white/80 underline underline-offset-2 hover:text-white">{{ references[k]?.short ?? k }}</a>
              </template>
            </p>
            <a
              v-if="!s.noLink"
              :href="withAppBase(viewLink(s.view))"
              target="_blank"
              rel="noopener"
              class="mt-4 inline-flex items-center gap-1 font-sans text-sm font-medium text-orange-300 hover:text-orange-200"
            >
              Open this view in OSTA
              <UIcon name="i-mdi-open-in-new" class="size-4" />
            </a>
          </article>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type mapboxgl from 'mapbox-gl'
import { useMainStore, type LayerName } from '~/stores/main'
import { formatLog2Percent, type LandSource } from '~/utils/land'
import { bucketLabel } from '~/utils/periods'
import { signed, viewLink, type StoryCamera, type StoryReference, type StoryStep } from '~/utils/story'

/**
 * The scrolling map story. A page supplies the steps and its references and
 * fills the `#outro` slot; everything else is here.
 *
 * Each step hands its whole view to `store.applyView`, the same path a pasted
 * link takes, so a step and its "Open this view" link cannot disagree. The
 * map's date is the store's except inside a `scrub` step, where scroll
 * position picks the month and the store is left alone.
 */
const props = defineProps<{
  steps: StoryStep[]
  references: Record<string, StoryReference>
}>()

const LAND: Record<LandSource, string> = { tmax: 'daytime highs', tmin: 'overnight lows', precip: 'precipitation' }

const store = useMainStore()
const api = useApi()
const { narrow } = useViewport()

const scroller = ref<HTMLElement | null>(null)
const stepEls: HTMLElement[] = []
const active = ref(0)
const scrubProgress = ref(0)
let map: mapboxgl.Map | null = null

// --- Time ---------------------------------------------------------------------

function monthsBetween(from: string, to: string): string[] {
  const out: string[] = []
  const d = new Date(`${from}T00:00:00Z`)
  const end = new Date(`${to}T00:00:00Z`)
  while (d <= end) {
    out.push(d.toISOString().slice(0, 10))
    d.setUTCMonth(d.getUTCMonth() + 1)
  }
  return out
}

const scrubFrames = computed(() => {
  const s = props.steps[active.value]?.scrub
  return s ? monthsBetween(s.from, s.to) : []
})

/** The month a scrub step is on, as an index into its frames. */
const scrubIndex = computed(() => Math.min(scrubFrames.value.length - 1, Math.floor(scrubProgress.value * scrubFrames.value.length)))

const mapDate = computed(() => {
  const frames = scrubFrames.value
  if (!frames.length) return store.selectedDate
  return frames[scrubIndex.value]!
})

// Stories write dates month first ("April 1, 2016"); the app keeps its own.
const dateLabel = computed(() => {
  if (!mapDate.value) return ''
  if (store.period !== 'daily') return bucketLabel(mapDate.value, store.period)
  return new Date(`${mapDate.value}T00:00:00Z`).toLocaleDateString('en-US', { dateStyle: 'long', timeZone: 'UTC' })
})
const layerLabel = computed(() => {
  const ocean = store.variable === 'mhw'
    ? 'Marine heatwave category'
    : store.variable === 'anom' ? 'Sea surface temperature anomaly' : 'Sea surface temperature'
  if (!store.landLayer) return ocean
  return `${ocean} · land: ${LAND[store.landLayer]}${store.landMode === 'value' ? '' : ' vs normal'}`
})

/**
 * Warm a scrub step's frames as the reader approaches it, so scrolling never
 * waits on the network. At the app's 4096 px width a monthly anomaly frame is
 * ~850 KB: keep scrubs to a few dozen months.
 */
const warmed = new Set<string>()
function warmFrames(s: StoryStep) {
  if (!s.scrub || warmed.has(s.id)) return
  warmed.add(s.id)
  for (const d of monthsBetween(s.scrub.from, s.scrub.to)) {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = api.imageUrl(d, 'monthly', s.view.variable ?? 'anom')
  }
}

// --- The key -------------------------------------------------------------------

interface Key { label: string, gradient?: string, classes?: string[], lo: string, mid?: string, hi: string }

/**
 * One layer's key, from the same stops and range the map is drawn with, so a
 * range the reader set in the app shows here too.
 */
function keyFor(layer: LayerName, label: string): Key | null {
  const stops = store.stopsFor(layer)
  if (stops.length < 2) return null
  if (store.isCategorical(layer)) {
    return { label, classes: stops.map(s => s.color), lo: stops[0]!.label ?? '', hi: stops.at(-1)!.label ?? '' }
  }
  const meta = store.domain?.variables?.[layer]
  const { vmin, vmax } = store.scaleFor(layer)
  const unit = store.unitLabelFor(layer) || meta?.units || ''
  const tick = (v: number) => meta?.display === 'log2_percent'
    ? formatLog2Percent(v)
    : `${vmin < 0 ? signed(v, Number.isInteger(v) ? 0 : 1) : v} ${unit}`
  const parts = stops.map((s, i) => `${s.color} ${((i / (stops.length - 1)) * 100).toFixed(1)}%`)
  return {
    label,
    gradient: `linear-gradient(90deg, ${parts.join(', ')})`,
    lo: tick(vmin),
    // A diverging ramp's white middle is the normal.
    mid: vmin < 0 && vmax > 0 ? 'normal' : undefined,
    hi: tick(vmax),
  }
}

const keys = computed(() => [
  keyFor(store.variable, 'Ocean'),
  store.landVariable ? keyFor(store.landVariable, `Land: ${LAND[store.landLayer!]}`) : null,
].filter((k): k is Key => !!k))

// --- Readouts count up when their step arrives --------------------------------

const counted = ref<Record<number, number>>({})
let raf = 0

function reducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function countUp(i: number) {
  const r = props.steps[i]?.readout
  if (!r) return
  cancelAnimationFrame(raf)
  if (reducedMotion()) {
    counted.value[i] = r.value
    return
  }
  const start = performance.now()
  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / 1100)
    counted.value[i] = r.value * (1 - (1 - t) ** 3)
    if (t < 1) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

function shown(i: number): string {
  const s = props.steps[i]!
  const r = s.readout!
  // A scrub with a value per month follows the clock instead of counting up.
  const v = s.scrub?.values && i === active.value ? (s.scrub.values[scrubIndex.value] ?? r.value) : (counted.value[i] ?? 0)
  // Locale pinned: this renders under SSR too.
  const n = r.signed ? signed(v, r.digits) : v.toLocaleString('en-GB', { minimumFractionDigits: r.digits, maximumFractionDigits: r.digits })
  return `${r.prefix ?? ''}${n}${r.unit}`
}

// --- A step's line and places ------------------------------------------------------

const LINE_SOURCE_ID = 'story-line'
let labels: mapboxgl.Marker[] = []

/**
 * Draws the step's `line` and `places`, or clears the last ones. Above every
 * map layer; labels are DOM markers so they take the page's type, not the style's.
 */
async function drawLine(s: StoryStep) {
  if (!map) return
  // `ready` comes before the style has loaded on a cold start.
  if (!map.getSource(LINE_SOURCE_ID) && !map.isStyleLoaded()) {
    map.once('load', () => void drawLine(props.steps[active.value]!))
    return
  }
  const coords = s.line?.coords ?? []
  const places = s.places ?? []
  const dot = (c: [number, number]) => ({ type: 'Feature' as const, properties: {}, geometry: { type: 'Point' as const, coordinates: c } })
  const data: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: [
      // One vertex is a place, not a line: just its dot.
      ...(coords.length > 1 ? [{ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: coords } }] : []),
      ...coords.map(dot),
      ...places.filter(p => p.dot !== false).map(p => dot(p.coords)),
    ],
  }
  const source = map.getSource(LINE_SOURCE_ID) as mapboxgl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
  } else {
    map.addSource(LINE_SOURCE_ID, { type: 'geojson', data })
    // A dark casing under the white dashes, for pale water.
    map.addLayer({
      id: `${LINE_SOURCE_ID}-casing`,
      type: 'line',
      source: LINE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round' },
      paint: { 'line-color': '#0b0d12', 'line-width': 5, 'line-opacity': 0.55 },
    })
    map.addLayer({
      id: `${LINE_SOURCE_ID}-line`,
      type: 'line',
      source: LINE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 2, 'line-dasharray': [2, 1.5] },
    })
    map.addLayer({
      id: `${LINE_SOURCE_ID}-stations`,
      type: 'circle',
      source: LINE_SOURCE_ID,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-radius': 3.5, 'circle-color': '#ffffff', 'circle-stroke-color': '#0b0d12', 'circle-stroke-width': 1.5 },
    })
  }
  for (const m of labels) m.remove()
  labels = []
  const wanted: { text: string, at: [number, number], anchor: 'bottom' | 'center' | 'left', offset: [number, number] }[] = [
    ...(coords.length && s.line?.label ? [{ text: s.line.label, at: coords[Math.floor(coords.length / 2)]!, anchor: 'bottom' as const, offset: [0, -8] as [number, number] }] : []),
    ...places.map(p => p.dot === false
      ? { text: p.name, at: p.coords, anchor: 'center' as const, offset: [0, 0] as [number, number] }
      : p.beside
        ? { text: p.name, at: p.coords, anchor: 'left' as const, offset: [14, -14] as [number, number] }
        : { text: p.name, at: p.coords, anchor: 'bottom' as const, offset: [0, -8] as [number, number] }),
  ]
  if (!wanted.length) return
  const { Marker } = (await import('mapbox-gl')).default
  if (!map || props.steps[active.value] !== s) return
  for (const w of wanted) {
    const el = document.createElement('span')
    el.className = 'pointer-events-none rounded bg-black/60 px-1.5 py-0.5 font-data text-xs font-semibold uppercase tracking-wider text-white'
    el.textContent = w.text
    labels.push(new Marker({ element: el, anchor: w.anchor, offset: w.offset }).setLngLat(w.at).addTo(map))
  }
}

// --- Scroll -> step -------------------------------------------------------------

function cameraFor(s: StoryStep): StoryCamera {
  // A phone shows less of the planet at the same zoom.
  return narrow.value ? { ...s.camera, zoom: s.camera.zoom - 0.7 } : s.camera
}

function enter(i: number) {
  const s = props.steps[i]!
  void store.applyView(s.view)
  countUp(i)
  for (const near of [s, props.steps[i + 1]]) if (near) warmFrames(near)
  if (!map) return
  void drawLine(s)
  const camera = cameraFor(s)
  const to = { ...camera, pitch: camera.pitch ?? 0, bearing: camera.bearing ?? 0 }
  if (reducedMotion()) map.jumpTo(to)
  else map.flyTo({ ...to, duration: 2800, curve: 1.3, essential: true })
}

let ticking = false
function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    ticking = false
    const el = scroller.value
    if (!el) return
    // A step is active while it holds the screen's middle line.
    const mid = el.scrollTop + el.clientHeight / 2
    const i = stepEls.findIndex(s => s && mid >= s.offsetTop && mid < s.offsetTop + s.offsetHeight)
    if (i >= 0 && i !== active.value) {
      active.value = i
      enter(i)
    }
    const s = stepEls[active.value]
    if (s && props.steps[active.value]?.scrub) {
      // The clock runs while the step's middle crosses the screen's middle,
      // with a short hold at either end.
      scrubProgress.value = Math.min(0.999, Math.max(0, (mid - s.offsetTop - el.clientHeight * 0.3) / (s.offsetHeight - el.clientHeight * 0.6)))
    }
  })
}

function goTo(i: number) {
  const s = stepEls[i]
  const el = scroller.value
  if (!s || !el) return
  el.scrollTo({
    top: s.offsetTop + (props.steps[i]?.scrub ? 0 : s.offsetHeight / 2) - el.clientHeight / 2 + 1,
    behavior: reducedMotion() ? 'auto' : 'smooth',
  })
}

function onReady(m: mapboxgl.Map) {
  map = m
  map.jumpTo(cameraFor(props.steps[active.value]!))
  void drawLine(props.steps[active.value]!)
}

onMounted(() => {
  void store.applyView(props.steps[0]!.view)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  for (const m of labels) m.remove()
  map = null
})
</script>

<style scoped>
/* The camera is the story's: no zoom buttons over the date. */
.story-map :deep(.mapboxgl-ctrl-top-right) { display: none; }
</style>
