<template>
  <!--
    One line, not a stacked block: the legend sits over the middle of the map,
    and every row of height it takes is ocean it hides. Title, ramp and the
    no-climatology key read left to right; the mid ticks are gone because the
    two ends and a diverging ramp's white centre already say where zero is.
  -->
  <div
    v-if="stops.length && !legend.hidden.value"
    class="flex items-center gap-3 whitespace-nowrap rounded-t-lg border border-b-0 border-default bg-elevated/90 px-3 py-1.5 shadow-lg backdrop-blur"
  >
    <!--
      A categorical scale is a key, not a ramp. Its five classes have names, and
      the names are the point — "Cat 3" means Severe, which is what the map is
      being read for. There is also nothing here to re-range: the classes are the
      values, so the popover and the slider are absent rather than disabled.
    -->
    <template v-if="categorical">
      <span class="text-[11px] font-medium text-muted">{{ title }}</span>
      <!--
        The class the raster cannot carry, and therefore the one the key has to.
        `mhw`'s WebP holds land, ice AND heatwave-free ocean at alpha 0 alike, so
        the map draws code 0 as a flat fill under the raster instead — which
        means the commonest thing on screen is the one colour the five stops
        do not account for. It leads because it is the floor of the same
        ordinal scale: 0, then 1..5.
      -->
      <span
        v-if="backgroundColor"
        class="flex items-center gap-1 text-[11px] text-muted"
        title="Category 0"
      >
        <span class="h-2.5 w-3 shrink-0 rounded-sm" :style="{ background: backgroundColor }" />
        none
      </span>
      <span
        v-for="stop in stops"
        :key="stop.value"
        class="flex items-center gap-1 text-[11px] text-muted"
        :title="`Category ${stop.value}`"
      >
        <span class="h-2.5 w-3 shrink-0 rounded-sm" :style="{ background: stop.color }" />
        {{ stop.label }}
      </span>
    </template>

    <UPopover v-else :content="{ side: 'top', align: 'center' }">
      <!--
        A real button, not the bar with a click handler: this is the only way to
        reach the range control, so it has to be focusable and it has to say what
        it does. It also has to *look* editable — a gradient reads as a legend,
        which is a thing you consult, not a thing you press — so the tune icon
        sits in a ring at the end of the row rather than being left to the cursor.
      -->
      <button
        type="button"
        class="group flex cursor-pointer items-center gap-2 rounded ring-offset-2 ring-offset-elevated focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        :aria-label="`Adjust the ${meta?.shortName ?? ''} colour range`"
        title="Adjust the colour range"
      >
        <span class="text-[11px] font-medium text-muted">{{ title }}</span>
        <!-- Marks a range that is not domain.yml's, so a map read at ±1 is never
             mistaken for one read at the default ±3. -->
        <span v-if="isCustom" class="text-[11px] text-primary">custom</span>
        <span class="text-[11px] tabular-nums text-muted">{{ formatTick(scale.vmin) }}</span>
        <span
          class="block h-2.5 w-40 rounded ring-offset-1 ring-offset-elevated transition-shadow group-hover:ring-1 group-hover:ring-primary"
          :style="{ background: gradient }"
        />
        <span class="text-[11px] tabular-nums text-muted">{{ formatTick(scale.vmax) }}</span>
        <span
          class="flex items-center rounded p-0.5 text-muted ring-1 ring-default transition-colors group-hover:text-default group-hover:ring-primary group-focus-visible:text-default"
        >
          <UIcon name="i-mdi-tune-variant" class="size-3" />
        </span>
      </button>

      <template #content>
        <div class="w-64 p-3">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-xs font-medium">Colour range</span>
            <UButton
              v-if="isCustom"
              label="Reset"
              size="xs"
              variant="subtle"
              color="neutral"
              @click="store.resetScale(store.variable)"
            />
          </div>

          <!--
            Named bands, one click each. They exist because the slider and the
            number fields say *that* the range is adjustable without saying what
            range is worth asking for — "where is the ocean between 20 and 32" is
            a question people have, and typing two numbers is not how they ask
            it. Narrowing CLAMPS the rest of the ocean to the end colours rather
            than hiding it; the band gets all 256 ramp entries, which is what
            makes it readable.

            A plain wrapping row rather than the `UFieldGroup` the toggles
            elsewhere use: five labels do not fit one 232px line as a joined pill
            strip, and a popover is the wrong place for horizontal overflow.
          -->
          <div v-if="chips.length > 1" class="mb-3 flex flex-wrap gap-1">
            <UButton
              v-for="chip in chips"
              :key="chip.label"
              :label="chip.label"
              size="xs"
              :color="chip.active ? 'primary' : 'neutral'"
              :variant="chip.active ? 'solid' : 'subtle'"
              @click="applyChip(chip)"
            />
          </div>

          <!--
            The images carry data rather than colour, so this is a paint change:
            no frame is refetched and no cached image is invalidated. That is
            what makes a slider — which fires on every drag frame — affordable.
          -->
          <USlider
            :model-value="[scale.vmin, scale.vmax]"
            :min="bounds.vmin"
            :max="bounds.vmax"
            :step="step"
            size="xs"
            class="my-3"
            aria-label="Colour range"
            @update:model-value="onSlide"
          />

          <div class="flex items-center gap-2">
            <UInput
              :model-value="scale.vmin"
              type="number"
              size="xs"
              class="w-full"
              :step="step"
              :min="bounds.vmin"
              :max="bounds.vmax"
              aria-label="Range minimum"
              @update:model-value="commit($event, scale.vmax)"
            />
            <span class="text-xs text-muted">to</span>
            <UInput
              :model-value="scale.vmax"
              type="number"
              size="xs"
              class="w-full"
              :step="step"
              :min="bounds.vmin"
              :max="bounds.vmax"
              aria-label="Range maximum"
              @update:model-value="commit(scale.vmin, $event)"
            />
          </div>

          <p class="mt-2 text-[11px] text-muted">
            Default {{ formatTick(defaults.vmin) }} to {{ formatTick(defaults.vmax) }}.
            Limits {{ formatTick(bounds.vmin) }} to {{ formatTick(bounds.vmax) }}.
          </p>
        </div>
      </template>
    </UPopover>

    <!--
      Only the anomaly has a third state. SST is defined on every ocean cell in
      the box, but the 1991-2020 climatology stops at the seasonal ice edge, so
      about 3% of the ocean has a temperature and no anomaly. Those cells are
      flat grey on the map, which needs saying — otherwise they read as land.
    -->
    <div
      v-if="store.variable === 'anom' && store.domain?.noClimColor"
      class="flex items-center gap-1.5 border-l border-default pl-3 text-[11px] text-muted"
    >
      <span
        class="h-2.5 w-2.5 rounded-sm border border-default"
        :style="{ background: store.domain.noClimColor }"
      />
      <span>no climatology</span>
    </div>

    <!-- Hides the whole legend, for a clean screenshot. The way back is a
         button in the map's top-left control column, which a screenshot
         already carries, so hiding this leaves the bottom of the map bare. -->
    <button
      type="button"
      class="-mr-1 flex cursor-pointer items-center rounded p-0.5 text-muted transition-colors hover:text-default focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      aria-label="Hide the legend"
      title="Hide the legend"
      @click="legend.setHidden(true)"
    >
      <UIcon name="i-mdi-close" class="size-3.5" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { quantise, useMainStore } from '~/stores/main'

