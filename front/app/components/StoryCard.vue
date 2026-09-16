<template>
  <section
    v-if="current"
    class="rounded-lg border border-default bg-elevated/95 shadow-lg backdrop-blur"
    :class="compact ? 'px-3 py-2' : 'w-80 px-4 py-3'"
    aria-live="polite"
  >
    <header class="flex items-start gap-2">
      <div class="min-w-0 grow">
        <p class="truncate text-xs text-muted">{{ story.active.value?.title }}</p>
        <p class="text-[11px] tabular-nums text-dimmed">Step {{ story.step.value + 1 }} of {{ total }}</p>
      </div>
      <UButton
        icon="i-mdi-close"
        size="xs"
        color="neutral"
        variant="ghost"
        aria-label="Exit story"
        title="Exit story"
        @click="story.exit()"
      />
    </header>

    <!-- On a phone the card replaces the sheet's peek bar, so its caption is
         capped and scrolls rather than pushing the map off screen. -->
    <div class="mt-1.5 space-y-2 text-sm text-default" :class="compact ? 'max-h-24 overflow-y-auto' : ''">
      <p v-for="(paragraph, i) in paragraphs" :key="i">{{ paragraph }}</p>
    </div>

    <footer class="mt-2 flex items-center gap-2">
      <UButton
        icon="i-mdi-chevron-left"
        size="xs"
        color="neutral"
        variant="subtle"
        aria-label="Previous step"
        :disabled="story.step.value === 0"
        @click="story.back()"
      />
      <div class="flex grow justify-center gap-1" aria-hidden="true">
        <span
          v-for="i in total"
          :key="i"
          class="size-1.5 rounded-full"
          :class="i - 1 === story.step.value ? 'bg-primary' : 'bg-accented'"
        />
      </div>
      <UButton
        v-if="story.step.value < total - 1"
        trailing-icon="i-mdi-chevron-right"
        label="Next"
        size="xs"
        @click="story.next()"
      />
      <UButton v-else label="Finish" size="xs" @click="story.exit()" />
    </footer>
  </section>
</template>

<script setup lang="ts">
import { useStory } from '~/composables/useStory'

defineProps<{ compact?: boolean }>()

const story = useStory()

const current = computed(() => story.active.value?.steps[story.step.value] ?? null)
const total = computed(() => story.active.value?.steps.length ?? 0)
const paragraphs = computed(() => current.value?.caption.split(/\n\s*\n/) ?? [])
</script>
