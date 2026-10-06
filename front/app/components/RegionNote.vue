<!--
  Why the active region is on the menu, how its edges are drawn, and what to
  cite for both.

  A region is a claim twice over: that the area is worth an area mean, and that
  its boundary is the one its label names. Neither is self-evident (Niño 3.4 is a
  convention, the NE Pacific box is this project's own, the Coral Triangle is
  MEOW's provinces and not the Coral Triangle Initiative's line), so each region
  declares `about` in `domain.yml`, and `shared/domain.py` refuses to load one
  without it.

  The body of the popover behind the info button beside the region menu
  (`ScopeControl.vue`), which mounts it only while open. Fetched from
  `/region/{key}/about` on first open, like the polygon outlines: ~20 KB of prose
  across 22 regions would nearly double `/domain` for text most visitors never
  open.
-->
<template>
  <div class="max-h-[70dvh] space-y-2.5 overflow-y-auto p-3 text-xs text-muted">
    <p class="text-sm font-semibold text-highlighted">{{ regionLabel }}</p>
    <UIcon v-if="!about && !failed" name="i-mdi-loading" class="size-4 animate-spin" />
    <p v-else-if="failed" class="text-error">Could not load this region's description.</p>

    <template v-else-if="about">
      <div>
        <p class="font-medium text-highlighted">Why it matters</p>
        <p class="mt-0.5 leading-snug">{{ about.why }}</p>
      </div>
      <div>
        <p class="font-medium text-highlighted">How it is defined</p>
        <p class="mt-0.5 leading-snug">{{ about.definition }}</p>
        <!-- A box's bounds are its whole definition and are printed in its
             text; a polygon's are not, so its geometry source is named here. -->
        <p v-if="about.outline" class="mt-1 leading-snug text-dimmed">
          Outline:
          <ULink v-if="about.outline.url" :to="about.outline.url" target="_blank" class="text-primary">
            {{ about.outline.source }}</ULink>
          <span v-else>{{ about.outline.source }}</span><span
            v-if="about.outline.retrieved"
          >, retrieved {{ about.outline.retrieved }}</span>.
        </p>
      </div>
      <div>
        <p class="font-medium text-highlighted">References</p>
        <ul class="mt-0.5 space-y-1 leading-snug">
          <li v-for="r in about.references" :key="r.url">
            {{ r.authors }}<template v-if="r.year"> ({{ r.year }})</template>.
            <ULink :to="r.url" target="_blank" class="text-primary">{{ r.title }}</ULink>.
            <span class="text-dimmed">{{ r.source }}.</span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script lang="ts">
export interface RegionAbout {
  key: string
  label: string
  why: string
  definition: string
  references: Array<{ authors: string, year: number | null, title: string, source: string, url: string }>
  outline: { source: string, url: string | null, retrieved: string | null } | null
}

/**
 * Module-level, like the outlines, so each region's text is fetched once a
 * session. It has to live out here: the popover mounts this component afresh on
 * every open, and a cache inside `<script setup>` would go with each instance.
 */
const cache = new Map<string, RegionAbout>()
</script>

<script setup lang="ts">
const props = defineProps<{ regionKey: string, regionLabel: string }>()
const api = useApi()

const about = ref<RegionAbout | null>(null)
const failed = ref(false)

async function load(key: string) {
  failed.value = false
  const hit = cache.get(key)
  if (hit) {
    about.value = hit
    return
  }
  about.value = null
  try {
    const data = await api.get<RegionAbout>(`/region/${key}/about`)
    cache.set(key, data)
    // The selection may have moved on while this was in flight.
    if (props.regionKey === key) about.value = data
  }
  catch {
    if (props.regionKey === key) failed.value = true
  }
}

// Left open across a region change, it follows, so it always describes the box drawn.
watch(() => props.regionKey, key => void load(key), { immediate: true })
</script>
