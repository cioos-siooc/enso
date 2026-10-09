<template>
  <div>
    <!-- Scrolls in its own container, like every story (see blob.vue). The
         three font roles the story components use are pointed at this story's
         faces here, so the components need no prop for it. -->
    <div class="h-full overflow-y-auto bg-default font-serif text-[1.1rem] leading-[1.65] text-default [--font-data:var(--font-martian)] [--font-display:var(--font-anybody)] [--font-serif:var(--font-source-serif)] [--story-stretch:120%]">
      <!-- ============ edition strip ============ -->
      <!-- Sticky from md up; on a phone it would take four lines of a short pane. -->
      <div class="z-10 border-b border-default bg-default/95 backdrop-blur md:sticky md:top-0">
        <div class="mx-auto flex w-full max-w-280 flex-wrap items-center gap-x-5 gap-y-1.5 px-5 py-2.5 font-data text-[0.7rem] tracking-wide text-muted">
          <span class="flex items-center gap-2 uppercase text-orange-400">
            <span class="size-2 rounded-full bg-orange-400 motion-safe:animate-pulse" /> Ongoing · edition {{ edition.number }}
          </span>
          <span>OSTA data through <b class="font-medium text-highlighted">{{ edition.through }}</b></span>
          <span>News checked <b class="font-medium text-highlighted">{{ edition.checked }}</b></span>
          <span>Next update <b class="font-medium text-highlighted">{{ edition.next }}</b></span>
          <a href="#log" class="underline underline-offset-3">Update log</a>
        </div>
      </div>

      <main class="px-5 pb-16">
        <!-- ============ hero ============ -->
        <header class="mx-auto grid w-full max-w-280 items-center gap-8 py-9 md:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] md:gap-12 md:py-13">
          <div class="flex flex-col gap-5">
            <span class="font-data text-xs uppercase tracking-wider text-muted">CIOOS Pacific · Ocean Surface Temperature Atlas</span>
            <h1 class="font-display text-[clamp(2.35rem,6vw,4.4rem)] font-[850] leading-[1.02] tracking-[-0.015em] text-balance text-highlighted [font-stretch:112%] md:[font-stretch:130%]">
              El Niño 2026, month by month
            </h1>
            <p class="text-[1.18rem]">
              The central and eastern equatorial Pacific is warmer than at any time in NOAA's satellite record, which begins in 1985. This page follows the 2026 El Niño as it unfolds: each month it adds the newest month of that data, viewed in the Ocean Surface Temperature Atlas (OSTA), and the news from the places it reaches.
            </p>
            <p>Every map and chart here is a screenshot of OSTA. The links under each one open the same view in the app, so you can click a cell, change the date or compare a past event yourself.</p>
          </div>
          <figure class="flex flex-col gap-2.5">
            <StoryPlayer
              :frames="heroFrames"
              :notes="heroNotes"
              base="/story-assets/el-nino-2026/hero"
              alt="Globe centred on the eastern Pacific showing the monthly SST anomaly"
              :legend="['−5 °C', '+5 °C']"
              :interval="800"
              start-at-end
            />
            <figcaption class="font-data text-xs leading-relaxed text-muted">
              Monthly SST anomaly against the 1991–2020 normal, from January 2026, drawn on OSTA's “Wide ±5” colour range.
              <NuxtLink :to="storyLink({ v: 'anom', p: 'monthly', d: '2026-01-01', at: '-5.07,-81.28' })" target="_blank" class="text-primary underline underline-offset-3">Open January 2026 in OSTA</NuxtLink> and press play.
            </figcaption>
          </figure>
        </header>

        <!-- ============ the month in five numbers ============ -->
        <section class="mx-auto w-full max-w-280" :aria-label="`${edition.month} in five numbers`">
          <p class="mb-3 font-data text-xs uppercase tracking-wider text-muted">
            {{ edition.month }} in five numbers · records are since 1985, when NOAA's satellite data begin
          </p>
          <div class="grid grid-cols-2 border-y border-default lg:grid-cols-5">
            <div
              v-for="(tile, i) in tiles"
              :key="tile.to"
              class="flex min-w-0 flex-col gap-2 border-default px-4 py-5"
              :class="[i % 2 ? 'border-l' : '', i < tiles.length - 1 ? 'border-b lg:border-b-0' : 'col-span-2 lg:col-span-1', i ? 'lg:border-l' : '']"
            >
              <span class="font-display text-[clamp(1.9rem,3.2vw,2.5rem)] font-[850] leading-none text-orange-400 tabular-nums [font-stretch:125%]">
                {{ tile.value }}<small class="text-[0.5em] font-bold"> {{ tile.unit }}</small>
              </span>
              <p class="text-[0.9rem] leading-snug">{{ tile.text }}</p>
              <span class="mt-auto font-data text-[0.66rem] text-muted">{{ tile.was }}</span>
              <NuxtLink :to="tile.to" target="_blank" class="font-data text-[0.66rem] text-primary hover:underline">Open in OSTA ↗</NuxtLink>
            </div>
          </div>
        </section>

        <!-- ============ 1. Niño 3.4 ============ -->
        <StoryChapter id="index" accent eyebrow="01 · Niño 3.4" title="Warmer than 1997 and 2015, two months earlier">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>In January, Niño 3.4 was still slightly cool at −0.46 °C, the tail of last winter's La Niña. It crossed the +0.5 °C El Niño threshold in April and gained about half a degree a month from there. By September it averaged +3.07 °C, the warmest month this region has had in the 42-year satellite record.</p>
            <p>The comparison that matters is the calendar. The two strongest El Niños since the record began, 1997–98 and 2015–16, both peaked in November, at +2.42 and +2.81 °C. This one passed 1997's peak in August and 2015's in September. Day by day, the Niño 3.4 mean broke its previous record (+2.99 °C on 19 November 2015) on 13 September and reached +3.27 °C on 30 September.</p>
          </div>

          <figure class="mx-auto flex w-full max-w-280 flex-col gap-2.5">
            <div class="rounded-xl border border-default bg-elevated/50 px-4 pb-2 pt-4">
              <div class="mb-2 flex flex-wrap gap-x-5 gap-y-1 font-data text-[0.68rem] text-muted">
                <span v-for="(k, n) in raceKey" :key="k" class="flex items-center gap-1.5" :style="{ color: RACE_COLORS[n] }">
                  <i class="inline-block h-0.75 w-4" :style="{ background: RACE_COLORS[n] }" />{{ k }}
                </span>
                <span>monthly Niño 3.4 anomaly, °C, from January of the first year</span>
              </div>
              <StoryRace
                :series="data.race"
                :colors="RACE_COLORS"
                :thresholds="[{ value: 0.5, label: 'El Niño +0.5' }, { value: 2, label: 'very strong +2.0' }]"
                label="Monthly Niño 3.4 anomaly for three El Niño events, from January of each event's first year. 2026 runs above both 1997 and 2015."
              />
            </div>
            <figcaption class="font-data text-xs leading-relaxed text-muted">
              NOAA Coral Reef Watch CoralTemp data averaged over Niño 3.4 (5°S–5°N, 170°W–120°W): monthly means of the daily area-mean anomaly against 1991–2020, as OSTA plots them. Dashed lines mark NOAA's thresholds for El Niño (+0.5 °C) and a very strong event (+2.0 °C).
            </figcaption>
          </figure>

          <div class="mx-auto grid w-full max-w-280 items-start gap-7 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <StoryFigure
              src="/story-assets/el-nino-2026/nino34.webp"
              :to="links.nino34"
              alt="OSTA with the Niño 3.4 region selected for September 2026. The dock shows +3.1 °C and the September ranking with 2026 at the top, ahead of 2015 and 1997. The chart below shows the anomaly since 1985 ending in a spike above 3 °C."
            >
              OSTA in region mode on Niño 3.4. The ranking under the numbers puts every September since 1985 in order; 2026 is first at +3.07 °C, then 2015 (+2.19) and 1997 (+2.00). The red bar across the top of the app is OSTA's ENSO summary, worked out from the same NOAA data.
            </StoryFigure>
            <div class="flex flex-col gap-5">
              <p>These are not NOAA's official El Niño numbers. OSTA measures how much warmer Niño 3.4 is than its 1991–2020 average. NOAA's official index, the Relative Oceanic Niño Index (RONI), measures how much warmer Niño 3.4 is than the tropical ocean around it. This year the whole tropical ocean is unusually warm, so OSTA's number comes out higher than NOAA's.</p>
              <p>Measured OSTA's way, July to September 2026 averaged +2.65 °C, just under the +2.67 °C of November 2015 to January 2016. That compares the two events on one method; it is not an official ranking. Official statements on how strong this El Niño is come from NOAA and the World Meteorological Organization, and are in the news below.</p>
            </div>
          </div>

          <StoryWire :items="news.index" />
          <StoryOpen
            :links="[
              { label: 'Niño 3.4, September 2026', to: links.nino34, note: 'Switch the ranking from Month to Year to rank whole years' },
              { label: 'Niño 3.4 against Niño 1+2', to: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', r: 'nino34', r2: 'nino12' }), note: 'Two regions on one chart; the coastal box runs two degrees hotter' },
              { label: 'The bar across the top of the app reads Very strong El Niño', note: 'Its ⓘ button explains how OSTA makes that reading' },
            ]"
            :features="['Region scope', 'Monthly and yearly rankings', 'Compare B', 'ENSO ribbon']"
          />
        </StoryChapter>

        <!-- ============ 2. Peru ============ -->
        <StoryChapter id="peru" accent eyebrow="02 · Peru's coast" title="“Beyond extreme” off northern Peru">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>El Niño is strongest where the warm water piles up against South America. In September the sea off Paita, in northern Peru, averaged 7.1 °C above normal; the warmest September there before this was 1997, at +4.3 °C. Further south, Chimbote was +5.8 °C and Callao, Lima's port, +4.8 °C. All three are records for September.</p>
            <p>OSTA also shows NOAA's daily marine heatwave category for every cell. The water off Paita has been in a heatwave since 14 May, 140 days by the end of September, and spent 23 September days in the top class, “Beyond extreme”. The dock keeps count. It also lists the cell's longest run on record: 370 days, from April 1997 to May 1998.</p>
          </div>
          <StoryFigure
            src="/story-assets/el-nino-2026/peru.webp"
            :to="links.paita"
            alt="OSTA showing NOAA's marine heatwave categories off Ecuador and Peru on 30 September 2026, mostly orange and red. A pin off Paita; the dock reads category 3 Severe, in a heatwave for 143 days since 14 May 2026, longest heatwave 370 days from 1997 to 1998."
          >
            Heatwave categories on 30 September 2026, with a pin off Paita. The dock's “In a heatwave for” card is counted up to the newest day in the archive (143 days on 3 October). The chart below has two spikes reaching Cat 5: 1997–98 and now.
          </StoryFigure>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>
              A category is not an anomaly. NOAA applies the definition of
              <a href="https://doi.org/10.1016/j.pocean.2015.12.014" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">Hobday et al. (2016)</a>:
              the water stays above its 90th percentile for that time of year, measured against 1985–2012. The classes, from
              <a href="https://doi.org/10.5670/oceanog.2018.205" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">Hobday et al. (2018)</a>,
              count multiples of the gap between that percentile and the normal: Moderate, Strong, Severe and Extreme. NOAA adds an open-ended fifth class above them, “Beyond extreme”.
            </p>
            <p>On land, Peru's coast is in its dry season, so OSTA cannot express its rainfall as a share of normal there. Temperatures can be: September nights at Piura were 5.2 °C warmer than normal, and days 3.7 °C warmer.</p>
          </div>
          <StoryWire :items="news.peru" />
          <StoryOpen
            :links="[
              { label: 'Heatwave categories off Paita', to: links.paita, note: 'Click anywhere on the coast for that cell\'s heatwave run' },
              { label: 'Paita against Callao', to: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', at: '-5.07,-81.28', at2: '-12.07,-77.28' }), note: 'Alt-click the map to drop your own second point' },
              { label: 'Night-time temperature at Piura', to: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', land: 'tmin', lm: 'anomaly', at: '-5.19,-80.63' }), note: 'The land overlay; a pin on land charts the land cell' },
            ]"
            :features="['MHW categories', 'Heatwave runs', 'Compare two points', 'Land overlay']"
          />
        </StoryChapter>

        <!-- ============ 3. Galápagos and Ecuador ============ -->
        <StoryChapter id="galapagos" accent eyebrow="03 · Galápagos and Ecuador" title="The Galápagos, against 1997">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>The west coast of Isabela, where cold water normally wells up around the Galápagos, averaged 6.5 °C above normal in September. That beats September 1997 there by more than a degree, and the cell has been in a heatwave since 18 May, at Severe or Extreme for the whole month. On Ecuador's mainland coast, the sea off Santa Elena was 4.7 °C above normal, well clear of its previous September high (+3.0 °C in 2023).</p>
            <p>OSTA's swipe compare puts two dates side by side on one map. Below, September 2026 is on the left and September 1997 on the right, on the same colour range.</p>
          </div>
          <StoryFigure
            src="/story-assets/el-nino-2026/galapagos.webp"
            :to="links.galapagos"
            alt="OSTA swipe compare over the eastern equatorial Pacific: September 2026 on the left, September 1997 on the right, both deep red near the Galápagos. A pin on west Isabela; the dock reads +6.5 °C and ranks September 2026 first, 1997 second."
          >
            Swipe compare, September 2026 (left) and September 1997 (right), on the ±5 °C range. The chart marks both dates: amber MAP for 2026, blue CMP for 1997. Drag the divider in the app to sweep between them.
          </StoryFigure>
          <StoryWire :items="news.galapagos" />
          <p class="mx-auto w-full max-w-160 text-[0.92rem] text-muted">
            Those floods came at the very end of September. NOAA's gauge data still had the month as dry at Quinindé in Esmeraldas (0.5 mm a day, 1.7 below normal), so the rain should show in October's map.
          </p>
          <StoryOpen
            :links="[
              { label: 'September 2026 against September 1997', to: links.galapagos, note: 'Choose Wide ±5 from the colour legend to see past +3 °C' },
              { label: 'With compare on, Alt-click the chart to move the second date' },
            ]"
            :features="['Swipe compare', 'Colour range presets', 'Chart-driven dates']"
          />
        </StoryChapter>

        <!-- ============ 4. Indonesia ============ -->
        <StoryChapter id="indonesia" accent eyebrow="04 · Across the Pacific" title="On the other side, the rain stopped">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>El Niño moves the tropical Pacific's rain east with the warm water, so the western side dries out. NOAA's daily gauge analysis, which OSTA draws as a land overlay, shows it plainly. At Palangka Raya, in Central Kalimantan, the record has essentially no rain for August or September; September came in 3.5 mm a day below normal. Palembang, in South Sumatra, had 0.1 mm a day. Afternoons in both were 2 °C warmer than normal.</p>
          </div>
          <StoryFigure
            src="/story-assets/el-nino-2026/indonesia.webp"
            :to="links.indonesia"
            :width="920"
            :height="813"
            alt="OSTA map of Indonesia for September 2026 with precipitation versus normal drawn on land: most of Kalimantan and southern Sumatra deep brown, meaning drier than normal. Below, a chart of monthly precipitation departure at Palangka Raya since 1985."
          >
            September 2026, with the land overlay on precipitation in “mm vs normal”: brown is drier, teal wetter, and the ocean anomaly sits underneath. The pin is on Palangka Raya, so the chart plots that land cell on its own right-hand axis.
          </StoryFigure>
          <StoryWire :items="news.indonesia" />
          <StoryOpen
            :links="[
              { label: 'Precipitation over Indonesia, September 2026', to: links.indonesia, note: 'Use the time bar\'s back arrow to step through July and August' },
              { label: 'Switch Land to Tmax for the heat that came with it' },
            ]"
            :features="['Land overlay', 'Tmax, Tmin, precipitation', 'Land charts on a second axis']"
          />
        </StoryChapter>

        <!-- ============ 5. West coast and BC ============ -->
        <StoryChapter id="bc" accent eyebrow="05 · Up the coast" title="California's seabirds, and what BC is watching">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>The North American coast was already warm before El Niño arrived. The water off San Diego was above normal in every month of 2026 so far, by 1.0 to 2.4 °C, and it was back in a heatwave from 9 September. In July, AP reported pelicans, murres and cormorants starving along the California coast.</p>
            <p>BC's waters are not there yet. Across DFO's Pacific bioregions, September was 0.4 °C above normal, 16th of 42 Septembers. During the 1997–98 El Niño the same water stayed warm through the winter, from +0.6 °C in November to +1.05 °C in March, and February 1998 is still the region's third-warmest February. OSTA can put the tropics and BC on one chart, which is how to see whether that happens again.</p>
          </div>
          <StoryFigure
            src="/story-assets/el-nino-2026/bc.webp"
            :to="links.bc"
            alt="OSTA comparing two regions: A, Niño 3.4, and B, Pacific Bioregions (DFO). The chart shows both anomalies since 1985, the tropical line with large El Niño spikes and the BC line smaller."
          >
            Two regions on one chart: A is Niño 3.4 (green), B is BC's Pacific bioregions (violet). Follow the violet line through the winters of 1997–98 and 2015–16.
          </StoryFigure>
          <StoryWire :items="news.bc" />
          <StoryOpen
            :links="[
              { label: 'Niño 3.4 against BC\'s waters', to: links.bc, note: 'Drag the slider under the chart to zoom into 1997–98' },
              { label: 'Heatwave categories off San Diego', to: storyLink({ v: 'mhw', p: 'daily', d: '2026-09-30', at: '32.72,-117.43' }) },
              { label: 'Night-time temperature at Kamloops', to: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', land: 'tmin', lm: 'anomaly', at: '50.67,-120.33' }), note: 'The winter signal to watch on land' },
            ]"
            :features="['Two regions on one chart', 'DFO bioregions', 'Chart zoom', 'Land overlay']"
          />
        </StoryChapter>

        <!-- ============ 6. Global ============ -->
        <StoryChapter id="global" accent eyebrow="06 · The whole ocean" title="A record September for the world's oceans">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>Averaged over the whole global ocean, September was 0.78 °C above normal, the warmest September in the satellite record; the Pacific alone was +0.85 °C. On an average September day, 45.6% of the global ocean's area was in a marine heatwave, against 40.4% in September 2023, the previous high.</p>
            <p>That extent needs one caution. NOAA's heatwave threshold is fixed to 1985–2012, so as the ocean warms, more of it crosses the line every year. Part of any new record is the trend, and OSTA prints it beside the number.</p>
          </div>
          <StoryFigure
            src="/story-assets/el-nino-2026/global.webp"
            :to="links.global"
            alt="OSTA flat map of the world's oceans for September 2026 with the global ocean selected. The equatorial Pacific is deep red. The dock reads +0.8 °C and ranks September 2026 first; the chart shows the global anomaly rising since 1985."
          >
            The Flat projection and the Global ocean region. The chart under the map is the whole ocean's anomaly since 1985; the dock prints its trend, +0.19 °C per decade.
          </StoryFigure>
          <StoryWire :items="news.global" />
          <StoryOpen
            :links="[
              { label: 'The global ocean, September 2026', to: links.global, note: 'Switch to Flat to see the whole map' },
              { label: 'Heatwave extent, global ocean', to: storyLink({ v: 'mhw', p: 'monthly', d: '2026-09-01', r: 'global' }), note: 'In region mode, MHW is the share of the area in a heatwave' },
              { label: 'Use Download data to save any series as a CSV' },
            ]"
            :features="['Globe and flat projections', 'Heatwave extent', 'Trend', 'CSV export']"
          />
        </StoryChapter>

        <!-- ============ watch list ============ -->
        <StoryChapter id="watch" accent eyebrow="Next edition" :title="`What to watch in ${edition.nextMonth}`">
          <ul class="mx-auto grid w-full max-w-280 border-t border-default sm:grid-cols-2">
            <li
              v-for="(w, i) in watch"
              :key="w.title"
              class="flex min-w-0 flex-col gap-1.5 border-b border-default py-4.5"
              :class="i % 2 ? 'sm:border-l sm:pl-5' : 'sm:pr-5'"
            >
              <strong class="font-display text-[1.05rem] font-bold text-highlighted [font-stretch:110%]">{{ w.title }}</strong>
              <p class="text-[0.95rem] leading-normal">{{ w.text }}</p>
            </li>
          </ul>
        </StoryChapter>

        <!-- ============ log and sources ============ -->
        <footer id="log" class="mx-auto mt-16 flex w-full max-w-160 scroll-mt-14 flex-col gap-4 border-t border-default pt-9">
          <p class="font-data text-xs uppercase tracking-wider text-muted">Update log</p>
          <ol class="flex flex-col gap-1 font-data text-xs leading-relaxed">
            <li v-for="entry in log" :key="entry.date" class="grid gap-x-3 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <span class="text-muted">{{ entry.date }}</span><span>{{ entry.text }}</span>
            </li>
          </ol>

          <p class="mt-4 font-data text-xs uppercase tracking-wider text-muted">How this page is made</p>
          <p class="text-[0.92rem] text-muted">
            The data are NOAA's (listed below). Every number on this page was read from them through OSTA on the day of the edition, for the last complete month, and the screenshots are of OSTA itself. A record means a record since 1 January 1985, where NOAA's satellite data begin. News items are summarised from the linked articles, and quotes are as they appear there. Claims about records in the news are those outlets' and their sources', on their own datasets.
          </p>

          <p class="mt-4 font-data text-xs uppercase tracking-wider text-muted">Data and references</p>
          <ol class="flex list-decimal flex-col gap-2 pl-5 text-[0.88rem] leading-normal">
            <li>NOAA Coral Reef Watch, CoralTemp v3.1 daily sea surface temperature, 0.05°. Anomalies in OSTA are against a 1991–2020 daily climatology.</li>
            <li>NOAA Coral Reef Watch, Marine Heatwave category v1.0.1, after Hobday et al. 2016 and 2018.</li>
            <li>NOAA Climate Prediction Center, Global Unified gauge-based precipitation and temperature (land overlay), 1991–2020 normals computed in OSTA.</li>
            <li v-for="r in references" :key="r.doi">
              {{ r.text }} <i>{{ r.journal }}</i> {{ r.where }}.
              <a :href="`https://doi.org/${r.doi}`" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">doi:{{ r.doi }}</a>
            </li>
          </ol>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The 2026 El Nino, followed month by month. Updated at the start of each
 * month with the last closed month of OSTA data and that month's news; the
 * runbook is stories/el-nino-2026/UPDATE.md at the repo root.
 *
 * `data` is written by that directory's measure.py and drives the hero's
 * frames and readings and the race chart. Everything else an edition changes
 * (the numbers in the prose, `edition`, `tiles`, `news`, `watch`, `log`) is
 * edited here by hand, from the same file.
 */
