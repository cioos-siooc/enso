<template>
  <div>
    <StoryScroll :steps="steps" :references="REFERENCES">
      <template #race>
        <div class="mb-2 flex flex-wrap gap-x-4 gap-y-1 font-data text-[0.68rem]">
          <span v-for="(k, n) in RACE_KEY" :key="k" class="flex items-center gap-1.5" :style="{ color: RACE_COLORS[n] }">
            <i class="inline-block h-0.75 w-4" :style="{ background: RACE_COLORS[n] }" />{{ k }}
          </span>
        </div>
        <StoryRace
          :series="data.race"
          :colors="RACE_COLORS"
          :thresholds="[{ value: 0.5, label: 'El Niño +0.5' }, { value: 2, label: 'very strong +2.0' }]"
          :width="640"
          :height="300"
          label="Monthly Niño 3.4 anomaly for three El Niño events, from January of each event's first year. 2026 runs above both 1997 and 2015."
        />
      </template>

      <template #outro>
        <ul class="grid w-full max-w-3xl gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 text-left sm:grid-cols-2">
          <li v-for="w in WATCH" :key="w.title" class="flex flex-col gap-1 bg-[#0f1219]/90 p-4 backdrop-blur-md">
            <strong class="font-display text-base font-bold text-white [font-stretch:110%]">{{ w.title }}</strong>
            <p class="text-[0.95rem] leading-normal text-white/80">{{ w.text }}</p>
          </li>
        </ul>
        <UButton :to="viewLink(steps.at(-1)!.view)" target="_blank" label="Open OSTA" trailing-icon="i-mdi-open-in-new" size="lg" class="mt-6 font-sans" />
        <div class="mt-10 flex max-w-xl flex-col gap-3 rounded-2xl border border-white/10 bg-[#0f1219]/90 p-6 text-left font-data text-[0.7rem] leading-relaxed text-white/70 backdrop-blur-md">
          <h2 class="font-display text-base font-bold text-white">Update log</h2>
          <ol class="flex flex-col gap-1">
            <li v-for="entry in LOG" :key="entry.date" class="grid gap-x-3 sm:grid-cols-[7.5rem_minmax(0,1fr)]">
              <span class="text-white/50">{{ entry.date }}</span><span>{{ entry.text }}</span>
            </li>
          </ol>
          <h2 class="mt-3 font-display text-base font-bold text-white">Data and credits</h2>
          <p>
            Maps: NOAA Coral Reef Watch CoralTemp v3.1 (anomaly against a 1991–2020 daily climatology) and Marine Heatwave v1.0.1 (against NOAA's 1985–2012 90th percentile); NOAA CPC Global Unified gauge-based temperature and precipitation on land, against 1991–2020 normals computed in OSTA. Basemap © Mapbox © OpenStreetMap.
          </p>
          <p>
            Every number on the map cards was read from NOAA's data through OSTA on {{ EDITION.checked }}, for the last complete month. A record means a record since January 1, 1985, where NOAA's satellite data begin. News is summarised from the articles linked on each card, quotes as they appear there; records claimed in the news are those outlets' and their sources', on their own datasets.
          </p>
        </div>
      </template>
    </StoryScroll>
  </div>
</template>

<script setup lang="ts">
import data from '~/data/stories/el-nino-2026.json'
import { STORY_BASE, viewLink, type StoryReference, type StoryStep } from '~/utils/story'

/**
 * The 2026 El Nino, followed month by month over the live map
 * (components/story/Scroll.vue). Updated at the start of each month with the
 * last closed month of NOAA data and that month's news; the runbook is
 * stories/el-nino-2026/UPDATE.md at the repo root.
 *
 * `data` is written by that directory's measure.py. The readouts, the first
 * scrub and the race chart read it directly; the prose, `EDITION`, `WATCH` and
 * `LOG` are edited by hand from the same file.
 */
useSeoMeta({
  title: 'El Niño 2026, month by month · OSTA',
  description: 'The record 2026 El Niño followed over the live map, from Peru to British Columbia, with the news from the places it reaches. Updated monthly.',
})

const EDITION = {
  number: 1,
  month: 'September 2026',
  through: 'September 30, 2026',
  checked: 'October 8, 2026',
  next: 'early November',
  nextMonth: 'October',
}

/** The edition's month as a monthly bucket: the latest month in `data`. */
const months2026 = data.nino.nino34.months_2026 as Array<[string, number]>
const MONTH = `${months2026.at(-1)![0]}-01`
const DAY = data.edition.through

const WARM = '#f4a582'
const HOT = '#ff8000'
const IMPACT = '#e2e8f0'

/** 1997 grey, 2015 cool, 2026 in the accent; follows data.race's order. */
const RACE_COLORS = ['#a3a3a3', '#79b5c8', '#ef6a3a']
const RACE_KEY = ['1997–98, peak +2.42 in November', '2015–16, peak +2.81 in November', '2026–27']

/** 1st, 2nd, 3rd, 16th, 21st. */
function ordinal(n: number): string {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${tail}`
}

const P = data.points
const L = data.land
const R = data.regions

const REFERENCES: Record<string, StoryReference> = {
  cpc: {
    short: 'NOAA Climate Prediction Center, October 8, 2026',
    full: 'NOAA Climate Prediction Center. ENSO Diagnostic Discussion, October 8, 2026.',
    url: 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml',
  },
  wmo: {
    short: 'WMO, September 3, 2026',
    full: 'World Meteorological Organization. September 3, 2026. El Niño set to become very strong, raising risks of extreme weather into 2027.',
    url: 'https://wmo.int/news/media-centre/el-nino-set-become-very-strong-raising-risks-of-extreme-weather-2027',
  },
  icn: {
    short: 'Inside Climate News, September 29, 2026',
    full: 'Inside Climate News. September 29, 2026. Incoming El Niño is so extreme it doesn\'t have a scientific name.',
    url: 'https://insideclimatenews.org/news/29092026/record-breaking-el-nino-grows-in-pacific/',
  },
  scienceNews: {
    short: 'Science News, September 24, 2026',
    full: 'Science News. September 24, 2026. This year\'s El Niño just broke a record months before it\'s expected to peak.',
    url: 'https://www.sciencenews.org/article/record-breaking-el-nino-temperatures',
  },
  cole2026: {
    short: 'Cole et al. 2026, Science',
    full: 'Cole, J.E. et al. 2026. Recent strengthening of eastern Pacific ENSO in the last millennium paleorecord. Science 394: 192–196.',
    url: 'https://doi.org/10.1126/science.ady2660',
  },
  hobday2016: {
    short: 'Hobday et al. 2016',
    full: 'Hobday, A.J. et al. 2016. A hierarchical approach to defining marine heatwaves. Progress in Oceanography 141: 227–238.',
    url: 'https://doi.org/10.1016/j.pocean.2015.12.014',
  },
  hobday2018: {
    short: 'Hobday et al. 2018',
    full: 'Hobday, A.J. et al. 2018. Categorizing and naming marine heatwaves. Oceanography 31(2): 162–173.',
    url: 'https://doi.org/10.5670/oceanog.2018.205',
  },
  grist: {
    short: 'Grist, July 8, 2026',
    full: 'Grist. July 8, 2026. El Niño is here, and it\'s already scrambling fisheries throughout the Pacific.',
    url: 'https://grist.org/economics/el-nino-scrambling-fisheries-throughout-the-pacific/',
  },
  watchers: {
    short: 'The Watchers, July 3, 2026',
    full: 'The Watchers. July 3, 2026. Peru declares state of emergency ahead of 2026–2027 El Niño rains.',
    url: 'https://watchers.news/2026/07/03/peru-declares-state-of-emergency-ahead-of-2026-2027-el-nino-rains/',
  },
  cdf: {
    short: 'Charles Darwin Foundation, September 4, 2026',
    full: 'Charles Darwin Foundation. September 4, 2026. El Niño 2026 in Galápagos.',
    url: 'https://www.darwinfoundation.org/en/news/all-news-stories/el-nino-2026-in-galapagos/',
  },
  abcBirds: {
    short: 'American Bird Conservancy, August 6, 2026',
    full: 'American Bird Conservancy. August 6, 2026. Pacific seabird die-offs demonstrate the need for fishery action.',
    url: 'https://abcbirds.org/news/pacific-seabird-dieoff-2026/',
  },
  elComercio: {
    short: 'El Comercio, October 3, 2026 (Spanish)',
    full: 'El Comercio. October 3, 2026. El fenómeno de El Niño deja ríos desbordados en Esmeraldas y Pastaza.',
    url: 'https://www.elcomercio.com/actualidad/ecuador/fenomeno-nino-inundaciones-esmeraldas/',
  },
  ap: {
    short: 'Associated Press, July 1, 2026',
    full: 'Associated Press, via the Press Democrat. July 1, 2026. A marine heat wave caused seabird deaths off California. El Niño could worsen the die-off.',
    url: 'https://www.pressdemocrat.com/2026/07/01/record-ocean-heat-and-el-nino-are-leading-to-mass-california-seabird-die-offs/',
  },
  noaaFisheries: {
    short: 'NOAA Fisheries, June 12, 2026',
    full: 'NOAA Fisheries. June 12, 2026. 7 ways El Niño and large marine heatwave could affect West Coast marine species.',
    url: 'https://www.fisheries.noaa.gov/feature-story/7-ways-el-nino-and-large-marine-heatwave-could-affect-west-coast-marine-species',
  },
  dfo2016: {
    short: 'DFO, State of the Pacific Ocean 2016',
    full: 'Chandler, P.C., King, S.A. and Boldt, J. (eds.) 2017. State of the physical, biological and selected fishery resources of Pacific Canadian marine ecosystems in 2016. Can. Tech. Rep. Fish. Aquat. Sci. 3225.',
    url: 'https://waves-vagues.dfo-mpo.gc.ca/Library/40617944.pdf',
  },
  watershed: {
    short: 'Watershed Watch Salmon Society, March 25, 2026',
    full: 'Watershed Watch Salmon Society. March 25, 2026. 2026 salmon outlook, part 1: environmental conditions.',
    url: 'https://watershedwatch.ca/stories/2026-salmon-outlook-part-1-environmental-conditions/',
  },
  climateData: {
    short: 'ClimateData.ca, August 21, 2026',
    full: 'ClimateData.ca, Canadian Centre for Climate Services. August 21, 2026. What the developing exceptional El Niño means for Canada in 2026–27.',
    url: 'https://climatedata.ca/news/what-the-developing-exceptional-el-nino-means-for-canada-in-2026-27/',
  },
  abcNews: {
    short: 'ABC News (Australia), September 7, 2026',
    full: 'ABC News (Australia). September 7, 2026. Indonesian wildfires spurred by super El Niño choke South-East Asia.',
    url: 'https://www.abc.net.au/news/2026-09-07/indonesia-wildfires-haze-poor-air-quality-smog-drought-el-nino/107122922',
  },
  nasa: {
    short: 'NASA Earth Observatory, September 3, 2026',
    full: 'NASA Earth Observatory. September 3, 2026. Peatland fires darken skies in Indonesia. Story by Adam Voiland.',
    url: 'https://science.nasa.gov/missions/aqua/peatland-fires-darken-skies-in-indonesia/',
  },
  carbonBrief: {
    short: 'Carbon Brief, September 15, 2026',
    full: 'Carbon Brief. September 15, 2026. Temperature "overshoot", world\'s warmest month and the catastrophic 1877–78 El Niño.',
    url: 'https://www.carbonbrief.org/cited-15-september-2026-temperature-overshoot-worlds-warmest-month-catastrophic-1877-78-el-nino',
  },
}

const steps: StoryStep[] = [
  {
    id: 'intro',
    align: 'center',
    eyebrow: `Ongoing · edition ${EDITION.number} · NOAA data through ${EDITION.through}`,
    title: 'El Niño 2026, month by month',
    body: [
      'The central and eastern equatorial Pacific is warmer than at any time since NOAA\'s satellite record began in 1985.',
      'This page follows the 2026 El Niño as it unfolds, from the coast of Peru to British Columbia. Each month it adds the newest month of NOAA\'s data and the news from the places it reaches.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'nino34' },
    camera: { center: [-118, 4], zoom: 1.9 },
  },
  {
    id: 'growth',
    eyebrow: `January – ${EDITION.month}`,
    title: 'From La Niña to a record',
    body: [
      'Keep scrolling to run the clock. Each frame is a month of sea surface temperature against the 1991–2020 normal: red is warmer, blue cooler.',
      'Niño 3.4, the stretch of equator NOAA watches, was still slightly cool in January, the tail of last winter\'s La Niña. It crossed the +0.5 °C El Niño threshold in April and gained about half a degree a month from there.',
    ],
    quote: { text: 'The transition has been very rapid, from a La Niña last winter to a very strong El Niño in less than a year.', cite: 'Nathaniel Johnson, NOAA Geophysical Fluid Dynamics Laboratory, to Science News' },
    refs: ['scienceNews'],
    readout: { value: months2026.at(-1)![1], digits: 2, unit: ' °C', signed: true, label: 'Niño 3.4 that month', color: WARM },
    scrub: { from: '2026-01-01', to: MONTH, values: months2026.map(([, v]) => v) },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2026-01-01', region: 'nino34' },
    camera: { center: [-128, -2], zoom: 2.4 },
  },
  {
    id: 'race',
    wide: true,
    eyebrow: `${EDITION.month} · Niño 3.4`,
    title: 'Warmer than 1997 and 2015, two months earlier',
    readout: { value: data.nino.nino34.value, digits: 2, unit: ' °C', signed: true, label: 'Niño 3.4\'s warmest month since 1985', color: WARM },
    body: [
      'The two strongest El Niños since 1985, 1997–98 and 2015–16, both peaked in November, at +2.42 and +2.81 °C. This one passed 1997\'s peak in August and 2015\'s in September. Day by day, Niño 3.4 broke its record (+2.99 °C on November 19, 2015) on September 13 and reached +3.27 °C on September 30.',
    ],
    figure: 'race',
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'nino34' },
    camera: { center: [-150, 2], zoom: 2.7, pitch: 30 },
  },
  {
    id: 'strength',
    align: 'right',
    eyebrow: 'How strong?',
    title: 'Off the end of NOAA\'s scale',
    body: [
      'These are not NOAA\'s official numbers. NOAA\'s index measures Niño 3.4 against the tropical ocean around it, which is also unusually warm this year, so it reads lower.',
      'Even so, NOAA gives October–December an 83% chance of beating every event since 1950, and the WMO puts the chance that El Niño lasts through February 2027 at nearly 100%. Talk of a "millennium" comes from a coral study of past El Niños, not this one.',
    ],
    quote: { text: 'We don\'t have a categorization for this.', cite: 'Daniel Swain, climate scientist, to Inside Climate News' },
    refs: ['cpc', 'wmo', 'icn', 'cole2026'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'nino34' },
    camera: { center: [-140, 0], zoom: 2.2 },
  },
  {
    id: 'peru',
    eyebrow: `${EDITION.month} · Paita, Peru`,
    title: '"Beyond extreme" off northern Peru',
    readout: { value: P.paita.category_days['5'], digits: 0, unit: ' days', label: `of ${EDITION.month} in NOAA's top heatwave class, "Beyond extreme"`, color: HOT },
    body: [
      'El Niño is strongest where the warm water piles up against South America. In September the sea off Paita averaged 7.1 °C above normal; its warmest September before was 1997, at +4.3 °C. Chimbote was +5.8 °C and Callao, Lima\'s port, +4.8 °C. All three are records for September.',
      'The map now shows NOAA\'s daily heatwave classes. Off Paita a heatwave began on May 14 and had run 140 days by the end of September. The longest there ran 370 days, from April 1997 to May 1998.',
    ],
    refs: ['hobday2016', 'hobday2018'],
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: DAY, point: { lat: -5.07, lon: -81.28 } },
    camera: { center: [-84, -7], zoom: 4.4, pitch: 45, bearing: 15 },
  },
  {
    id: 'anchoveta',
    align: 'right',
    eyebrow: 'July 2026 · Peru',
    title: 'The world\'s biggest fishery, out of reach',
    body: [
      'Peru suspended its anchoveta fishery, the largest single-species fishery in the world. Boats with sonar found the fish more than 100 m down, beyond their nets, and prices for jack mackerel and corvina reportedly doubled.',
      'The government declared a 60-day emergency in 796 districts for "the imminent threat of intense rainfall".',
    ],
    quote: { text: 'Our vulnerability is increasing.', cite: 'Juan Carlos Sueiro, Oceana Peru, to Grist' },
    refs: ['grist', 'watchers'],
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: DAY, point: { lat: -12.07, lon: -77.28 } },
    camera: { center: [-80, -11], zoom: 4.6, pitch: 40, bearing: -10 },
  },
  {
    id: 'piura',
    eyebrow: `${EDITION.month} · Piura, Peru`,
    title: 'Warm nights on land',
    readout: { value: L.piura.land_tmin_anom, digits: 1, unit: ' °C', signed: true, label: 'overnight lows at Piura against normal', color: WARM },
    body: [
      'The land overlay is NOAA\'s gauge-based analysis. September nights at Piura were 5.2 °C warmer than normal, and days 3.7 °C warmer.',
      'Peru\'s coast is in its dry season, so its rainfall cannot yet be read as a share of normal.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, point: { lat: -5.19, lon: -80.63 }, landLayer: 'tmin', landMode: 'anomaly' },
    camera: { center: [-79.5, -6], zoom: 5.2, pitch: 35 },
  },
  {
    id: 'galapagos-1997',
    align: 'right',
    eyebrow: 'September 1997 · Isabela, Galápagos',
    title: 'The Galápagos, last time…',
    readout: { value: P.isabela.next[0]![1] as number, digits: 2, unit: ' °C', signed: true, label: 'west of Isabela, September 1997', color: WARM },
    body: ['West of Isabela, cold water normally wells up around the Galápagos. This is September 1997, as the 1997–98 El Niño built toward its peak.'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '1997-09-01', point: { lat: -0.52, lon: -91.72 } },
    camera: { center: [-89, -1], zoom: 4.2, pitch: 40, bearing: -10 },
  },
  {
    id: 'galapagos-2026',
    align: 'right',
    eyebrow: EDITION.month,
    title: '…and now',
    readout: { value: P.isabela.anom, digits: 2, unit: ' °C', signed: true, label: 'west of Isabela: more than a degree past 1997', color: WARM },
    body: [
      'The same water has been in a heatwave since May 18, Severe or Extreme for the whole of September. On Ecuador\'s mainland coast, the sea off Santa Elena was 4.7 °C above normal, well clear of its previous September high (+3.0 °C in 2023).',
      'The link opens both Septembers side by side, in OSTA\'s swipe compare.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, compareDate: '1997-09-01', point: { lat: -0.52, lon: -91.72 } },
    camera: { center: [-89, -1], zoom: 4.2, pitch: 40, bearing: -10 },
  },
  {
    id: 'galapagos-life',
    eyebrow: 'June – October 2026 · Ecuador and the Galápagos',
    title: 'Hungry iguanas, dying seabirds',
    readout: { value: 968, digits: 0, unit: '', label: 'dead seabirds counted on Ecuador\'s coast in July, against a few dozen a month before', color: IMPACT },
    body: [
      'Marine iguanas lose weight as the algae they graze die back, and seabirds may abandon their nests. Sooty shearwaters, boobies and critically endangered waved albatrosses were among the dead on Ecuador\'s coast.',
      'At the end of September nine rivers burst their banks in Esmeraldas and Pastaza, affecting about 800 families. That rain came too late for September\'s map.',
    ],
    quote: { text: 'Corals will probably be among the biggest losers.', cite: 'María José Barragán, Charles Darwin Foundation' },
    refs: ['cdf', 'abcBirds', 'elComercio'],
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: DAY, point: { lat: -2.22, lon: -81.08 } },
    camera: { center: [-85.5, -1.5], zoom: 4.3, pitch: 35 },
  },
  {
    id: 'north',
    align: 'center',
    eyebrow: 'Up the coast',
    title: 'What it means for BC',
    body: ['California\'s coast is already feeling the heat. In BC, El Niño\'s mark has been a warm winter, on land and at sea.'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'pacific_bioregions' },
    camera: { center: [-135, 40], zoom: 2.6 },
  },
  {
    id: 'california',
    eyebrow: `${EDITION.month} · San Diego`,
    title: 'California\'s coast, already hot',
    photo: {
      src: '/story-assets/el-nino-2026/img/sea-lion-pup.webp',
      alt: 'A thin California sea lion pup, its ribs showing, resting on wet rocks by a beach.',
      credit: 'An underweight California sea lion pup, 2015. Photo: NOAA Fisheries (public domain)',
      href: 'https://www.fisheries.noaa.gov/feature-story/7-ways-el-nino-and-large-marine-heatwave-could-affect-west-coast-marine-species',
    },
    readout: { value: P.san_diego.anom, digits: 1, unit: ' °C', signed: true, label: `off San Diego, ${EDITION.month}`, color: WARM },
    body: [
      'The water off San Diego has been above normal in every month of 2026 and back in a heatwave since September 9. In July, AP reported pelicans, murres and cormorants starving along the coast, and NOAA Fisheries warns of hungry sea lion pups, as in 2015.',
    ],
    quote: { text: 'We\'ve been seeing cormorants walk to shore and then just die within the hour.', cite: 'Tammy Russell, Scripps Institution of Oceanography, to AP' },
    refs: ['ap', 'noaaFisheries'],
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: DAY, point: { lat: 32.72, lon: -117.43 } },
    camera: { center: [-120.5, 33], zoom: 4.6, pitch: 40, bearing: -15 },
  },
  {
    id: 'bc-now',
    align: 'right',
    eyebrow: `${EDITION.month} · British Columbia`,
    title: 'BC\'s waters are not there yet',
    readout: { value: R.pacific_bioregions.anom.value, digits: 2, unit: ' °C', signed: true, label: `DFO's Pacific bioregions, ${ordinal(R.pacific_bioregions.anom.rank)} warmest of ${R.pacific_bioregions.anom.of} Septembers`, color: WARM },
    body: [
      'Across DFO\'s Pacific bioregions, September was only a little warmer than normal. In the last two big El Niños, this water warmed through the winter.',
      'The link opens Niño 3.4 and BC\'s waters on one chart, to watch whether it happens again.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'pacific_bioregions', region2: 'nino34' },
    camera: { center: [-131, 51.5], zoom: 4.3, pitch: 35, bearing: -10 },
  },
  {
    id: 'bc-1997',
    eyebrow: 'November 1997 – March 1998',
    title: 'Last time: a warm winter offshore',
    body: [
      'Scroll through the 1997–98 winter. BC\'s waters warmed from +0.6 °C in November to +1.05 °C in March. February and March 1998 are still the third-warmest of those months since 1985.',
    ],
    readout: { value: 1.05, digits: 2, unit: ' °C', signed: true, label: 'BC\'s waters that month', color: WARM },
    scrub: { from: '1997-11-01', to: '1998-03-01', values: [0.6, 0.7, 0.66, 0.85, 1.05] },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '1997-11-01', region: 'pacific_bioregions' },
    camera: { center: [-133, 50], zoom: 3.8, pitch: 30 },
  },
  {
    id: 'bc-2016',
    align: 'right',
    eyebrow: 'Winter 2015–16 · British Columbia',
    title: 'Mild nights, a high sea',
    body: [
      'DFO\'s review of 2016 found the El Niño winter typical for BC: very warm in January and February, with overnight lows even further above normal than daytime highs. In February, highs ran more than 5 °C above normal.',
      'Sea level at Tofino, Victoria and Prince Rupert sat above its century-long trend, raised by El Niño. Off Vancouver Island, surveys caught southern copepods rarely seen there except in large El Niño events.',
    ],
    refs: ['dfo2016'],
    places: [
      { name: 'Prince Rupert', coords: [-130.32, 54.32] },
      { name: 'Tofino', coords: [-125.91, 49.15] },
      { name: 'Victoria', coords: [-123.37, 48.43] },
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2016-02-01', region: 'pacific_bioregions', landLayer: 'tmin', landMode: 'anomaly' },
    camera: { center: [-125, 51.5], zoom: 4.3, pitch: 30 },
  },
  {
    id: 'salmon',
    eyebrow: '2016 and 2026 · BC salmon',
    title: 'Hard years for young salmon',
    photo: {
      src: '/story-assets/el-nino-2026/img/skinny-coho.webp',
      alt: 'Three juvenile coho salmon on a measuring board; the two lower fish are visibly thinner.',
      credit: 'Juvenile coho from offshore surveys in the Blob years; the two at bottom are skinny. Photo: NOAA Fisheries (public domain)',
      href: 'https://www.fisheries.noaa.gov/feature-story/7-ways-el-nino-and-large-marine-heatwave-could-affect-west-coast-marine-species',
    },
    body: [
      'DFO judged that a warm ocean in 2015, followed by El Niño in spring 2016, left poor conditions for juvenile salmon going to sea from BC\'s central and south coasts, and expected fewer of them to return in 2017–18.',
      'Watershed Watch\'s 2026 outlook makes the same point: El Niño years tend to bring warmer, less productive conditions for BC salmon.',
    ],
    refs: ['dfo2016', 'watershed', 'noaaFisheries'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'pacific_bioregions' },
    camera: { center: [-128, 50], zoom: 5, pitch: 45, bearing: 10 },
  },
  {
    id: 'bc-winter',
    align: 'right',
    eyebrow: 'Winter 2026–27 · Canada',
    title: 'A winter forecast off the charts',
    body: [
      'Canada\'s climate services expect a warmer-than-normal winter in BC, and a drier one over the Rockies and the Okanagan. In past very strong El Niños, warm, dry weather lasted through the spring in BC, the coast included.',
      'Kamloops, pinned on the map, is one place to watch: its September nights were near normal.',
    ],
    quote: { text: '…some ensemble members including from ECCC approaching or exceeding 4°C, which would be unprecedented in the modern record by a substantial margin.', cite: 'Bill Merryfield, Environment and Climate Change Canada, on forecasts for Niño 3.4' },
    refs: ['climateData'],
    places: [
      { name: 'Kamloops', coords: [-120.33, 50.67], beside: true },
      { name: 'Okanagan', coords: [-119.5, 49.6], dot: false },
      { name: 'Rockies', coords: [-116.3, 51.6], dot: false },
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, point: { lat: 50.67, lon: -120.33 }, landLayer: 'tmin', landMode: 'anomaly' },
    camera: { center: [-121.5, 51], zoom: 4.6, pitch: 35 },
  },
  {
    id: 'indonesia',
    eyebrow: `${EDITION.month} · Kalimantan and Sumatra`,
    title: 'Across the Pacific, the rain stopped',
    readout: { value: L.palangka_raya.land_precip_anom, digits: 1, unit: ' mm', signed: true, label: 'a day: rain at Palangka Raya against normal', color: '#bf812d' },
    body: [
      'El Niño moves the tropical Pacific\'s rain east with the warm water, and the western side dries out. On land the map now shows rain against normal: brown is drier.',
      'NOAA\'s gauges had essentially no rain at Palangka Raya in August or September, and 0.1 mm a day at Palembang. Afternoons in both were 2 °C warmer than normal.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, point: { lat: -2.21, lon: 113.92 }, landLayer: 'precip', landMode: 'difference' },
    camera: { center: [110, -2], zoom: 4.2, pitch: 30 },
  },
  {
    id: 'fires',
    align: 'right',
    eyebrow: 'September 2026 · Borneo',
    title: 'Fire and smoke',
    photo: {
      src: '/story-assets/el-nino-2026/img/borneo-smoke.webp',
      alt: 'Satellite image of Borneo half hidden under grey smoke streaming from fires, with the Java Sea to the south.',
      credit: 'Smoke over Borneo, September 1, 2026. NASA Earth Observatory image by Lauren Dauphin, MODIS data from NASA EOSDIS LANCE and GIBS/Worldview',
      href: 'https://science.nasa.gov/missions/aqua/peatland-fires-darken-skies-in-indonesia/',
    },
    readout: { value: 200000, digits: 0, unit: ' ha', label: 'burned in Indonesia by early September, at least', color: IMPACT },
    body: [
      'Drained peat burns, slowly and underground. The air quality index passed 900 in Pontianak, and smoke reached the Philippines.',
    ],
    quote: { text: 'Indeed worse than in 2015.', cite: 'Andri Susanto, firefighter, to ABC News' },
    refs: ['abcNews', 'nasa'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, point: { lat: -2.21, lon: 113.92 }, landLayer: 'tmax', landMode: 'anomaly' },
    camera: { center: [112, -0.5], zoom: 5, pitch: 40 },
  },
  {
    id: 'global',
    eyebrow: `${EDITION.month} · The whole ocean`,
    title: 'A record September for the world\'s oceans',
    readout: { value: R.global.anom.value, digits: 2, unit: ' °C', signed: true, label: 'the global ocean, warmest September since 1985', color: WARM },
    body: [
      'Averaged over every ocean, September was the warmest since 1985; the Pacific alone was +0.85 °C. Copernicus found that August 2026 tied July 2023 as the planet\'s warmest month on record.',
    ],
    refs: ['carbonBrief'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'global' },
    camera: { center: [-150, 8], zoom: 1.5 },
  },
  {
    id: 'extent',
    align: 'right',
    eyebrow: `${EDITION.month} · The whole ocean`,
    title: 'Nearly half the ocean in a heatwave',
    readout: { value: R.global.mhw_extent.value, digits: 1, unit: '%', label: 'of the global ocean in a heatwave on an average September day; 40.4% in 2023, the previous high', color: HOT },
    body: [
      'One caution: NOAA\'s heatwave threshold is fixed to 1985–2012, so as the ocean warms, more of it crosses the line every year. Part of any new record is the trend, and OSTA prints the trend beside the number.',
    ],
    view: { ...STORY_BASE, variable: 'mhw', period: 'monthly', date: MONTH, region: 'global' },
    camera: { center: [-60, 8], zoom: 1.5 },
  },
  {
    id: 'outro',
    align: 'center',
    outro: true,
    eyebrow: `Next edition ${EDITION.next}`,
    title: `What to watch in ${EDITION.nextMonth}`,
    body: [],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: MONTH, region: 'nino34' },
    camera: { center: [-125, 5], zoom: 1.7 },
  },
]

const WATCH = [
  { title: 'Does Niño 3.4 keep climbing?', text: 'The first three days of October averaged +3.30 °C. NOAA gives October–December an 83% chance of beating every event since 1950.' },
  { title: 'Paita\'s heatwave: day 140', text: 'The 1997–98 run off Paita lasted 370 days. This one began on May 14.' },
  { title: 'Rain on Ecuador\'s and Peru\'s coast', text: 'The Esmeraldas floods came at the end of September. October\'s land map will show how widespread the rain was.' },
  { title: 'Peru\'s anchovy fishery', text: 'Whether a second fishing season opens this year, after the first was cut short.' },
  { title: 'BC\'s waters', text: '+0.4 °C in September. In 1997–98 the same water stayed 0.6 to 1.05 °C above normal from November to March.' },
  { title: 'Indonesia\'s dry season', text: 'Palangka Raya had essentially no rain in August or September. October\'s map will show whether the rains have started.' },
]

const LOG = [
  { date: 'October 12, 2026', text: 'Retold over the live map; same edition, same numbers. BC chapter extended from DFO\'s State of the Pacific Ocean 2016.' },
  { date: 'October 8, 2026', text: 'Edition 1. NOAA data through September 30, 2026; news to October 8.' },
]
</script>
