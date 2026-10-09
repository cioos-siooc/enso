<template>
  <!-- One past event in a gallery: its screenshot, where and when, the
       numbers OSTA gives for it, and a link to its warmest month. -->
  <article class="flex min-w-0 flex-col gap-2.5">
    <NuxtLink :to="to" target="_blank" class="block overflow-hidden rounded-lg border border-default bg-[#181818] transition-colors hover:border-primary">
      <img :src="src" :alt="alt" width="920" height="504" loading="lazy" class="block h-auto w-full">
    </NuxtLink>
    <span class="font-data text-xs text-muted">{{ meta }}</span>
    <h3 class="font-display text-lg font-bold leading-tight text-highlighted">{{ title }}</h3>
    <div class="flex flex-wrap gap-1.5">
      <UBadge v-for="stat in stats" :key="stat" color="neutral" variant="subtle" :label="stat" class="font-data" />
    </div>
    <p class="text-base leading-relaxed">{{ text }}</p>
    <NuxtLink :to="to" target="_blank" class="font-data text-xs text-primary hover:underline">Open in OSTA ↗</NuxtLink>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  to: string
  src: string
  alt: string
  meta: string
  title: string
  stats: string[]
  text: string
}>()
</script>