import data from '~/data/stories/el-nino-2026.json'
import type { WireItem } from '~/components/story/Wire.vue'

useSeoMeta({
  title: 'El Niño 2026, month by month · OSTA',
  description: 'The record 2026 El Niño followed through OSTA\'s data and the news from the places it reaches, updated monthly.',
})

const edition = {
  number: 1,
  month: 'September 2026',
  through: '30 Sep 2026',
  checked: '8 Oct 2026',
  next: 'early November',
  nextMonth: 'October',
}

const links = {
  nino34: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', r: 'nino34' }),
  paita: storyLink({ v: 'mhw', p: 'daily', d: '2026-09-30', at: '-5.07,-81.28' }),
  galapagos: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', c: '1997-09-01', at: '-0.52,-91.72' }),
  indonesia: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', land: 'precip', lm: 'difference', at: '-2.21,113.92' }),
  bc: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', r: 'nino34', r2: 'pacific_bioregions' }),
  global: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', r: 'global' }),
}

/** One hero frame per month of 2026 read so far, each with its Niño 3.4 reading. */
const months2026 = data.nino.nino34.months_2026 as Array<[string, number]>
const heroFrames = months2026.map(([m]) => `${m}-01`)
const heroNotes = months2026.map(([, v]) => `Niño 3.4 ${signed(v)} °C`)

