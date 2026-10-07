<template>
  <!-- Wraps rather than scrolls: on a phone, and on a desktop with the dock and
       compare's second stepper both open, the controls do not fit one row, and a
       horizontally scrolling toolbar hides the one control you are looking for. -->
  <div class="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-default bg-elevated/90 px-2 py-1 shadow-lg backdrop-blur">
    <!-- "When" only: what is drawn is the map's Layers card, where is its
         scope control. UFieldGroup, not UButtonGroup — Nuxt UI v4 renamed it
         and the old name renders an empty comment node. -->
    <UFieldGroup :size="size">
      <UButton
        v-for="item in PERIODS"
        :key="item.value"
        :label="item.label"
        :color="store.period === item.value ? 'primary' : 'neutral'"
        :variant="store.period === item.value ? 'solid' : 'subtle'"
        @click="store.setPeriod(item.value)"
      />
    </UFieldGroup>

    <div class="hidden h-5 w-px bg-accented md:block" />

    <div class="flex items-center gap-1">
      <UButton
        icon="i-mdi-chevron-left"
        variant="ghost"
        color="neutral"
        :size="size"
        :disabled="atStart"
        @click="step(-1)"
      />

      <UInput
        v-model="dateInput"
        type="date"
        :size="size"
        :min="store.coverage?.start ?? undefined"
        :max="store.coverage?.end ?? undefined"
        class="w-36"
      />

      <UButton
        icon="i-mdi-chevron-right"
        variant="ghost"
        color="neutral"
        :size="size"
        :disabled="atEnd"
        @click="step(1)"
      />

      <!-- The end of coverage in whatever period is in force, not a raw date:
           `latest` is the bucket the map can actually show, so in a monthly view
           this lands on the first of the month the archive ends in. -->
      <UButton
        icon="i-mdi-skip-next"
        variant="ghost"
        color="neutral"
        :size="size"
        :disabled="!latest || atEnd"
        :title="latest ? `Jump to the latest ${periodWord} frame` : 'Coverage unknown'"
        @click="goLatest()"
      />
    </div>

    <div class="hidden h-5 w-px bg-accented md:block" />

    <!-- Playback runs until stopped: the playhead is just repeated store.setDate(),
         so stepping or clicking the chart mid-run relocates it rather than fighting
         it, and reaching the end of coverage stops it. Typing in the date
         field does stop it — otherwise the value being typed into is a moving
         target. -->
    <div class="flex items-center gap-2">
      <UButton
        :icon="playing ? 'i-mdi-pause' : 'i-mdi-play'"
        :color="playing ? 'primary' : 'neutral'"
        :variant="playing ? 'solid' : 'ghost'"
        :size="size"
        :disabled="!canPlay"
        :title="playing ? 'Stop' : 'Play'"
        @click="playing ? stop() : play()"
      />
      <USlider
        v-if="!narrow"
        v-model="fps"
        :min="MIN_FPS"
        :max="MAX_FPS"
        :step="1"
        :size="size"
        class="w-20"
        :aria-label="`Animation speed, ${fps} frames per second`"
      />
      <span class="hidden w-12 shrink-0 text-xs tabular-nums text-muted sm:inline">{{ fps }} fps</span>
    </div>

    <!-- The input still picks a day; this is what that day's bucket covers. -->
    <span v-if="store.period !== 'daily' && store.selectedDate" class="hidden pr-1 text-xs text-muted sm:inline">
      {{ bucketLabel(store.selectedDate, store.period) }}
    </span>

    <div class="hidden h-5 w-px bg-accented md:block" />

    <!-- Compare with a second DATE (swipe compare, a second map). The second
         PLACE is a "where" and sits beside the scope control on the map. Each
         button's hover text carries its own shortcut. Only the date is the user's to set on
         the second map: variable, period and
         colour range are shared, so the legend describes both halves. The
         second stepper is sky-tinted to match the chart's CMP line and the
         right half of the divider. -->
    <div class="flex items-center gap-1">
      <span class="hidden pl-1 text-xs text-muted sm:inline">Compare</span>
      <UButton
        icon="i-mdi-compare-horizontal"
        :label="narrow ? undefined : 'Date'"
        aria-label="Compare with another date"
        :color="store.compareDate ? 'primary' : 'neutral'"
        :variant="store.compareDate ? 'solid' : 'subtle'"
        :size="size"
        :disabled="!store.selectedDate"
        :title="dateTitle"
        @click="store.toggleCompare()"
      />
      <CompareHint :text="dateHint" :size="size" />
      <template v-if="store.compareDate">
        <UButton
          icon="i-mdi-chevron-left"
          variant="ghost"
          color="neutral"
          :size="size"
          :disabled="compareAtStart"
          @click="stepCompare(-1)"
        />
        <UInput
          v-model="compareInput"
          type="date"
          :size="size"
          :min="store.coverage?.start ?? undefined"
          :max="store.coverage?.end ?? undefined"
          class="w-36"
          :ui="{ base: 'ring-sky-400/70' }"
          aria-label="Compare date"
          :title="`Or ${alt}-click the chart`"
        />
        <UButton
          icon="i-mdi-chevron-right"
          variant="ghost"
          color="neutral"
          :size="size"
          :disabled="compareAtEnd"
          @click="stepCompare(1)"
        />
      </template>
    </div>

    <!-- Exports the series the chart is drawing, at the current variable and
         period, rather than issuing a request of its own: a second path to the
         same numbers would be a second definition of "the weekly mean".
         `ml-auto` parks it at the far right, away from the controls that change
         what is plotted — it is the one button here that leaves the app. -->
    <UButton
      icon="i-mdi-download"
      variant="ghost"
      color="neutral"
      :size="size"
      class="ml-auto shrink-0"
      :disabled="!canExport"
      :aria-label="`Download this ${periodWord} series as CSV`"
      :title="canExport ? `Download this ${periodWord} series as CSV` : 'Nothing plotted to download'"
      @click="exportSeries()"
    >
      <span class="hidden sm:inline">Download data</span>
    </UButton>
  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { useMainStore } from '~/stores/main'
