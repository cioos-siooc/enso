<template>
  <!-- The ribbon's index beside NOAA's RONI, season by season. Inline SVG rather
       than ECharts: two short lines in a popover, and it renders on the server. -->
  <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="label" class="block h-auto w-full">
    <g font-size="10" class="tabular-nums">
      <template v-for="v in ticks" :key="`t${v}`">
        <line :x1="L" :x2="W - R" :y1="y(v)" :y2="y(v)" class="stroke-(--ui-border)" />
        <text :x="L - 5" :y="y(v) + 3.5" text-anchor="end" class="fill-(--ui-text-muted)">{{ v === 0 ? '0' : signed(v, 0) }}</text>
      </template>
      <line
        v-if="threshold > domain[0] && threshold < domain[1]"
        :x1="L" :x2="W - R" :y1="y(threshold)" :y2="y(threshold)"
        stroke-dasharray="3 3" class="stroke-(--ui-text-muted)"
      />
      <text
        v-for="t in years" :key="t.year"
        :x="x(t.i)" :y="H - 4" text-anchor="middle" class="fill-(--ui-text-muted)"
      >{{ t.year }}</text>

      <g v-for="line in lines" :key="line.key">
        <polyline :points="line.points" fill="none" :stroke="line.color" stroke-width="2" stroke-linejoin="round" />
        <circle :cx="line.end[0]" :cy="line.end[1]" r="3" :fill="line.color" />
        <text :x="line.end[0] + 6" :y="line.end[1] + 3.5" font-weight="600" :fill="line.color">{{ signed(line.value, 2) }}</text>
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
import type { EnsoSeason } from '~/stores/main'

const props = defineProps<{
  history: EnsoSeason[]
  threshold: number
  colors: { osta: string, noaa: string }
}>()

const W = 340
const H = 150
const L = 26
const R = 40
const T = 8
const B = 18

function signed(v: number, digits: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}`
}

const domain = computed<[number, number]>(() => {
  const vals = props.history.flatMap(h => [h.osta, h.noaa]).filter((v): v is number => v != null)
  return [Math.floor(Math.min(0, ...vals)), Math.ceil(Math.max(props.threshold, ...vals))]
})

const x = (i: number) => L + i * (W - L - R) / Math.max(1, props.history.length - 1)
const y = (v: number) => T + (domain.value[1] - v) * (H - T - B) / (domain.value[1] - domain.value[0])

const ticks = computed(() => {
  const out: number[] = []
  for (let v = domain.value[0]; v <= domain.value[1]; v++) out.push(v)
  return out
})

/** A label under each January season. */
const years = computed(() => props.history.flatMap((h, i) =>
  h.middle.slice(5, 7) === '01' ? [{ i, year: h.middle.slice(0, 4) }] : []))

const lines = computed(() => (['osta', 'noaa'] as const).flatMap((key) => {
  const pts = props.history.flatMap((h, i) => h[key] == null ? [] : [[x(i), y(h[key]!), h[key]!] as const])
  const last = pts.at(-1)
  if (!last) return []
  return [{
    key,
    color: props.colors[key],
    points: pts.map(p => `${p[0]},${p[1]}`).join(' '),
    end: [last[0], last[1]] as const,
    value: last[2],
  }]
}))

const label = computed(() => {
  const h = props.history.at(-1)
  return h ? `Three-month Niño 3.4 index, OSTA's against NOAA's RONI, to ${h.season}` : ''
})
</script>