/** 2026 in the accent; 2015 cool; 1997 grey. Follows data.race's order. */
const RACE_COLORS = ['#a3a3a3', '#79b5c8', '#ef6a3a']
const raceKey = ['1997–98, peak +2.42 in Nov', '2015–16, peak +2.81 in Nov', '2026–27']

const tiles = [
  { value: '+3.07', unit: '°C', text: 'Niño 3.4, the region NOAA uses to track El Niño. Its warmest month since the satellite record began in 1985.', was: 'previous high: Nov 2015, +2.81', to: links.nino34 },
  { value: '+5.29', unit: '°C', text: 'Niño 1+2, the water off Ecuador and northern Peru. Also its warmest month.', was: 'previous high: Aug 1997, +4.27', to: storyLink({ v: 'anom', p: 'monthly', d: '2026-09-01', r: 'nino12' }) },
  { value: '23', unit: 'of 30 days', text: 'Off Paita, Peru, in NOAA\'s top heatwave category, “Beyond extreme”.', was: 'in a heatwave since 14 May', to: links.paita },
  { value: '+0.78', unit: '°C', text: 'The global ocean\'s warmest September since 1985.', was: 'previous high: Sep 2023, +0.64', to: links.global },
  { value: '48.8', unit: '%', text: 'Share of the Pacific in a marine heatwave on an average September day. The most for any September.', was: 'previous high: Sep 2023, 44.4%', to: storyLink({ v: 'mhw', p: 'monthly', d: '2026-09-01', r: 'pacific' }) },
]

