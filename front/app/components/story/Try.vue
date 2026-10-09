<template>
  <!-- "Try it in OSTA": how to reach the chapter's view by hand, the features
       it uses, the chapter's numbers, and a link straight to the view. The
       only carded element in a chapter. -->
  <div class="mx-auto grid w-full max-w-280 gap-6 rounded-xl border border-default bg-elevated/50 p-5 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] md:p-7">
    <div class="flex min-w-0 flex-col gap-3">
      <span class="font-data text-xs uppercase tracking-wider text-primary">Try it in OSTA</span>
      <p class="text-base leading-relaxed">
        <slot />
      </p>
      <div class="flex flex-wrap gap-1.5">
        <UBadge v-for="chip in chips" :key="chip" color="neutral" variant="subtle" :label="chip" class="font-sans" />
      </div>
    </div>
    <div class="flex min-w-0 flex-col gap-4">
      <dl class="flex flex-col gap-3">
        <div v-for="fact in facts" :key="fact.term" class="grid grid-cols-[6.5rem_minmax(0,1fr)] items-baseline gap-3">
          <dt class="font-display text-lg font-bold text-highlighted [font-stretch:var(--story-stretch,112%)]">{{ fact.term }}</dt>
          <dd class="text-sm leading-snug text-muted">{{ fact.desc }}</dd>
        </div>
      </dl>
      <UButton :to="to" target="_blank" label="Open this view" trailing-icon="i-mdi-open-in-new" class="self-start font-sans" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  to: string
  chips: string[]
  facts: Array<{ term: string, desc: string }>
}>()
</script>
