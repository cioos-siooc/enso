<template>
  <!-- One chapter of a story: a dated eyebrow, the heading, an optional
       readout, then whatever the chapter holds. `scroll-mt` keeps an anchor
       jump from landing the heading under the top edge. -->
  <section :id="id" class="flex scroll-mt-6 flex-col gap-8 pt-20">
    <div class="mx-auto flex w-full max-w-160 flex-col gap-3">
      <span class="font-data text-xs uppercase tracking-wider" :class="accent ? 'text-orange-400' : 'text-muted'">{{ eyebrow }}</span>
      <h2 class="font-display text-[clamp(1.8rem,3.6vw,2.6rem)] font-[750] leading-[1.05] text-balance text-highlighted [font-stretch:var(--story-stretch,112%)]">
        {{ title }}
      </h2>
      <slot name="readout" />
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  id: string
  eyebrow: string
  title: string
  /** Colour the eyebrow with the story's accent rather than muted grey. */
  accent?: boolean
}>()
</script>
