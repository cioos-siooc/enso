<template>
  <!-- The answer to the question a first-time visitor arrives with, before they
       have touched a control. Everything else on the page answers a question
       they have already framed — this cell, that region, this date — and none of
       it says whether anything is happening out there right now.

       A strip under the header rather than a card in the dock: it describes the
       whole basin, not the current selection, so it must not move when the
       selection does. It is a button, because the natural next gesture after
       reading a finding is to look at it, and the thing it selects is exactly
       the thing the sentence is about.

       There used to be a second half, the basin's marine heatwave extent against
       its 1991-2020 "normal". It was removed: the heatwave threshold is a fixed
       1985-2012 percentile in a warming ocean, so extent trends upward and no
       period's average is a normal worth comparing to. -->
  <div
    v-if="enso"
    class="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b md:gap-x-5 border-default bg-elevated/40 px-3 py-1.5 text-xs md:px-4"
  >
    <!-- First, so the caveats are found before the number they qualify. -->
    <div class="flex items-center gap-1 text-dimmed">
      <span v-if="asOf" class="hidden tabular-nums sm:inline">as of {{ asOf }}</span>

      <!-- On demand, not always on. The sentence beside it is written to be
           read without it; this is where the caveats that would otherwise
           clutter it live — chiefly that the index is not NOAA's official one,
           which is the one thing here that would be wrong to leave unsaid. -->
      <UPopover :ui="{ content: 'max-w-sm' }">
        <UButton
          icon="i-mdi-information-outline"
          variant="ghost"
          color="neutral"
          size="xs"
          aria-label="How this number is calculated"
          @click="trackEvent('state_guide_opened', {})"
        />
        <template #content>
          <div class="space-y-2.5 p-3 text-xs text-muted">
            <p v-if="enso">
              <span class="font-medium text-highlighted">ENSO.</span>
              {{ enso.label }} is the mean sea surface temperature over
              5°S–5°N, 170°W–120°W. The phase follows the three-month running mean
              of its anomaly — <span class="tabular-nums">{{ signed(enso.index) }}{{ unit }}</span>
              for {{ enso.season }} — against NOAA's ±{{ enso.threshold }}{{ unit }} threshold.
              {{ enso.seasons }} consecutive season<span v-if="enso.seasons !== 1">s</span> so far;
              NOAA calls five in a row an episode.
            </p>
            <p v-if="enso" class="text-dimmed">
              This is not NOAA's official index. NOAA rates El Niño and La Niña
              with its Relative Oceanic Niño Index (RONI), which measures Niño 3.4
              against the tropical ocean around it. The number here measures it
              against a fixed {{ enso.baseline }} average, so when the whole
              tropical ocean is warm it runs higher than NOAA's.
              <template v-if="enso.noaa">
                NOAA's RONI for {{ enso.noaa.season }} is
                <span class="tabular-nums">{{ signed(enso.noaa.value) }}{{ unit }}</span>;
                its newest values can change for up to two months.
              </template>
            </p>
            <figure v-if="enso.history?.length" class="space-y-1.5">
              <EnsoCompare :history="enso.history" :threshold="enso.threshold" :colors="COLORS" />
              <figcaption class="flex flex-wrap gap-x-3 gap-y-0.5">
                <span class="flex items-center gap-1.5">
                  <span class="h-0.5 w-3 rounded" :style="{ background: COLORS.osta }" />OSTA, vs {{ enso.baseline }}
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-0.5 w-3 rounded" :style="{ background: COLORS.noaa }" />NOAA RONI
                </span>
                <span class="text-dimmed">three-month means, dashed at +{{ enso.threshold }}{{ unit }}</span>
              </figcaption>
            </figure>
          </div>
        </template>
      </UPopover>
    </div>

    <button
      v-if="enso"
      type="button"
      class="group flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left md:flex-none"
      :title="`Show ${enso.label} — ${ensoTitle}`"
      @click="showEnso()"
    >
      <span
        class="rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
        :class="phaseClass"
      >{{ phaseWord }}</span>
      <span class="text-muted group-hover:text-default">
        <!-- The month leads, not the season: it is the most recent thing the
             archive knows and the number the rank is about. The ONI-style
             season index is the formal basis for the phase word beside it, and
             is said second. -->
        <span class="font-medium text-highlighted tabular-nums">{{ signed(enso.latestMonth.value) }}{{ unit }}</span>
        in {{ enso.label }} for {{ monthName }}<span v-if="rankPhrase">, {{ rankPhrase }}</span>
      </span>
    </button>

    <!-- NOAA's official number beside OSTA's own, because the two differ by
         most of a degree in a year when the whole tropics are warm, and the news
         quotes NOAA's. A link to CPC's page, not a selection: it is their index. -->
    <a
      v-if="enso.noaa"
      :href="enso.noaa.url"
      target="_blank"
      rel="noopener"
      class="w-full text-muted hover:text-default md:w-auto"
      :title="`${enso.noaa.source}: Relative Oceanic Niño Index for ${enso.noaa.season}`"
    >
      NOAA RONI <span class="font-medium text-highlighted tabular-nums">{{ signed(enso.noaa.value) }}{{ unit }}</span>
      for {{ enso.noaa.season }}
    </a>

  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/composables/useAnalytics'
