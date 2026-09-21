<template>
  <div
    v-if="stops.length || reason"
    class="rounded-lg border border-default bg-elevated/90 px-3 py-2 shadow-lg backdrop-blur"
  >
    <!--
      A land layer that cannot be drawn on this bucket says why, in the legend's
      own place. The map REMOVES the layer rather than leaving it on its last
      frame (Mapbox keeps the previous image on a 404), and a layer that vanishes
      without a word reads as a bug.
    -->
    <div v-if="reason" class="w-48">
      <span class="text-[11px] font-medium text-muted">{{ title }}</span>
      <p class="mt-1 text-[11px] leading-snug text-muted">
        {{ reason }}
      </p>
    </div>

    <!--
      A categorical key has no range to edit, so its title is a plain label. The
      continuous case moves the title inside the popover trigger instead, so the
      whole block — title, Customize chip, bar and ticks — is one hit target.
    -->
    <div v-else-if="categorical" class="mb-1 flex items-center gap-1.5">
      <span class="text-[11px] font-medium text-muted">{{ title }}</span>
    </div>

    <!--
      A categorical scale is a key, not a ramp. Its five classes have names, and
      the names are the point — "Cat 3" means Severe, which is what the map is
      being read for. There is also nothing here to re-range: the classes are the
      values, so the popover, the slider and the tick row are all absent rather
      than disabled.
    -->
    <div v-if="!reason && categorical" class="flex w-48 flex-col gap-0.5">
      <!--
        The class the raster cannot carry, and therefore the one the key has to.
        `mhw`'s WebP holds land, ice AND heatwave-free ocean at alpha 0 alike, so
        the map draws code 0 as a flat fill under the raster instead — which
        means the commonest thing on screen is the one colour the five stops
        below do not account for. It leads rather than trails the list because it
        is the floor of the same ordinal scale: 0, then 1..5.
      -->
      <div
        v-if="backgroundColor"
        class="flex items-center gap-1.5 text-[11px] text-muted"
      >
        <span
          class="h-2.5 w-4 shrink-0 rounded-sm"
          :style="{ background: backgroundColor }"
        />
        <span class="tabular-nums text-default">0</span>
        <span>no heatwave</span>
      </div>
      <div
        v-for="stop in stops"
        :key="stop.value"
        class="flex items-center gap-1.5 text-[11px] text-muted"
      >
        <span
          class="h-2.5 w-4 shrink-0 rounded-sm"
          :style="{ background: stop.color }"
        />
        <span class="tabular-nums text-default">{{ stop.value }}</span>
        <span>{{ stop.label }}</span>
      </div>
    </div>

    <UPopover v-else-if="!reason" :content="{ side: 'top', align: 'center' }">
      <!--
        A real button, not the bar with a click handler: this is the only way to
        reach the range control, so it has to be focusable and it has to say what
        it does. It also has to *look* editable — a gradient reads as a legend,
        which is a thing you consult, not a thing you press — so the affordance
        is spelled out in a chip beside the title rather than left to the cursor.
      -->
      <button
        type="button"
        class="group block w-48 cursor-pointer rounded ring-offset-2 ring-offset-elevated focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        :aria-label="`Adjust the ${meta?.shortName ?? ''} colour range`"
        title="Adjust the colour range"
      >
        <span class="mb-1 flex items-center gap-1.5">
          <span class="text-[11px] font-medium text-muted">{{ title }}</span>
          <!-- Marks a range that is not domain.yml's, so a map read at ±1 is never
               mistaken for one read at the default ±3. -->
          <span v-if="isCustom" class="text-[11px] text-primary">custom</span>
          <span
            class="ml-auto flex items-center gap-0.5 rounded px-1 py-px text-[10px] text-muted ring-1 ring-default transition-colors group-hover:text-default group-hover:ring-primary group-focus-visible:text-default"
          >
            <UIcon name="i-mdi-tune-variant" class="size-3" />
            Customize
          </span>
        </span>
        <span
          class="block h-2.5 w-full rounded ring-offset-1 ring-offset-elevated transition-shadow group-hover:ring-1 group-hover:ring-primary"
          :style="{ background: gradient }"
        />
        <span class="mt-1 flex justify-between text-[11px] text-muted">
          <span v-for="(tick, i) in ticks" :key="i">{{ formatTick(tick) }}</span>
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
              @click="store.resetScale(name)"
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
          <!--
            The slider moves the range in the layer's OWN units — log2 for the
            rainfall ratio, so a halving and a doubling are the same drag. It
            shows no numbers, so there is nothing to convert; the fields below
            and every tick do.
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
              :model-value="toField(scale.vmin)"
              type="number"
              size="xs"
              class="w-full"
              :step="fieldStep"
              :min="toField(bounds.vmin)"
              :max="toField(bounds.vmax)"
              :aria-label="`Range minimum${percent ? ' (% of normal)' : ''}`"
              @update:model-value="commit(fromField($event), scale.vmax)"
            />
            <span class="text-xs text-muted">to</span>
            <UInput
              :model-value="toField(scale.vmax)"
              type="number"
              size="xs"
              class="w-full"
              :step="fieldStep"
              :min="toField(bounds.vmin)"
              :max="toField(bounds.vmax)"
              :aria-label="`Range maximum${percent ? ' (% of normal)' : ''}`"
              @update:model-value="commit(scale.vmin, fromField($event))"
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
      The third state: a value exists but no meaningful departure from normal
      does, drawn flat grey. Two variables have one, for different reasons — the
      ocean anomaly at the seasonal ice edge, which has no climatology, and the
      rainfall ratio where the normal is too small to divide by — so the label is
      `domain.yml`'s, not written here. Without it the grey reads as land.
    -->
    <div
      v-if="!reason && meta?.encoding?.sentinel != null && meta?.noValueLabel && store.domain?.noClimColor"
      class="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted"
    >
      <span
        class="h-2.5 w-2.5 shrink-0 rounded-sm border border-default"
        :style="{ background: store.domain.noClimColor }"
      />
      <span>{{ meta.noValueLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { quantise, useMainStore, type LayerName } from '~/stores/main'
import { formatLog2Percent, parseLog2Percent } from '~/utils/land'

/**
 * The legend for ONE layer. Defaults to the ocean variable on screen; the land
 * overlay mounts a second instance with its own layer, so the two scales —
 * which cannot honestly share one legend (ocean anomaly saturates at +/-3, land
 * at +/-8) — sit side by side and are each re-ranged independently.
 */
const props = defineProps<{
  variable?: LayerName
  /** Shown instead of the ramp when the layer cannot be drawn on this bucket. */
  reason?: string | null
  /** A prefix for the title, e.g. "Land", to tell two legends apart. */
  label?: string
}>()

const store = useMainStore()

/** The layer this legend describes. */
const name = computed<LayerName>(() => props.variable ?? store.variable)

/**
 * The layer's stops, spread over the range in force. The colours are the
 * server's; only the value each one sits at follows the user's range.
 */
const stops = computed(() => store.stopsFor(name.value))
const meta = computed(() => store.domain?.variables?.[name.value])
const categorical = computed(() => store.isCategorical(name.value))
/**
 * `log2_percent`: the rainfall ratio, ranged in log2 and printed as percent of
 * normal. Everything a person reads — ticks, the number fields, the limits line
 * — goes through `formatTick` / `toField`; the stored range never changes unit.
 */
const percent = computed(() => meta.value?.display === 'log2_percent')
/**
 * What the map paints under the raster for this variable, where it paints
 * anything — `mhw`'s no-heatwave blue, NOAA's own. Read from `/domain` rather
 * than written here, so the key and the fill cannot come to disagree about
 * which blue it is. Null for every continuous variable.
 */
const backgroundColor = computed(() => meta.value?.backgroundColor ?? null)

const scale = computed(() => store.scaleFor(name.value))
const bounds = computed(() => store.scaleBoundsFor(name.value))
const isCustom = computed(() => store.scaleIsCustom(name.value))
/** domain.yml's range — what Reset returns to. */
const defaults = computed(() => ({ vmin: meta.value?.vmin ?? 0, vmax: meta.value?.vmax ?? 1 }))
/**
 * Coarser than the encoding on purpose — see `rangeStep` in the store. The
 * slider and both number fields share it, so a value typed in can never sit off
 * the slider's grid and get silently snapped when the popover re-renders.
 */
const step = computed(() => store.scaleStepFor(name.value))

/** The number fields' own step: whole percent for the ratio, else the range's. */
const fieldStep = computed(() => (percent.value ? 1 : step.value))

/** A range value as the number field shows it. */
function toField(value: number): number {
  return percent.value ? Math.round(100 * 2 ** value) : value
}

/** A number field's value back into the layer's own units. */
function fromField(value: unknown): number {
  return percent.value ? parseLog2Percent(String(value)) : Number(value)
}

const title = computed(() => {
  const v = meta.value
  if (!v) return ''
  // The degree sign belongs to a temperature, not to a category. `mhw` reads
  // "MHW (category)"; the old expression produced "(°category)". The ratio's
  // number is log2 but what anybody reads is percent of normal.
  const unit = percent.value ? '% of normal' : (store.unitLabelFor(name.value) || v.units)
  return `${props.label ? `${props.label} · ` : ''}${v.shortName} (${unit})`
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

const ticks = computed(() => {
  const { vmin, vmax } = scale.value
  const mid = (vmin + vmax) / 2
  return [vmin, (vmin + mid) / 2, mid, (mid + vmax) / 2, vmax]
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
    ...store.presetsFor(name.value).map(preset => ({
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
    variable: name.value,
    source: chip.reset ? 'default' : 'preset',
    preset: chip.label,
    vmin: chip.vmin,
    vmax: chip.vmax,
  })
  if (chip.reset) store.resetScale(name.value)
  else store.setScale(name.value, chip.vmin, chip.vmax)
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
    trackEvent('color_range_changed', { variable: name.value, source, vmin, vmax })
  }, 1000)
}
onBeforeUnmount(() => clearTimeout(rangeTimer))

/** All clamping lives in the store, so slider and keyboard agree exactly. */
function commit(vmin: unknown, vmax: unknown, source: 'slider' | 'field' = 'field') {
  store.setScale(name.value, Number(vmin), Number(vmax))
  trackRange(source)
}

function onSlide(value: number | number[] | undefined) {
  if (Array.isArray(value)) commit(value[0], value[1], 'slider')
}

/**
 * A signed `+` only makes sense on a scale centred at zero. SST runs -2..32,
 * where "+17" would be noise; an anomaly runs -3..+3, where the sign is the
 * whole point. "Is a departure" is read off the baseline's statistic rather
 * than the variable's name, so the land anomalies get it with no list to edit.
 */
function formatTick(tick: number): string {
  if (percent.value) return formatLog2Percent(tick)
  const rounded = Math.round(tick * 10) / 10
  const signed = meta.value?.baseline?.statistic === 'mean' && rounded > 0
  return `${signed ? '+' : ''}${rounded}`
}

// localStorage is browser-only, and this component mounts after /domain has
// landed — so the remembered ranges are clamped against a known encoding.
onMounted(() => store.loadScales())
</script>