/** Each article was opened and checked against these lines before it went in. */
const news: Record<string, WireItem[]> = {
  index: [
    { date: '8 Oct 2026', iso: '2026-10-08', source: 'NOAA Climate Prediction Center', title: 'ENSO Diagnostic Discussion', href: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml', text: '“El Niño continues to strengthen.” NOAA puts an 83% chance on October–December beating every event since 1950, meaning a three-month RONI above +2.5 °C.' },
    { date: '29 Sep 2026', iso: '2026-09-29', source: 'Inside Climate News', title: 'Incoming El Niño is so extreme it doesn\'t have a scientific name', href: 'https://insideclimatenews.org/news/29092026/record-breaking-el-nino-grows-in-pacific/', text: 'NOAA\'s strength scale stops at “very strong”. Climate scientist Daniel Swain: “We don\'t have a categorization for this.”' },
    { date: '24 Sep 2026', iso: '2026-09-24', source: 'Science News', title: 'This year\'s El Niño just broke a record months before it\'s expected to peak', href: 'https://www.sciencenews.org/article/record-breaking-el-nino-temperatures', text: 'On 21 September, Niño 3.4 was 3.08 °C above its 1991–2020 average, beating the 3.02 °C of November 2015. “The transition has been very rapid, from a La Niña last winter to a very strong El Niño in less than a year,” said Nathaniel Johnson of NOAA\'s Geophysical Fluid Dynamics Laboratory.' },
    { date: '3 Sep 2026', iso: '2026-09-03', source: 'World Meteorological Organization', title: 'El Niño set to become very strong, raising risks of extreme weather into 2027', href: 'https://wmo.int/news/media-centre/el-nino-set-become-very-strong-raising-risks-of-extreme-weather-2027', text: 'A nearly 100% likelihood that El Niño lasts through February 2027. “This exceptional El Niño demands exceptional preparation and response,” said WMO Secretary-General Celeste Saulo.' },
    { date: '27 Aug 2026', iso: '2026-08-27', source: 'Science · Cole et al.', title: 'Recent strengthening of eastern Pacific ENSO in the last millennium paleorecord', href: 'https://doi.org/10.1126/science.ady2660', text: 'Galápagos coral cores show El Niños of the last four decades were stronger than any in the 1,000 years before about 1850. The study is about past events, not this one, but it is where talk of a “millennium” comes from.' },
  ],
  peru: [
    { date: '8 Jul 2026', iso: '2026-07-08', source: 'Grist', title: 'El Niño is here, and it\'s already scrambling fisheries throughout the Pacific', href: 'https://grist.org/economics/el-nino-scrambling-fisheries-throughout-the-pacific/', text: 'Peru suspended its anchoveta fishery, the world\'s largest single-species fishery, and boats with sonar found the fish more than 100 m down, beyond the reach of their nets. Prices for jack mackerel and corvina reportedly doubled. “Our vulnerability is increasing,” said Oceana Peru economist Juan Carlos Sueiro.' },
    { date: '3 Jul 2026', iso: '2026-07-03', source: 'The Watchers', title: 'Peru declares state of emergency ahead of 2026–2027 El Niño rains', href: 'https://watchers.news/2026/07/03/peru-declares-state-of-emergency-ahead-of-2026-2027-el-nino-rains/', text: 'A 60-day emergency in 796 districts across 22 departments and Callao, for “the imminent threat of intense rainfall”.' },
  ],
  galapagos: [
    { date: '3 Oct 2026', iso: '2026-10-03', source: 'El Comercio (Spanish)', title: 'El fenómeno de El Niño deja ríos desbordados en Esmeraldas y Pastaza', href: 'https://www.elcomercio.com/actualidad/ecuador/fenomeno-nino-inundaciones-esmeraldas/', text: 'Nine rivers burst their banks in Esmeraldas and Pastaza provinces, affecting about 800 families.' },
    { date: '4 Sep 2026', iso: '2026-09-04', source: 'Charles Darwin Foundation', title: 'El Niño 2026 in Galápagos', href: 'https://www.darwinfoundation.org/en/news/all-news-stories/el-nino-2026-in-galapagos/', text: 'Marine iguanas lose weight as their algae die back, and seabirds may abandon nests. “Corals will probably be among the biggest losers,” said science director María José Barragán.' },
    { date: '6 Aug 2026', iso: '2026-08-06', source: 'American Bird Conservancy', title: 'Pacific seabird die-offs demonstrate the need for fishery action', href: 'https://abcbirds.org/news/pacific-seabird-dieoff-2026/', text: 'Surveys on Ecuador\'s coast counted 638 dead seabirds in June and 968 in July, against a few dozen a month before. Sooty shearwaters, boobies and the critically endangered waved albatross were among them. “Our recent surveys have been reporting seabird strandings and deaths every day, but it started to explode in June,” said Sebástian Cruz, the group\'s marine program coordinator for South America.' },
  ],
  indonesia: [
    { date: '7 Sep 2026', iso: '2026-09-07', source: 'ABC News (Australia)', title: 'Indonesian wildfires spurred by super El Niño choke South-East Asia', href: 'https://www.abc.net.au/news/2026-09-07/indonesia-wildfires-haze-poor-air-quality-smog-drought-el-nino/107122922', text: 'At least 200,000 hectares burned, an air quality index above 900 in Pontianak, and smoke reaching the Philippines. “Indeed worse than in 2015,” said firefighter Andri Susanto.' },
  ],
  bc: [
    { date: '21 Aug 2026', iso: '2026-08-21', source: 'ClimateData.ca · Canadian Centre for Climate Services', title: 'What the developing exceptional El Niño means for Canada in 2026–27', href: 'https://climatedata.ca/news/what-the-developing-exceptional-el-nino-means-for-canada-in-2026-27/', text: 'A warmer-than-normal winter across much of BC, drier especially over the Rockies and the Okanagan. ECCC\'s Bill Merryfield: some forecasts approach or exceed 4 °C, “which would be unprecedented in the modern record by a substantial margin.”' },
    { date: '1 Jul 2026', iso: '2026-07-01', source: 'Associated Press, via the Press Democrat', title: 'A marine heat wave caused seabird deaths off California. El Niño could worsen the die-off', href: 'https://www.pressdemocrat.com/2026/07/01/record-ocean-heat-and-el-nino-are-leading-to-mass-california-seabird-die-offs/', text: '“We\'ve been seeing cormorants walk to shore and then just die within the hour,” said Tammy Russell of Scripps Institution of Oceanography.' },
    { date: '12 Jun 2026', iso: '2026-06-12', source: 'NOAA Fisheries', title: '7 ways El Niño and large marine heatwave could affect West Coast marine species', href: 'https://www.fisheries.noaa.gov/feature-story/7-ways-el-nino-and-large-marine-heatwave-could-affect-west-coast-marine-species', text: 'Hungry sea lion pups, harmful algal blooms that close crab and shellfish fisheries, poorer salmon survival, and whales pushed into fishing gear.' },
    { date: '25 Mar 2026', iso: '2026-03-25', source: 'Watershed Watch Salmon Society', title: '2026 salmon outlook, part 1: environmental conditions', href: 'https://watershedwatch.ca/stories/2026-salmon-outlook-part-1-environmental-conditions/', text: 'El Niño years tend to bring warmer, less productive conditions for BC salmon.' },
  ],
  global: [
    { date: '15 Sep 2026', iso: '2026-09-15', source: 'Carbon Brief', title: 'Temperature “overshoot”, world\'s warmest month and the catastrophic 1877–78 El Niño', href: 'https://www.carbonbrief.org/cited-15-september-2026-temperature-overshoot-worlds-warmest-month-catastrophic-1877-78-el-nino', text: 'Copernicus found August 2026 tied July 2023 as the warmest month on record, at 16.96 °C, 1.65 °C above pre-industrial.' },
  ],
}

const watch = [
  { title: 'Does Niño 3.4 keep climbing?', text: 'The first three days of October averaged +3.30 °C. NOAA gives October–December an 83% chance of beating every event since 1950.' },
  { title: 'Paita\'s heatwave: day 140', text: 'The 1997–98 run off Paita lasted 370 days. This one began on 14 May.' },
  { title: 'Rain on Ecuador\'s and Peru\'s coast', text: 'The Esmeraldas floods came at the end of September. October\'s land map will show how widespread the rain was.' },
  { title: 'Peru\'s anchovy fishery', text: 'Whether a second fishing season opens this year, after the first was cut short.' },
  { title: 'Indonesia\'s dry season', text: 'Palangka Raya had essentially no rain in August or September. October\'s map will show whether the rains have started.' },
  { title: 'BC\'s waters', text: '+0.4 °C in September. In 1997–98 the same water stayed 0.6 to 1.05 °C above normal from November to March.' },
]

const log = [
  { date: '8 Oct 2026', text: 'Edition 1. OSTA data through 30 September 2026; news to 8 October.' },
]

const references = [
  { text: 'Hobday, A. J. et al. (2016). A hierarchical approach to defining marine heatwaves.', journal: 'Progress in Oceanography', where: '141, 227–238', doi: '10.1016/j.pocean.2015.12.014' },
  { text: 'Hobday, A. J. et al. (2018). Categorizing and naming marine heatwaves.', journal: 'Oceanography', where: '31(2), 162–173', doi: '10.5670/oceanog.2018.205' },
  { text: 'Cole, J. E. et al. (2026). Recent strengthening of eastern Pacific ENSO in the last millennium paleorecord.', journal: 'Science', where: '394, 192–196', doi: '10.1126/science.ady2660' },
]
</script>