import { useMainStore } from '~/stores/main'

const store = useMainStore()

const enso = computed(() => store.pacific?.enso ?? null)

const unit = '°C'

/** The popover chart's two lines: the ribbon's phase red, and NOAA's in sky. */
const COLORS = { osta: '#f87171', noaa: '#38bdf8' }

/** The date the finding is as of: the archive's last day. */
const asOf = computed(() => {
  const iso = store.coverage?.end
  if (!iso) return ''
  // 'en-GB' pinned, not the visitor's locale, and for a reason that only shows
  // up under SSR: this line is rendered on the server too, where Node's default
  // locale is whatever the container has, and a client that formats it
  // differently is a hydration mismatch. `utils/periods.ts` pins the same one.
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  })
})

const PHASE_WORDS: Record<string, string> = {
  el_nino: 'El Niño',
  la_nina: 'La Niña',
  neutral: 'Neutral',
}

/**
 * The phase, with its strength where there is one.
 *
 * NOAA's five-season rule is what separates an *episode* from *conditions*, and
 * the badge honours it: below five seasons this says "El Niño conditions"
 * rather than declaring an event that has not met the definition yet. Neutral
 * takes no strength — a "weak neutral" is not a thing.
 */
const phaseWord = computed(() => {
  const e = enso.value
  if (!e) return ''
  const name = PHASE_WORDS[e.phase] ?? e.phase
  if (e.phase === 'neutral') return name
  return e.episode ? `${e.strength} ${name}` : `${name} conditions`
})

const phaseClass = computed(() => ({
  el_nino: 'bg-red-500/15 text-red-400',
  la_nina: 'bg-sky-500/15 text-sky-400',
  neutral: 'bg-elevated text-muted',
}[enso.value?.phase ?? 'neutral']))

const monthName = computed(() => {
  const iso = enso.value?.latestMonth.month
  if (!iso) return ''
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', {
    month: 'long', timeZone: 'UTC',
  })
})

function signed(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`
}

/**
 * "the warmest August in 42 years", when the month is actually near the top.
 *
 * Only for the first three: a rank of 19 is not a finding, and a ribbon that
 * reports one every month teaches the reader to stop looking at it. The word
 * follows the sign, so a record cold month reads as coldest rather than as a
 * warmest-of-the-bottom.
 */
const rankPhrase = computed(() => {
  const m = enso.value?.latestMonth
  if (!m || m.rank > 3) return ''
  const warm = m.value >= 0
  const nth = m.rank === 1
    ? (warm ? 'the warmest' : 'the coldest')
    : `${m.rank === 2 ? '2nd' : '3rd'} ${warm ? 'warmest' : 'coldest'}`
  const so_far = m.partial ? ' so far' : ''
  return `${nth} ${monthName.value} in ${m.of} years${so_far}`
})

const ensoTitle = computed(() =>
  `${phaseWord.value} · ${signed(enso.value?.index ?? 0)}${unit} for ${enso.value?.season}`)

/**
 * Selects what the sentence is about. The variable is set too, not just the
 * region: reading "El Niño" and landing on a marine-heatwave chart of
 * Niño 3.4 would be a non-sequitur, and the ribbon's whole point is that the
 * next click needs no thought.
 */
function showEnso() {
  const e = enso.value
  if (!e) return
  trackEvent('state_ribbon_clicked', { half: 'enso', region: e.region, phase: e.phase, variable: 'anom' })
  // One call, because the two are one gesture: `setVariable` followed by
  // `selectRegion` fetched the region being left behind as well, and the two
  // rollup reads race.
  store.showRegion(e.region, 'anom')
}

</script>
