<template>
  <!-- A card, not a modal: the map is what a first visit learns from, and a
       modal would cover it. Three gestures and no more — the full guide is one
       click away and is where everything else is explained. Centred on the map,
       so it reads as the first thing to look at rather than as another control. -->
  <div
    v-if="intro.shown.value"
    class="absolute left-1/2 top-1/2 z-20 w-[calc(100%-1rem)] -translate-x-1/2 -translate-y-1/2 rounded-lg md:w-80 border border-default bg-elevated/95 p-2.5 text-xs shadow-lg md:p-3 md:text-sm"
    role="dialog"
    aria-label="Getting started"
  >
    <div class="mb-1.5 flex items-start md:mb-2 justify-between gap-2">
      <p class="font-semibold text-highlighted">Getting started</p>
      <UButton
        icon="i-mdi-close"
        variant="ghost"
        color="neutral"
        size="xs"
        aria-label="Dismiss"
        class="-mr-1 -mt-1"
        @click="close('dismiss')"
      />
    </div>
    <ul class="space-y-1.5 text-muted md:space-y-2">
      <li v-for="tip in tips" :key="tip.icon" class="flex gap-2">
        <UIcon :name="tip.icon" class="mt-0.5 size-4 shrink-0 text-primary" />
        <span>{{ tip.text }}</span>
      </li>
    </ul>
    <div class="mt-2 flex justify-end gap-1 md:mt-3">
      <UButton variant="ghost" color="neutral" size="xs" label="Full guide" @click="close('guide')" />
      <UButton size="xs" label="Got it" @click="close('dismiss')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'

const intro = useIntro()
const guide = useGuide()

const tips = [
  { icon: 'i-mdi-cursor-default-click', text: 'Click the map to chart that cell\'s whole record since 1985.' },
  { icon: 'i-mdi-chart-line', text: 'Click the chart to move the map to that date.' },
  { icon: 'i-mdi-vector-rectangle', text: 'Pick a region from the menu at top left for an area mean, such as Niño 3.4.' },
]

// Read at setup, before `useUrlState` rewrites the address bar with the
// defaults: a visitor arriving on a shared link came to see that view, and a
// card over it would be in the way of the thing they were sent.
const arrivedOnLink = Object.keys(useRoute().query).length > 0

onMounted(() => {
  if (!arrivedOnLink) intro.restore()
})

function close(action: 'dismiss' | 'guide') {
  intro.dismiss()
  trackEvent('intro_closed', { action })
  if (action === 'guide') guide.openOn('guide')
}
</script>