const store = useMainStore()
const legend = useLegend()

/**
 * The active variable's stops, spread over the range in force — sst is
 * sequential, anom diverging. The colours are the server's; only the value each
 * one sits at follows the user's range.
 */
const stops = computed(() => store.activeStops)
const meta = computed(() => store.domain?.variables?.[store.variable])
const categorical = computed(() => store.activeIsCategorical)
/**
 * What the map paints under the raster for this variable, where it paints
 * anything — `mhw`'s no-heatwave blue, NOAA's own. Read from `/domain` rather
 * than written here, so the key and the fill cannot come to disagree about
 * which blue it is. Null for every continuous variable.
 */
const backgroundColor = computed(() => meta.value?.backgroundColor ?? null)

const scale = computed(() => store.activeScale)
const bounds = computed(() => store.scaleBoundsFor(store.variable))
const isCustom = computed(() => store.scaleIsCustom(store.variable))
/** domain.yml's range — what Reset returns to. */
const defaults = computed(() => ({ vmin: meta.value?.vmin ?? 0, vmax: meta.value?.vmax ?? 1 }))
/**
 * Coarser than the encoding on purpose — see `rangeStep` in the store. The
 * slider and both number fields share it, so a value typed in can never sit off
 * the slider's grid and get silently snapped when the popover re-renders.
 */
