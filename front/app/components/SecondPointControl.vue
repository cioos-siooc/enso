<template>
  <!-- The second selection, B: a cell or a named region, drawn beside A on the
       chart whichever A is. A menu rather than a button because B can be either
       kind: "Point on map" arms the next click (Alt-click does the same on a
       desktop), and the regions are the scope menu's own grouped list. With B
       set the button removes it. It sits beside `ScopeControl` on the map: B is a
       second "where", so it lives next to the control that picks A. -->
  <UButton
    v-if="store.hasSecond || store.addingPoint"
    :size="size"
    :icon="store.hasSecond ? 'i-mdi-map-marker-remove' : 'i-mdi-map-marker-plus'"
    :label="narrow ? undefined : label"
    :aria-label="label"
    :color="store.addingPoint ? 'primary' : 'neutral'"
    :variant="store.addingPoint ? 'solid' : 'subtle'"
    :title="title"
    :style="store.hasSecond ? removeStyle : undefined"
    :aria-pressed="store.addingPoint"
    @click="onClick"
  />
  <UDropdownMenu v-else :items="items" :content="{ align: 'start' }">
    <UButton
      :size="size"
      icon="i-mdi-map-marker-plus"
      :trailing-icon="narrow ? undefined : 'i-mdi-chevron-down'"
      :label="narrow ? undefined : 'Compare'"
      aria-label="Compare with another place"
      color="neutral"
      variant="subtle"
      :title="`Compare with a second point or region, drawn beside A on the chart. Or ${alt}-click the map to drop point B.`"
    />
  </UDropdownMenu>
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'
import { PIN_COLORS } from '~/utils/points'

defineProps<{ size: 'xs' | 'sm' }>()

const store = useMainStore()
const { narrow } = useViewport()
const alt = useAltKey()

const label = computed(() => {
  if (store.hasSecond) return 'Remove B'
  return 'Click the map…'
})

const title = computed(() => (store.hasSecond
  ? 'Remove the second selection from the chart'
  : 'Click the map to drop point B (Esc cancels)'))

// B's own violet, so the button reads as belonging to the pin and outline it
// removes. Inline, because the colour is PIN_COLORS', not a theme colour.
const removeStyle = {
  'color': PIN_COLORS.b,
  'backgroundColor': `${PIN_COLORS.b}1f`,
  '--tw-ring-color': `${PIN_COLORS.b}80`,
}

function onClick() {
  if (store.hasSecond) store.removeSecondPoint()
  else store.setAddingPoint(false)
}

/**
 * "Point on map", then every region under the scope menu's headings. A's own
 * region is left out: comparing a region with itself draws one line twice.
 */
const items = computed(() => {
  const regions = (store.domain?.regions ?? [])
    .filter(r => !(store.scope === 'region' && r.key === store.activeRegion))
  const item = (r: typeof regions[number]) => ({
    label: r.label,
    onSelect: () => { void store.selectSecondRegion(r.key) },
  })
  const groups = store.domain?.regionGroups ?? []
  const known = new Set(groups.map(g => g.key))
  const sections = groups
    .map(g => [
      { type: 'label' as const, label: g.label },
      ...regions.filter(r => r.group === g.key).map(item),
    ])
    .filter(s => s.length > 1)
  const rest = regions.filter(r => !r.group || !known.has(r.group)).map(item)
  return [
    [{ label: 'Point on map', icon: 'i-mdi-map-marker', onSelect: () => store.setAddingPoint(true) }],
    ...sections,
    ...(rest.length ? [rest] : []),
  ]
})

// Esc disarms, the way it cancels any other half-finished gesture.
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && store.addingPoint) store.setAddingPoint(false)
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
