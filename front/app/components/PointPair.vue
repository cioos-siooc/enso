<template>
  <!-- The chart's legend in two-point mode, and B's remove button. A row of the
       chart pane rather than ECharts' own legend, because it also has to say
       when B is still loading or could not be read, and carry the one control
       that removes it — the path a phone reaches first. -->
  <div
    v-if="store.activeSecondPoint"
    class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 px-1 pt-1 text-xs"
  >
    <span class="flex items-center gap-1.5 text-default">
      <span class="size-2.5 rounded-full" :style="{ background: PIN_COLORS.a }" />
      <span class="font-semibold">A</span>
      {{ formatCell(store.activeLandSeries?.cell ?? store.pointSeries?.cell ?? store.selectedPoint) }}
      <span v-if="store.activeLandSeries" class="text-muted">· land</span>
    </span>
    <span class="flex items-center gap-1.5 text-default">
      <span class="size-2.5 rounded-full" :style="{ background: PIN_COLORS.b }" />
      <span class="font-semibold">B</span>
      <UIcon v-if="loadingB" name="i-mdi-loading" class="size-3.5 animate-spin text-muted" />
      <span v-if="store.secondError" class="text-error">{{ store.secondError }}</span>
      <template v-else>
        <span>{{ formatCell(store.activeSecondLandSeries?.cell ?? store.secondSeries?.cell ?? store.secondPoint) }}</span>
        <span v-if="store.activeSecondLandSeries" class="text-muted">· land</span>
        <span v-if="emptyB" class="text-muted">· {{ emptyB }}</span>
      </template>
      <UButton
        icon="i-mdi-close"
        size="xs"
        color="neutral"
        variant="ghost"
        aria-label="Remove point B"
        title="Remove point B"
        @click="store.removeSecondPoint()"
      />
    </span>
  </div>
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'
import { PIN_COLORS, formatCell } from '~/utils/points'

const store = useMainStore()

const loadingB = computed(() => store.loadingSecond || store.landPins.b.loading)

/**
 * Why B draws no line, once nothing is loading. A land cell answers the ocean
 * request with an empty series, which would otherwise name a place with no
 * line and say nothing.
 */
const emptyB = computed(() => {
  if (loadingB.value || store.secondSeries?.dates.length || store.activeSecondLandSeries) return null
  if (!store.landLayer) return 'no ocean record; turn on a land layer to chart land'
  return store.landChartReason ?? store.landPins.b.error ?? 'no record here'
})
</script>