import { PERIODS, bucketLabel, bucketStart, shiftBuckets } from '~/utils/periods'
import { MAX_FPS, MIN_FPS, usePlayback } from '~/composables/usePlayback'
import { cellSlug, downloadCsv, seriesCsv, slug } from '~/utils/csv'

const store = useMainStore()

const { playing, fps, canPlay, play, stop } = usePlayback()

/** Finger-sized on a phone, compact everywhere else. */
const { narrow } = useViewport()
// 'sm', not larger: the time bar shares the chart's pane, and every row it
// wraps onto is a row the chart loses on a phone.
const size = computed(() => (narrow.value ? 'sm' : 'xs'))

const alt = useAltKey()
const dateTitle = computed(() => (store.compareDate
  ? `Stop comparing. Drag the divider to swipe between the two dates; ${alt.value}-click the chart to move the right-hand map.`
  : `Split the map: the same view on another date, side by side. Then ${alt.value}-click the chart to set that date.`))

const dateHint = computed(() => (store.compareDate
  ? `${alt.value}-click the chart to move the right-hand map's date.`
  : `Split the map by date; then ${alt.value}-click the chart to set the second date.`))

const dateInput = computed({
  get: () => store.selectedDate ?? '',
  set: (value: string) => { if (value) { stop(); store.setDate(clamp(value)) } },
})

// Compared bucket-wise: in a weekly or monthly view the first and last buckets
// usually start before / end after the ingested range, so comparing raw dates
// would leave the arrows enabled forever.
const atStart = computed(() => store.selectedDate === snapped(store.coverage?.start))
const latest = computed(() => snapped(store.coverage?.end))
const atEnd = computed(() => store.selectedDate === latest.value)

function snapped(iso: string | null | undefined): string | null {
  return iso ? bucketStart(iso, store.period) : null
}

function clamp(iso: string): string {
  const { start, end } = store.coverage ?? {}
  if (start && iso < start) return start
  if (end && iso > end) return end
  return iso
}

