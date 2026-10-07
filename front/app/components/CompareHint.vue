<template>
  <!-- A one-line hint beside a compare button, on hover. The shortcut it names
       (Alt-click) has no control of its own, so a `title` on the button was the
       only place it was said, and nothing on screen invited hovering there. -->
  <UTooltip :text="text" :content="{ side: 'bottom' }" :delay-duration="0">
    <UButton
      icon="i-mdi-help-circle"
      color="neutral"
      :variant="variant ?? 'ghost'"
      :size="size"
      :aria-label="text"
    />
  </UTooltip>
</template>

<script setup lang="ts">
defineProps<{
  text: string
  size: 'xs' | 'sm'
  variant?: 'ghost' | 'subtle'
}>()
</script>
