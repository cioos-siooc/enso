<template>
  <!-- A flip-book of pre-rendered monthly frames: play, pause and scrub.
       Frames are screenshots of OSTA, so this is not the app's own playback
       (`usePlayback`), which drives the live map. -->
  <div class="overflow-hidden rounded-xl border border-default bg-[#181818]">
    <div class="relative" :style="{ aspectRatio: `${width} / ${height}` }">
      <img :src="src(index)" :alt="`${alt}, ${label(index)}`" :width="width" :height="height" class="absolute inset-0 size-full object-cover">
      <span class="absolute left-3.5 top-3 font-display text-[clamp(1.2rem,3vw,1.7rem)] font-[750] text-white [font-stretch:var(--story-stretch,112%)] [text-shadow:0_1px_6px_rgb(0_0_0/0.6)]">
        {{ label(index) }}
      </span>
      <span v-if="notes?.[index]" class="absolute bottom-3 right-3.5 font-data text-xs text-white tabular-nums [text-shadow:0_1px_6px_rgb(0_0_0/0.7)] md:bottom-auto md:top-3.5">
        {{ notes[index] }}
      </span>
    </div>
    <div class="flex items-center gap-3 px-3.5 py-2.5 font-data text-xs text-neutral-300">
      <UButton
        :icon="playing ? 'i-mdi-pause' : 'i-mdi-play'"
        :aria-label="playing ? 'Pause' : 'Play'"
        size="xs"
        color="neutral"
        variant="outline"
        @click="playing ? stop() : play()"
      />
      <input
        v-model.number="index"
        type="range"
        min="0"
        :max="frames.length - 1"
        aria-label="Month"
        class="min-w-0 flex-1 accent-(--ui-primary)"
        @input="stop()"
      >
      <span class="tabular-nums">{{ index + 1 }} / {{ frames.length }}</span>
    </div>
    <div class="flex items-center gap-2 px-3.5 pb-3 font-data text-[0.7rem] text-neutral-400">
      <span>{{ legend[0] }}</span>
      <i class="h-2 flex-1 rounded-full" :style="{ background: RAMP }" />
      <span>{{ legend[1] }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  /** Frame dates, YYYY-MM-DD; each is `${base}/${date}.webp`. */
  frames: string[]
  base: string
  alt: string
  legend?: [string, string]
  width?: number
  height?: number
  /** Milliseconds per frame. */
  interval?: number
  /** A short line per frame, drawn in the frame's corner. */
  notes?: string[]
  /** Open on the last frame instead of the first. */
  startAtEnd?: boolean
}>(), { legend: () => ['−3 °C', '+3 °C'], width: 580, height: 504, interval: 450, notes: undefined, startAtEnd: false })

const RAMP = 'linear-gradient(90deg, #053061, #2166ac 10%, #4393c3 20%, #92c5de 30%, #d1e5f0 40%, #f7f7f7 50%, #fddbc7 60%, #f4a582 70%, #d6604d 80%, #b2182b 90%, #67001f)'

const index = ref(props.startAtEnd ? props.frames.length - 1 : 0)
const playing = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const src = (i: number) => `${props.base}/${props.frames[i]}.webp`

/** 'September 2013'. Locale and zone pinned: this renders under SSR too. */
function label(i: number) {
  return new Date(`${props.frames[i]}T00:00:00Z`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
}

function stop() {
  if (timer) clearInterval(timer)
  timer = null
  playing.value = false
}

function play() {
  if (index.value >= props.frames.length - 1) index.value = 0
  playing.value = true
  timer = setInterval(() => {
    if (index.value >= props.frames.length - 1) return stop()
    index.value += 1
  }, props.interval)
}

onMounted(() => {
  // Warm every frame so playback does not stall on the network.
  props.frames.forEach((_, i) => { new Image().src = src(i) })
  if (!props.startAtEnd && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) setTimeout(play, 800)
})
onBeforeUnmount(stop)
</script>
