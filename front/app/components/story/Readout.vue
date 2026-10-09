<template>
  <!-- The chapter's one number, drawn on a small gauge. An anomaly sits as a
       tick on the anomaly ramp (the map's own RdBu_r), clamped at the ends
       like the map; an extent fills a bar from zero to 100%. -->
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 font-data text-sm text-muted">
    <span
      class="relative h-2.5 w-40 shrink-0 rounded-full"
      :class="kind === 'extent' ? 'bg-accented' : ''"
      :style="kind === 'anom' ? { background: RAMP } : undefined"
      aria-hidden="true"
    >
      <i
        v-if="kind === 'anom'"
        class="absolute -top-1 h-4.5 w-0.75 -translate-x-1/2 rounded-sm bg-white shadow"
        :style="{ left: `${position}%` }"
      />
      <i v-else class="absolute inset-y-0 left-0 rounded-full bg-[#ffb333]" :style="{ width: `${position}%` }" />
    </span>
    <span><slot /></span>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  kind: 'anom' | 'extent'
  value: number
  /** The anomaly scale's half-width, in °C; the ocean's default is 3. */
  range?: number
}>(), { range: 3 })

/** RdBu_r, as the map draws the anomaly. */
const RAMP = 'linear-gradient(90deg, #053061, #2166ac 10%, #4393c3 20%, #92c5de 30%, #d1e5f0 40%, #f7f7f7 50%, #fddbc7 60%, #f4a582 70%, #d6604d 80%, #b2182b 90%, #67001f)'

const position = computed(() => {
  const p = props.kind === 'anom'
    ? (props.value + props.range) / (2 * props.range) * 100
    : props.value
  return Math.min(100, Math.max(0, p))
})
</script>