const step = computed(() => store.scaleStepFor(store.variable))

const title = computed(() => {
  const v = meta.value
  if (!v) return ''
  // The degree sign belongs to a temperature, not to a category. `mhw` reads
  // "MHW (category)"; the old expression produced "(°category)".
  const unit = store.unitLabelFor(store.variable) || v.units
  return `${v.shortName} (${unit})`
})

/**
 * Positions the stops by index, not by value — which stays correct because
 * `stopsFor` re-labels an evenly spaced ramp and keeps it evenly spaced. A
 * non-uniform stop list would need positioning by value instead.
 */
const gradient = computed(() => {
  const list = stops.value
  if (!list.length) return ''
  const parts = list.map((s, i) => `${s.color} ${((i / (list.length - 1)) * 100).toFixed(1)}%`)
  return `linear-gradient(to right, ${parts.join(', ')})`
})

/**
 * The band chips: `domain.yml`'s presets, with the default range prepended.
 *
 * The default is synthesised from `vmin`/`vmax` rather than declared alongside
 * the others, so the file holds one definition of it instead of two that drift
 * apart the first time one is edited. It is also the only chip that *clears*
 * the override rather than setting one — which is what makes the `custom` badge
 * and the Reset button agree with the chips without a third rule.
 *
 * A preset is active on the range in force, compared through the same
 * quantisation `setScale` applied on the way in. Every declared band is a step
 * multiple today, so a bare `===` would work by luck; this keeps working when
 * someone adds one at 24.05.
 */
const chips = computed(() => {
  const custom = isCustom.value
  const { vmin, vmax } = scale.value
  const same = (a: number, b: number) =>
    quantise(a, step.value) === quantise(b, step.value)
  return [
    { label: 'Default', ...defaults.value, reset: true, active: !custom },
    ...store.presetsFor(store.variable).map(preset => ({
      ...preset,
      reset: false,
      active: custom && same(vmin, preset.vmin) && same(vmax, preset.vmax),
    })),
  ]
})

function applyChip(chip: { label?: string, vmin: number, vmax: number, reset: boolean }) {
  // The label, not just the numbers: whether people reach for `Coral 24-32` by
  // name is the question the presets were added to answer, and a bare pair of
  // bounds cannot distinguish a chip from a drag that landed on the same place.
  trackEvent('color_range_changed', {
    variable: store.variable,
    source: chip.reset ? 'default' : 'preset',
    preset: chip.label,
    vmin: chip.vmin,
    vmax: chip.vmax,
  })
  if (chip.reset) store.resetScale(store.variable)
  else store.setScale(store.variable, chip.vmin, chip.vmax)
}

/**
 * One event per gesture, not per frame.
 *
 * The slider emits on every pointer move, so capturing in `commit` directly
 * would send a hundred events for one drag — the flooding `/image` and the
 * playhead are excluded for. A trailing debounce collapses a drag into the
 * range it came to rest on, which is the only part anybody would ask about; a
 * typed value lands the same way one second later.
 */
let rangeTimer: ReturnType<typeof setTimeout> | undefined
function trackRange(source: 'slider' | 'field') {
  clearTimeout(rangeTimer)
  rangeTimer = setTimeout(() => {
    const { vmin, vmax } = scale.value
    trackEvent('color_range_changed', { variable: store.variable, source, vmin, vmax })
  }, 1000)
}
onBeforeUnmount(() => clearTimeout(rangeTimer))

/** All clamping lives in the store, so slider and keyboard agree exactly. */
function commit(vmin: unknown, vmax: unknown, source: 'slider' | 'field' = 'field') {
  store.setScale(store.variable, Number(vmin), Number(vmax))
  trackRange(source)
}

function onSlide(value: number | number[] | undefined) {
  if (Array.isArray(value)) commit(value[0], value[1], 'slider')
}

/**
 * A signed `+` only makes sense on a scale centred at zero. SST runs -2..32,
 * where "+17" would be noise; the anomaly runs -3..+3, where the sign is the
 * whole point.
 */
function formatTick(tick: number): string {
  const rounded = Math.round(tick * 10) / 10
  const signed = store.variable === 'anom' && rounded > 0
  return `${signed ? '+' : ''}${rounded}`
}

// localStorage is browser-only, and this component mounts after /domain has
// landed — so the remembered ranges are clamped against a known encoding.
onMounted(() => {
  store.loadScales()
  legend.restore()
})
</script>
