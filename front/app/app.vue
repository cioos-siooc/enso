<template>
  <UApp>
    <div class="flex h-screen flex-col bg-default text-default">
      <header class="flex shrink-0 items-center gap-2 border-b border-default px-3 py-2 md:gap-3 md:px-4">
        <img src="/osta-logo.svg" alt="" class="size-6 shrink-0 md:size-8" >
        <div class="min-w-0">
          <h1 class="truncate text-sm font-semibold leading-tight">
            <!-- A phone has room for the abbreviation beside the CIOOS logo, not
                 the full name; the full name is the tab title and About's lead. -->
            <span class="md:hidden">OSTA</span>
            <span class="hidden md:inline">Ocean Surface Temperature Atlas (OSTA)</span>
          </h1>
          <!-- The source line is reference, not orientation; a phone header has
               room for the title and the two buttons and nothing else. -->
          <p class="hidden text-xs leading-tight text-muted md:block">
            NOAA Coral Reef Watch CoralTemp v3.1 &middot; daily &middot; 0.05&deg;
            <!-- The years come from the variable's own declaration, not from a
                 literal: `mhw` has a DIFFERENT baseline, so a hard-coded pair
                 here is one `v-if` away from labelling the wrong one. -->
            <span v-if="store.activeBaseline"> &middot; {{ store.activeBaselinePhrase }}</span>
          </p>
        </div>
        <div class="grow" />
        <!-- The app's own mark leads; the host organisation sits at the far end,
             so the bar never shows two logos side by side. -->
        <a
          href="https://cioospacific.ca"
          target="_blank"
          rel="noopener"
          class="shrink-0 opacity-90 transition-opacity hover:opacity-100"
          aria-label="CIOOS Pacific"
        >
          <img src="/cioospacific-logo.svg" alt="CIOOS Pacific" class="h-6 w-auto md:h-8" >
        </a>
        <!-- <UBadge v-if="store.coverage" variant="subtle" color="neutral">
          {{ store.coverage.start }} &ndash; {{ store.coverage.end }}
        </UBadge> -->
        <AboutDialog />
      </header>

      <!-- Under the header and above everything else, because it describes the
           basin rather than the current selection: it must not move when the
           map does. `shrink-0` so it keeps its one line and the page below it
           takes the rest. -->
      <StateRibbon class="shrink-0" />

      <NuxtPage class="grow overflow-hidden" />
    </div>
  </UApp>
</template>

<script setup lang="ts">
import { useMainStore } from '~/stores/main'

const store = useMainStore()

await store.loadMetadata()
</script>