function step(buckets: number) {
  if (!store.selectedDate) return
  store.setDate(clamp(shiftBuckets(store.selectedDate, store.period, buckets)))
}

// Like the arrows, this does not stop playback: the playhead is just repeated
// `store.setDate()`, so a jump relocates it rather than fighting it.
function goLatest() {
  if (latest.value) store.setDate(latest.value)
}

const compareInput = computed({
  get: () => store.compareDate ?? '',
  set: (value: string) => { if (value) setCompare(value) },
})

const compareAtStart = computed(() => store.compareDate === snapped(store.coverage?.start))
const compareAtEnd = computed(() => store.compareDate === latest.value)

function stepCompare(buckets: number) {
  if (!store.compareDate) return
  setCompare(shiftBuckets(store.compareDate, store.period, buckets))
}

/**
 * Move the compare map, reporting one event for where it came to rest.
 *
 * A trailing debounce, like the colour range: stepping ten weeks back is ten
 * clicks and one decision.
 */
let compareTimer: ReturnType<typeof setTimeout> | null = null

function setCompare(iso: string) {
  store.setCompareDate(clamp(iso))
  if (compareTimer) clearTimeout(compareTimer)
  compareTimer = setTimeout(() => {
    compareTimer = null
    trackEvent('compare_date_changed', {
      date: store.compareDate,
      mapDate: store.selectedDate,
      variable: store.variable,
      period: store.period,
    })
  }, 1000)
}

onBeforeUnmount(() => {
  if (compareTimer) clearTimeout(compareTimer)
  // The playhead is page-wide now; the component that shows it stops it on the way out.
  stop()
})

const canExport = computed(() => (store.activeSeries?.dates.length ?? 0) > 0)

const periodWord = computed(() => ({ daily: 'daily', weekly: 'weekly', monthly: 'monthly' })[store.period])

/**
 * Save the plotted series.
 *
 * The filename carries everything that decides what the numbers ARE — variable,
 * period, subject and span — because a folder of `timeseries.csv` files is
 * indistinguishable a week later, and the two subjects a series can have (a
 * clicked cell, a named region) are not comparable numbers.
 */
function exportSeries() {
  const series = store.activeSeries
  if (!series?.dates.length) return
  // B only once it has loaded; a file must not name a cell it has no column for.
  const second = store.activeSecondSeries?.dates.length ? store.activeSecondSeries : null
  const pointSlug = (s: typeof series) => (s.cell ? cellSlug(s.cell) : 'point')
  const aSlug = store.scope === 'region'
    ? slug(store.activeRegionMeta?.label ?? store.activeRegion ?? 'region')
    : pointSlug(series)
  const bSlug = second && (store.secondRegion
    ? slug(store.secondRegionMeta?.label ?? store.secondRegion)
    : pointSlug(second))
  const subject = bSlug ? `${aSlug}_vs_${bSlug}` : aSlug
  const dates = [...series.dates, ...(second?.dates ?? [])].sort()
  const span = `${dates[0]}_${dates[dates.length - 1]}`
  // Worth knowing precisely because it is the feature least visible in the UI —
  // one ghost icon — and the one whose removal nobody would notice until
  // somebody complained.
  trackEvent('csv_downloaded', {
    kind: 'series',
    variable: store.variable,
    quantity: store.activeQuantity,
    period: store.period,
    scope: store.scope,
    rows: series.dates.length,
    points: second ? 2 : 1,
  })
  downloadCsv(
    `${store.activeQuantity ?? store.variable}_${store.period}_${subject}_${span}.csv`,
    seriesCsv(series, {
      // The column header names what the numbers ARE, which in region scope is
      // not the variable: `mhw` there is a percentage of area, and a column
      // headed `mhw` would read back as a category. Same reason the filename
      // below carries it.
      variable: store.activeQuantity ?? store.variable,
      period: store.period,
      unit: store.seriesUnitLabel,
      precision: store.seriesPrecision,
      second,
    }),
  )
}
</script>
