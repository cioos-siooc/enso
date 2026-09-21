<template>
  <!-- The land overlay: WHAT is drawn on land, and HOW.

       Its own control rather than more buttons on the ocean toggle, because it
       is not a fourth ocean variable. It is drawn OVER whichever ocean variable
       is showing — so El Nino's ocean anomaly and its land response can be read
       on one map — and the chart, stats and rankings stay ocean. It sits in the
       map's top-left column with the projection and scope controls, because it
       changes what the map shows and nothing else.

       Value | Anomaly is the land layer's own choice, independent of the ocean
       toggle: SST anomaly over the sea can sit beside absolute rainfall on land.
       It is hidden while the overlay is off, since it would describe nothing. -->
  <div v-if="store.domain" class="flex flex-col items-start gap-1">
    <UFieldGroup :size="narrow ? 'sm' : 'xs'" class="rounded-lg shadow-lg">
      <UButton
        icon="i-mdi-terrain"
        :label="narrow ? undefined : 'Land'"
        aria-label="Land overlay off"
        :color="store.landLayer === null ? 'primary' : 'neutral'"
        :variant="store.landLayer === null ? 'solid' : 'subtle'"
        :title="available ? 'No land overlay' : unavailableTitle"
        @click="store.setLandLayer(null)"
      />
      <UButton
        v-for="item in SOURCES"
        :key="item.value"
        :label="item.label"
        :color="store.landLayer === item.value ? 'primary' : 'neutral'"
        :variant="store.landLayer === item.value ? 'solid' : 'subtle'"
        :disabled="!available"
        :title="available ? item.title : unavailableTitle"
        @click="store.setLandLayer(item.value)"
      />
    </UFieldGroup>

    <UFieldGroup v-if="store.landLayer" :size="narrow ? 'sm' : 'xs'" class="rounded-lg shadow-lg">
      <UButton
        v-for="mode in MODES"
        :key="mode.value"
        :label="modeLabel(mode.value)"
        :color="store.landMode === mode.value ? 'primary' : 'neutral'"
        :variant="store.landMode === mode.value ? 'solid' : 'subtle'"
        :disabled="!modeReady(mode.value)"
        :title="modeReady(mode.value) ? modeTitle(mode.value) : 'The 1991-2020 land climatology has not been built yet'"
        @click="store.setLandMode(mode.value)"
      />
    </UFieldGroup>
  </div>
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'
import type { LandMode, LandSource } from '~/utils/land'

const store = useMainStore()
const { narrow } = useViewport()

const SOURCES: Array<{ value: LandSource, label: string, title: string }> = [
  { value: 'tmax', label: 'Tmax', title: 'Daily maximum temperature on land (NOAA CPC)' },
  { value: 'tmin', label: 'Tmin', title: 'Daily minimum temperature on land (NOAA CPC)' },
  { value: 'precip', label: 'Rain', title: 'Rainfall on land (NOAA CPC)' },
]

const MODES: Array<{ value: LandMode }> = [{ value: 'value' }, { value: 'anomaly' }]

/** Whether this server has land data at all — `/coverage.land` is null if not. */
const available = computed(() => Boolean(store.coverage?.land))
const unavailableTitle = 'Land data is not loaded on this server'

/**
 * Rain's anomaly is a ratio, so the button says what the map will show: "% of
 * normal", not "Anomaly", which would promise a difference in millimetres.
 */
function modeLabel(mode: LandMode): string {
  if (mode === 'value') return 'Value'
  return store.landLayer === 'precip' ? '% of normal' : 'Anomaly'
}

function modeTitle(mode: LandMode): string {
  if (mode === 'value') return store.landLayer === 'precip' ? 'Rainfall in mm/day' : 'Temperature in °C'
  return store.landLayer === 'precip'
    ? 'Rainfall as a share of the 1991-2020 normal (weekly and monthly only)'
    : 'Difference from the 1991-2020 normal for the time of year'
}

function modeReady(mode: LandMode): boolean {
  return store.landLayer ? store.landModeReady(store.landLayer, mode) : false
}
</script>
