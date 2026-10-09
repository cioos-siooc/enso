<template>
  <!-- Several events' monthly index on one calendar: each line runs 24 months
       from January of its first year, so the lines can be compared month for
       month. Drawn as SVG in the template, so it renders on the server. -->
  <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="label" class="block h-auto w-full">
    <g class="font-data" font-size="12">
      <template v-for="v in ticks" :key="`t${v}`">
        <line :x1="L" :x2="W - R" :y1="y(v)" :y2="y(v)" class="stroke-(--ui-border)" :stroke-width="v === 0 ? 1.4 : 1" />
        <text :x="L - 8" :y="y(v) + 4" text-anchor="end" class="fill-(--ui-text-muted)">{{ v === 0 ? '0' : signed(v, 0) }}</text>
      </template>
      <template v-for="t in thresholds" :key="t.label">
        <line :x1="L" :x2="W - R" :y1="y(t.value)" :y2="y(t.value)" stroke-dasharray="4 5" class="stroke-(--ui-text-muted)" />
        <text :x="W - R + 6" :y="y(t.value) + 4" font-size="11" class="fill-(--ui-text-muted)">{{ t.label }}</text>
      </template>
      <text v-for="i in 24" :key="`m${i}`" :x="x(i - 1)" :y="H - B + 18" text-anchor="middle" font-size="11" class="fill-(--ui-text-muted)">
        {{ MONTHS[(i - 1) % 12] }}
      </text>
      <text :x="x(0)" :y="H - 4" font-size="11" class="fill-(--ui-text-muted)">first year</text>
      <text :x="x(12)" :y="H - 4" font-size="11" class="fill-(--ui-text-muted)">second year</text>
      <line :x1="x(11.5)" :x2="x(11.5)" :y1="T" :y2="H - B" class="stroke-(--ui-border)" />

      <g v-for="line in lines" :key="line.label">
        <polyline :points="line.points" fill="none" :stroke="line.color" :stroke-width="line.live ? 3.5 : 2" stroke-linejoin="round" stroke-linecap="round" />
        <circle :cx="line.dot[0]" :cy="line.dot[1]" :r="line.live ? 5 : 3.5" :fill="line.color" />
        <text v-if="line.live" :x="line.dot[0] - 8" :y="line.dot[1] - 10" text-anchor="end" font-size="12.5" font-weight="600" :fill="line.color">
          {{ line.label }} {{ signed(line.dotValue) }}
        </text>
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
export interface RaceSeries {
  label: string
  /** 24 monthly values from January of the first year; null where not yet measured. */
  values: Array<number | null>
}

const props = withDefaults(defineProps<{
  series: RaceSeries[]
  /** One colour per series, in order. The last series with any nulls is the live one. */
  colors: string[]
  label: string
  domain?: [number, number]
  thresholds?: Array<{ value: number, label: string }>
}>(), { domain: () => [-2.5, 3.5], thresholds: () => [] })

const W = 960
const H = 380
const L = 48
const R = 116
const T = 16
const B = 40
const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

const x = (i: number) => L + i * (W - L - R) / 23
const y = (v: number) => T + (props.domain[1] - v) * (H - T - B) / (props.domain[1] - props.domain[0])

const ticks = computed(() => {
  const out: number[] = []
  for (let v = Math.ceil(props.domain[0]); v <= Math.floor(props.domain[1]); v++) out.push(v)
  return out
})

const lines = computed(() => props.series.map((s, n) => {
  const live = s.values.some(v => v == null)
  const pts = s.values.flatMap((v, i) => v == null ? [] : [[x(i), y(v)] as const])
  // The live line is marked at its newest month, a finished one at its peak.
  let k = -1
  s.values.forEach((v, i) => {
    if (v == null) return
    if (live || k < 0 || v > s.values[k]!) k = i
  })
  return {
    label: s.label,
    live,
    color: props.colors[n] ?? 'currentColor',
    points: pts.map(p => p.join(',')).join(' '),
    dot: [x(k), y(s.values[k]!)] as const,
    dotValue: s.values[k]!,
  }
}))
</script>
