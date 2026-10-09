<template>
  <blockquote class="flex flex-col gap-2 border-l-3 border-red-400 pl-5">
    <p class="text-xl leading-snug italic text-highlighted">
      <slot />
    </p>
    <footer class="font-data text-xs leading-relaxed text-muted">{{ cite }}</footer>
  </blockquote>
</template>

<script setup lang="ts">
defineProps<{ cite: string }>()
</script>
