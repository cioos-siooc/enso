<template>
  <!-- Dated news items, newest first: the outlet, the headline as a link, and
       what the article says in a sentence or two. -->
  <ul class="mx-auto w-full max-w-160 border-t border-default">
    <li
      v-for="item in items"
      :key="item.href"
      class="grid gap-x-4 gap-y-1 border-b border-default py-3.5 sm:grid-cols-[6.2rem_minmax(0,1fr)]"
    >
      <time :datetime="item.iso" class="pt-1 font-data text-[0.68rem] text-muted">{{ item.date }}</time>
      <div class="flex min-w-0 flex-col gap-1">
        <span class="font-data text-[0.66rem] uppercase tracking-wider text-muted">{{ item.source }}</span>
        <a :href="item.href" target="_blank" rel="noopener" class="font-display text-[1.02rem] font-bold leading-snug text-highlighted [font-stretch:100%] hover:text-primary hover:underline">
          {{ item.title }}
        </a>
        <p class="text-[0.95rem] leading-relaxed">{{ item.text }}</p>
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
export interface WireItem {
  /** As printed, '8 Oct 2026'. */
  date: string
  /** For `<time datetime>`, '2026-10-08'. */
  iso: string
  source: string
  title: string
  href: string
  text: string
}

defineProps<{ items: WireItem[] }>()
</script>
