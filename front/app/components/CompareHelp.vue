<template>
  <!-- The Compare group's shortcuts, beside the buttons they shortcut. The
       Alt-clicks are otherwise only in a button's hover title and the guide, and
       a tooltip is invisible on a phone and easy to miss on a desktop. The text
       follows the mode: what Alt-click does on the chart depends on whether
       date compare is on, so the line for whichever is active comes first. -->
  <UPopover
    :content="{ align: 'end', side: 'top' }"
    :ui="{ content: 'w-80 max-w-[calc(100vw-2rem)] p-3 text-xs' }"
    @update:open="onOpen"
  >
    <UButton
      icon="i-mdi-help-circle-outline"
      color="neutral"
      variant="ghost"
      :size="size"
      aria-label="How to compare"
      title="How to compare"
    />
    <template #content>
      <p class="mb-2 font-semibold text-default">
        Compare
      </p>
      <ul class="space-y-2">
        <li v-for="item in items" :key="item.key" class="flex gap-2">
          <UIcon :name="item.icon" class="mt-0.5 size-4 shrink-0" :class="item.active ? 'text-primary' : 'text-muted'" />
          <span :class="item.active ? 'text-default' : 'text-muted'">
            <span class="font-medium text-default">{{ item.title }}</span>
            <template v-if="item.active">
              <span class="ml-1 rounded bg-primary/15 px-1 text-[10px] font-medium uppercase text-primary">on</span>
            </template>
            <br>{{ item.text }}
          </span>
        </li>
      </ul>
      <button type="button" class="mt-3 text-primary hover:underline" @click="guide.openOn('guide')">
        Full guide
      </button>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { useMainStore } from '~/stores/main'

defineProps<{ size: 'xs' | 'sm' }>()

const store = useMainStore()
const guide = useGuide()
const { narrow } = useViewport()

// Read on mount, not in setup: `navigator` does not exist under SSR, and a
// key name that differs between server and browser is a hydration mismatch.
const alt = ref('Alt')
onMounted(() => {
  if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) alt.value = '⌥ Option'
})

const items = computed(() => {
  const placeOn = store.hasSecond || store.addingPoint
  const dateOn = !!store.compareDate
  const place = {
    key: 'place',
    icon: 'i-mdi-map-marker-plus',
    title: 'A second place (B)',
    active: placeOn,
    text: narrow.value
      ? 'Place → Point on map, then tap the map; or pick a region. B is drawn beside A on the chart.'
      : `${alt.value}-click the map to drop point B, or use Place for a region. B is drawn beside A on the chart.`,
  }
  const date = {
    key: 'date',
    icon: 'i-mdi-compare-horizontal',
    title: 'A second date',
    active: dateOn,
    text: dateOn
      ? (narrow.value
          ? 'Drag the divider to swipe between the two dates; set the right-hand one with its own date field.'
          : `${alt.value}-click the chart to move the right-hand map to that date. Drag the divider to swipe between them.`)
      : (narrow.value
          ? 'Press Date to split the map: the same view on another date, side by side.'
          : `Press Date to split the map: the same view on another date, side by side. Then ${alt.value}-click the chart to set that date.`),
  }
  // Whichever is on leads; with both or neither, place first, matching the buttons.
  return dateOn && !placeOn ? [date, place] : [place, date]
})

function onOpen(open: boolean) {
  if (open) trackEvent('compare_help_opened', { place: store.hasSecond, date: !!store.compareDate })
}
</script>
