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
      {{ formatCell(store.pointSeries?.cell ?? store.selectedPoint) }}
    </span>
    <span class="flex items-center gap-1.5 text-default">
      <span class="size-2.5 rounded-full" :style="{ background: PIN_COLORS.b }" />
      <span class="font-semibold">B</span>
      <UIcon v-if="store.loadingSecond" name="i-mdi-loading" class="size-3.5 animate-spin text-muted" />
      <span v-if="store.secondError" class="text-error">{{ store.secondError }}</span>
      <span v-else>{{ formatCell(store.secondSeries?.cell ?? store.secondPoint) }}</span>
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
</script>
