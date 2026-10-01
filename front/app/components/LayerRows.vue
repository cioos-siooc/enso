<template>
  <!-- The rows of `LayerControl`'s card, split out so the desktop card and the
       phone popover draw the same buttons. -->
  <div v-if="store.domain" class="grid grid-cols-[auto_auto] items-center gap-x-2 gap-y-1.5">
    <span class="text-xs text-muted">Ocean</span>
    <!--
      UFieldGroup, not UButtonGroup: Nuxt UI v4 renamed it and the old name
      resolves to an empty comment node instead of erroring, so the control
      simply vanishes from the DOM.
    -->
    <UFieldGroup :size="size">
      <UButton
        v-for="item in OCEAN_VARIABLES"
        :key="item.value"
        :label="item.label"
        :color="store.variable === item.value ? 'primary' : 'neutral'"
        :variant="store.variable === item.value ? 'solid' : 'subtle'"
        :disabled="!store.variableReady(item.value)"
        :title="store.variableReady(item.value) ? item.title : item.pending"
        @click="store.setVariable(item.value)"
      />
    </UFieldGroup>

    <!-- Land is not a fourth ocean variable: it is drawn OVER whichever ocean
         field is showing, so El Nino's ocean anomaly and its land response can
         be read on one map. Hence a row of its own with an Off. -->
    <span class="text-xs text-muted">Land</span>
    <UFieldGroup :size="size">
      <UButton
        label="Off"
        :color="store.landLayer === null ? 'primary' : 'neutral'"
        :variant="store.landLayer === null ? 'solid' : 'subtle'"
        :title="available ? 'No land overlay' : unavailableTitle"
        @click="store.setLandLayer(null)"
      />
      <UButton
        v-for="item in LAND_SOURCES"
        :key="item.value"
        :label="item.label"
        :color="store.landLayer === item.value ? 'primary' : 'neutral'"
        :variant="store.landLayer === item.value ? 'solid' : 'subtle'"
        :disabled="!available"
        :title="available ? item.title : unavailableTitle"
        @click="store.setLandLayer(item.value)"
      />
    </UFieldGroup>

    <!-- Value | Anomaly is the land layer's own choice, independent of the
         ocean row: SST anomaly over the sea can sit beside absolute precipitation on
         land. Hidden while the overlay is off, since it would describe nothing. -->
    <template v-if="store.landLayer">
      <span />
      <UFieldGroup :size="size">
        <UButton
          v-for="mode in landModesFor(store.landLayer)"
          :key="mode"
          :label="modeLabel(mode)"
          :color="store.landMode === mode ? 'primary' : 'neutral'"
          :variant="store.landMode === mode ? 'solid' : 'subtle'"
          :disabled="!modeReady(mode)"
          :title="modeReady(mode) ? modeTitle(mode) : 'The 1991-2020 land climatology has not been built yet'"
          @click="store.setLandMode(mode)"
        />
      </UFieldGroup>
    </template>
  </div>
</template>

<script lang="ts">
import { useMainStore } from '~/stores/main'
import { landModesFor, type LandMode, type LandSource } from '~/utils/land'

// Anomaly first, and it is what the app opens on: the question this dashboard
// exists for is "how far from normal is it", and absolute SST is the reference
// view you switch to. MHW comes last because it is the narrowest question of the
// three — not "how warm" but "is this officially a heatwave, and how bad" — and
// it is the one most likely to be unavailable, being a separate archive.
//
// `pending` is the tooltip shown while a variable's precondition is unmet. Each
// says what is missing rather than just greying out, because in both cases the
// failure mode without the gate is silent wrong data, not an error — see
// `variableReady` in the store.
export const OCEAN_VARIABLES = [
  {
    value: 'anom' as const,
    label: 'Anomaly',
    title: 'Difference from the 1991-2020 daily climatology',
    pending: 'Anomaly needs the full 366-day climatology, which is still loading',
  },
  {
    value: 'sst' as const,
    label: 'SST',
    title: 'Sea surface temperature',
  },
  {
    value: 'mhw' as const,
    label: 'MHW',
    title: 'NOAA marine heatwave category, 1 (Moderate) to 5 (Beyond extreme)',
    pending: 'Marine heatwave needs its own archive, which has not finished ingesting',
  },
]

export const LAND_SOURCES: Array<{ value: LandSource, label: string, title: string }> = [
  { value: 'tmax', label: 'Tmax', title: 'Daily maximum temperature on land (NOAA CPC)' },
  { value: 'tmin', label: 'Tmin', title: 'Daily minimum temperature on land (NOAA CPC)' },
  // Precipitation, not rain: CPC's gauge analysis is total precipitation, snow
  // included as its liquid-water equivalent.
  { value: 'precip', label: 'Precip', title: 'Precipitation on land, rain and snow as water (NOAA CPC)' },
]
</script>

<script setup lang="ts">
defineProps<{ size: 'xs' | 'sm' }>()

const store = useMainStore()

/** Whether this server has land data at all — `/coverage.land` is null if not. */
const available = computed(() => Boolean(store.coverage?.land))
const unavailableTitle = 'Land data is not loaded on this server'

/**
 * Precipitation has two departures, so its buttons say which the map will show:
 * "% of normal" and "mm vs normal", not "Anomaly", which would not say which.
 */
function modeLabel(mode: LandMode): string {
  if (mode === 'value') return 'Value'
  if (store.landLayer !== 'precip') return 'Anomaly'
  return mode === 'difference' ? 'mm vs normal' : '% of normal'
}

function modeTitle(mode: LandMode): string {
  if (mode === 'value') return store.landLayer === 'precip' ? 'Precipitation in mm/day' : 'Temperature in °C'
  if (store.landLayer !== 'precip') return 'Difference from the 1991-2020 normal for the time of year'
  return mode === 'difference'
    ? 'Precipitation minus the 1991-2020 normal, in mm/day (weekly and monthly only)'
    : 'Precipitation as a share of the 1991-2020 normal (weekly and monthly only)'
}

function modeReady(mode: LandMode): boolean {
  return store.landLayer ? store.landModeReady(store.landLayer, mode) : false
}
</script>
