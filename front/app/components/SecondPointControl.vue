<template>
  <!-- Point scope only: B is a second cell on the point chart, and a region's
       chart has nothing to put it beside. Alt-click does the same on a desktop;
       this button is the path that works on a phone, and the one that says the
       feature exists at all. It sits in the time bar's Compare group beside
       swipe compare's Date: a second place and a second date are the two ways
       to compare. -->
  <UButton
    v-if="store.scope === 'point'"
    :size="size"
    :icon="store.secondPoint ? 'i-mdi-map-marker-remove' : 'i-mdi-map-marker-plus'"
    :label="narrow ? undefined : label"
    :aria-label="label"
    :color="store.addingPoint ? 'primary' : 'neutral'"
    :variant="store.addingPoint ? 'solid' : 'subtle'"
    :title="title"
    :aria-pressed="store.addingPoint"
    @click="onClick"
  />
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'

defineProps<{ size: 'xs' | 'sm' }>()

const store = useMainStore()
const { narrow } = useViewport()

const label = computed(() => {
  if (store.secondPoint) return 'Remove B'
  return store.addingPoint ? 'Click the map…' : 'Point'
})

const title = computed(() => (store.secondPoint
  ? 'Remove the second point from the chart'
  : 'Drop a second point to compare on the chart (or Alt-click the map)'))

function onClick() {
  if (store.secondPoint) store.removeSecondPoint()
  else store.setAddingPoint(!store.addingPoint)
}

// Esc disarms, the way it cancels any other half-finished gesture.
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && store.addingPoint) store.setAddingPoint(false)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
