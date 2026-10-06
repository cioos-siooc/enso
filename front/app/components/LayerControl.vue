<template>
  <!-- WHAT the map draws, in one card: the ocean field and the land overlay.

       They used to sit in two places — the ocean toggle in the time bar, the
       land one here — which read as two unrelated kinds of control. Both are
       layers of the same map (land is drawn OVER whichever ocean field is
       showing), so they are two rows of one panel. The time bar is left
       holding only "when".

       On a phone the card sits behind one button naming the active pair, so the
       map column grows by one row rather than three. -->
  <UPopover v-if="narrow" :content="{ align: 'start', side: 'bottom' }">
    <UButton
      icon="i-mdi-layers-outline"
      trailing-icon="i-mdi-chevron-down"
      :label="summary"
      size="sm"
      color="neutral"
      variant="subtle"
      class="rounded-lg shadow-lg"
      title="Choose what the map draws"
    />
    <template #content>
      <div class="p-2">
        <LayerRows :size="size" />
      </div>
    </template>
  </UPopover>

  <div
    v-else
    class="rounded-lg border border-default bg-elevated/90 p-1.5 shadow-lg backdrop-blur"
  >
    <LayerRows :size="size" />
  </div>
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'
import { LAND_SOURCES, OCEAN_VARIABLES } from '~/components/LayerRows.vue'

const store = useMainStore()
const { narrow } = useViewport()
const size = computed(() => (narrow.value ? 'sm' : 'xs'))

/** The phone button's label: what is on screen, e.g. "Anomaly · Tmax". */
const summary = computed(() => {
  const ocean = OCEAN_VARIABLES.find(v => v.value === store.variable)?.label ?? 'Layers'
  const land = LAND_SOURCES.find(s => s.value === store.landLayer)?.label
  return land ? `${ocean} · ${land}` : ocean
})
</script>
