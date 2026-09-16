<template>
  <!-- Absent, not disabled, when there is nothing to tell: a production build
       with no finished stories shows no button at all. -->
  <template v-if="stories.length">
    <UButton
      icon="i-mdi-book-open-page-variant-outline"
      variant="ghost"
      color="neutral"
      size="xs"
      aria-label="Guided stories"
      title="Guided stories"
      @click="open = true"
    >
      <span class="hidden sm:inline">Stories</span>
    </UButton>

    <UModal v-model:open="open" title="Stories" description="Guided walks through events in the record." :fullscreen="narrow">
      <template #body>
        <ul class="space-y-2">
          <li v-for="item in stories" :key="item.key">
            <button
              type="button"
              class="w-full cursor-pointer rounded-lg border border-default bg-elevated/40 px-4 py-3 text-left transition-colors hover:border-primary"
              @click="begin(item.key)"
            >
              <span class="flex items-center gap-2">
                <span class="text-sm font-semibold text-highlighted">{{ item.title }}</span>
                <UBadge v-if="item.draft" size="sm" variant="subtle" color="warning">draft</UBadge>
                <span class="ml-auto shrink-0 text-xs text-dimmed">{{ item.steps.length }} steps</span>
              </span>
              <span class="mt-1 block text-sm text-muted">{{ item.summary }}</span>
            </button>
          </li>
        </ul>
      </template>
    </UModal>
  </template>
</template>

<script setup lang="ts">
import { useStory } from '~/composables/useStory'
import { visibleStories } from '~/stories'

const stories = visibleStories()
const story = useStory()
const { narrow } = useViewport()
const open = ref(false)

function begin(key: string) {
  open.value = false
  void story.start(key)
}
</script>
