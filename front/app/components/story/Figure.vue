<template>
  <!-- A screenshot of OSTA that opens the same view, in a new tab so the
       reader keeps their place in the story. -->
  <figure class="mx-auto flex w-full flex-col gap-2.5" :class="narrow ? 'max-w-160' : 'max-w-280'">
    <NuxtLink
      :to="to"
      target="_blank"
      class="block overflow-hidden rounded-lg border border-default bg-[#181818] transition-colors hover:border-primary"
    >
      <img :src="src" :alt="alt" :width="width" :height="height" loading="lazy" class="block h-auto w-full">
    </NuxtLink>
    <figcaption v-if="$slots.default" class="max-w-200 font-data text-xs leading-relaxed text-muted">
      <slot />
    </figcaption>
  </figure>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  src: string
  alt: string
  to: string
  width?: number
  height?: number
  narrow?: boolean
}>(), { width: 1440, height: 900, narrow: false })
</script>
