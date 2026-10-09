<template>
  <!-- "Open in OSTA" with several views: each a link into the app (new tab)
       and a line on what to do there, then the features it shows. -->
  <div class="mx-auto flex w-full max-w-160 flex-col gap-3 rounded-xl border border-default bg-elevated/50 px-5 py-5 md:px-6">
    <span class="flex items-center gap-2 font-data text-xs uppercase tracking-wider text-primary">
      <UIcon name="i-mdi-open-in-new" class="size-4" /> Open in OSTA
    </span>
    <ul class="flex list-disc flex-col gap-2 pl-5 text-[0.98rem] leading-relaxed">
      <li v-for="link in links" :key="link.label + link.note">
        <NuxtLink v-if="link.to" :to="link.to" target="_blank" class="text-primary underline underline-offset-3">{{ link.label }}</NuxtLink>
        <template v-else>{{ link.label }}</template><template v-if="link.note">. {{ link.note }}</template>
      </li>
    </ul>
    <div class="flex flex-wrap gap-1.5">
      <UBadge v-for="f in features" :key="f" :label="f" color="neutral" variant="subtle" class="font-sans" />
    </div>
  </div>
</template>

<script setup lang="ts">
export interface OpenLink {
  label: string
  /** A view in the app; omit for an instruction with no link. */
  to?: string
  note?: string
}

defineProps<{ links: OpenLink[], features: string[] }>()
</script>
