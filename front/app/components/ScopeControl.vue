<template>
  <!-- The one mode switch in the app, and it lives on the map because that is
       what it changes: Point reads the cell you clicked, the other half reads a
       named box drawn on the same canvas. It sits under the projection pair so
       every control that reframes what the map is showing is in one column.

       The region half is a MENU, not a second toggle. There are twenty regions
       and only one is ever drawn, so a plain toggle needed a picker on a row of
       its own underneath it — two controls for one decision. As a dropdown the
       button states the region currently being read and opening it is how you
       change it, which is the same gesture either way. -->
  <UFieldGroup :size="narrow ? 'sm' : 'xs'" class="rounded-lg shadow-lg">
    <UButton
      icon="i-mdi-map-marker"
      label="Point"
      :color="store.scope === 'point' ? 'primary' : 'neutral'"
      :variant="store.scope === 'point' ? 'solid' : 'subtle'"
      :title="store.selectedPoint ? 'The clicked cell' : 'Click the map to pick a cell'"
      @click="store.setScope('point')"
    />
    <UDropdownMenu :items="items" :content="{ align: 'start' }" :ui="{ label: 'text-[#d4af37]' }">
      <UButton
        icon="i-mdi-vector-rectangle"
        trailing-icon="i-mdi-chevron-down"
        :label="store.activeRegionMeta?.label ?? 'Region'"
        :color="store.scope === 'region' ? 'primary' : 'neutral'"
        :variant="store.scope === 'region' ? 'solid' : 'subtle'"
        title="Area mean over a named region — pick one"
      />
    </UDropdownMenu>
    <!-- What the region is and why it is on the menu, beside the name it
         explains. Region scope only: a cell needs no defending. -->
    <UPopover
      v-if="store.scope === 'region' && store.activeRegionMeta"
      :content="{ align: 'start', side: 'bottom' }"
      :ui="{ content: 'w-96 max-w-[calc(100vw-2rem)]' }"
      @update:open="(o: boolean) => o && trackEvent('region_about_opened', { region: store.activeRegion })"
    >
      <UButton
        icon="i-mdi-information-outline"
        color="primary"
        variant="solid"
        :aria-label="`About ${store.activeRegionMeta.label}`"
        title="Why this region, how it is defined, and references"
      />
      <template #content>
        <RegionNote :region-key="store.activeRegionMeta.key" :region-label="store.activeRegionMeta.label" />
      </template>
    </UPopover>
  </UFieldGroup>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { useMainStore } from '~/stores/main'

const store = useMainStore()
const { narrow } = useViewport()

/**
 * Picking a region IS switching to region scope — `store.selectRegion()` sets
 * both, so there is no state where the menu names a box the panel is not
 * reading. The active one is marked by weight and ink rather than a tick column,
 * which keeps every row on the same left edge.
 */
const items = computed(() => {
  const regions = store.domain?.regions ?? []
  const item = (r: typeof regions[number]) => ({
    label: r.label,
    class: store.scope === 'region' && r.key === store.activeRegion
      ? 'font-semibold text-primary'
      : undefined,
    onSelect: () => { store.selectRegion(r.key) },
  })
  // One section per declared group, in `domain.yml` order, each under its own
  // heading — twenty-odd regions in one flat list is a scroll, not a menu. A
  // region with no (or an unknown) group still appears, in a last section.
  const groups = store.domain?.regionGroups ?? []
  const known = new Set(groups.map(g => g.key))
  const sections = groups
    .map(g => [
      { type: 'label' as const, label: g.label },
      ...regions.filter(r => r.group === g.key).map(item),
    ])
    .filter(s => s.length > 1)
  const rest = regions.filter(r => !r.group || !known.has(r.group)).map(item)
  return rest.length ? [...sections, rest] : sections
})
</script>
