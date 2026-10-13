<template>
  <div>
    <StoryScroll :steps="steps" :references="REFERENCES">
      <template #outro>
        <UButton :to="viewLink(steps.at(-1)!.view)" target="_blank" label="Open OSTA" trailing-icon="i-mdi-open-in-new" size="lg" class="mt-2 font-sans" />
        <div class="mt-10 flex max-w-xl flex-col gap-3 rounded-2xl border border-white/10 bg-[#0f1219]/90 p-6 text-left font-data text-[0.7rem] leading-relaxed text-white/70 backdrop-blur-md">
          <h2 class="font-display text-base font-bold text-white">Data and credits</h2>
          <p>
            Maps: NOAA Coral Reef Watch CoralTemp v3.1 (anomaly against a 1991–2020 daily climatology) and Marine Heatwave v1.0.1 (against NOAA's 1985–2012 90th percentile); NOAA CPC Global Unified on land. Basemap © Mapbox © OpenStreetMap. Map numbers were read from NOAA's data in OSTA on October 8, 2026, with ocean data through October 3, 2026.
          </p>
          <p>Every impact links to its source on its own card, and every card opens its view in OSTA.</p>
          <p>
            Retold from
            <a href="https://cioospacific.ca/ressource/a-fever-on-canadas-pacific-coast/" target="_blank" rel="noopener" class="text-white/90 underline underline-offset-2">A Fever on Canada's Pacific Coast</a>,
            created by Tyee Bridge, Jonathan Kellogg, Mat Brown, Mercedes Minck, Jeremy Latham and Jorin Weatherston of the Hakai Institute, for CIOOS Pacific.
          </p>
        </div>
      </template>
    </StoryScroll>
  </div>
</template>

<script setup lang="ts">
import { STORY_BASE, viewLink, type StoryReference, type StoryStep } from '~/utils/story'

/**
 * "A Fever on Canada's Pacific Coast", the CIOOS Pacific story about the
 * 2013-16 marine heatwave, told over the live map (components/story/Scroll.vue).
 *
 * Map numbers were read from the API on October 8, 2026. Impacts lead with
 * Canadian sources, DFO's State of the Pacific Ocean reports first, and each
 * is linked on its own card.
 */
useSeoMeta({
  title: 'A Fever on Canada\'s Pacific Coast · OSTA',
  description: 'The 2013–16 marine heatwave known as the Blob, and what it did to Canada\'s Pacific coast, told over the live map.',
})

const WARM = '#f4a582'

/** DFO's Line P, its major stations P1, P4, P12, P16, P20 and P26 (Station P). */
const LINE_P: [number, number][] = [
  [-125.5, 48.575], [-126.667, 48.65], [-130.667, 48.97], [-134.667, 49.283], [-138.667, 49.567], [-145, 50],
]
const HOT = '#ff8000'
const IMPACT = '#e2e8f0'

const REFERENCES: Record<string, StoryReference> = {
  original: {
    short: 'A Fever on Canada\'s Pacific Coast (Hakai Institute for CIOOS Pacific)',
    full: 'A Fever on Canada\'s Pacific Coast. Tyee Bridge, Jonathan Kellogg, Mat Brown, Mercedes Minck, Jeremy Latham and Jorin Weatherston, Hakai Institute, for CIOOS Pacific.',
    url: 'https://cioospacific.ca/ressource/a-fever-on-canadas-pacific-coast/',
  },
  dfo2014: {
    short: 'DFO, State of the Pacific Ocean 2014',
    full: 'Chandler, P.C., King, S.A. and Perry, R.I. (eds.) 2015. State of the physical, biological and selected fishery resources of Pacific Canadian marine ecosystems in 2014. Can. Tech. Rep. Fish. Aquat. Sci. 3131.',
    url: 'https://waves-vagues.dfo-mpo.gc.ca/Library/358018.pdf',
  },
  dfo2015: {
    short: 'DFO, State of the Pacific Ocean 2015',
    full: 'Chandler, P.C., King, S.A. and Perry, R.I. (eds.) 2016. State of the physical, biological and selected fishery resources of Pacific Canadian marine ecosystems in 2015. Can. Tech. Rep. Fish. Aquat. Sci. 3179.',
    url: 'https://waves-vagues.dfo-mpo.gc.ca/Library/365564.pdf',
  },
  dfo2016: {
    short: 'DFO, State of the Pacific Ocean 2016',
    full: 'Chandler, P.C., King, S.A. and Boldt, J. (eds.) 2017. State of the physical, biological and selected fishery resources of Pacific Canadian marine ecosystems in 2016. Can. Tech. Rep. Fish. Aquat. Sci. 3225.',
    url: 'https://waves-vagues.dfo-mpo.gc.ca/Library/40617944.pdf',
  },
  dfo2017: {
    short: 'DFO, State of the Pacific Ocean 2017',
    full: 'Chandler, P.C., King, S.A. and Boldt, J. (eds.) 2018. State of the physical, biological and selected fishery resources of Pacific Canadian marine ecosystems in 2017. Can. Tech. Rep. Fish. Aquat. Sci. 3266.',
    url: 'https://waves-vagues.dfo-mpo.gc.ca/library-bibliotheque/40717914.pdf',
  },
  piatt2020: {
    short: 'Piatt et al. 2020',
    full: 'Piatt, J.F., Parrish, J.K., Renner, H.M. et al. 2020. Extreme mortality and reproductive failure of common murres resulting from the northeast Pacific marine heatwave of 2014–2016. PLOS ONE 15(1): e0226087.',
    url: 'https://doi.org/10.1371/journal.pone.0226087',
  },
  ap2026: {
    short: 'AP, July 2026',
    full: 'Watson, J. 2026. A marine heat wave caused seabird deaths off California. El Nino could worsen the die-off. Associated Press, July 1, 2026.',
    url: 'https://www.kpbs.org/news/environment/2026/07/01/a-marine-heat-wave-caused-seabird-deaths-off-california-el-nino-could-worsen-the-die-off',
  },
  ctv2026: {
    short: 'CTV News, September 2026',
    full: 'Dying sea birds washing ashore in Bay Area due to effects of warming ocean. CNN, via CTV News, September 17, 2026.',
    url: 'https://www.ctvnews.ca/climate-and-environment/article/dying-sea-birds-washing-ashore-in-bay-area-due-to-effects-of-warming-ocean/',
  },
  noaaHab: {
    short: 'NOAA National Ocean Service 2016',
    full: 'NOAA National Ocean Service. 2016. West Coast harmful algal bloom.',
    url: 'https://oceanservice.noaa.gov/news/sep15/westcoast-habs.html',
  },
  barbeaux2020: {
    short: 'Barbeaux et al. 2020',
    full: 'Barbeaux, S.J., Holsman, K. and Zador, S. 2020. Marine heatwave stress test of ecosystem-based fisheries management in the Gulf of Alaska Pacific cod fishery. Frontiers in Marine Science 7: 703.',
    url: 'https://doi.org/10.3389/fmars.2020.00703',
  },
  alaskaPublic2019: {
    short: 'Alaska Public Media 2019',
    full: 'Alaska Public Media. December 6, 2019. Extremely low cod numbers linked to the marine heatwave lead feds to close the Gulf of Alaska fishery for the first time.',
    url: 'https://alaskapublic.org/news/2019-12-07/extremely-low-cod-numbers-linked-to-the-marine-heatwave-lead-feds-to-close-the-gulf-of-alaska-fishery-for-the-first-time',
  },
}

const steps: StoryStep[] = [
  {
    id: 'intro',
    align: 'center',
    eyebrow: 'CIOOS Pacific · Ocean Surface Temperature Atlas',
    title: 'A Fever on Canada\'s Pacific Coast',
    body: [
      'In September 2025 the northeast Pacific broke records set by the Blob, the marine heatwave that ran from late 2013 into 2016.',
      'The Blob showed what heat like this does to this coast: to plankton, seabirds and the fisheries that depend on them. This is what happened last time.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2013-09-01', region: 'ne_pacific' },
    camera: { center: [-152, 36], zoom: 1.9 },
  },
  {
    id: 'growth',
    eyebrow: 'September 2013 – December 2016',
    title: 'Three years, a month at a time',
    body: [
      'Keep scrolling to run the clock. Each frame is a month of NOAA\'s sea surface temperature against the 1991–2020 normal for that time of year: red is warmer, blue cooler.',
      'Watch the Gulf of Alaska first, then the coast.',
    ],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2013-09-01', region: 'ne_pacific' },
    camera: { center: [-145, 44], zoom: 2.5 },
    scrub: { from: '2013-09-01', to: '2016-12-01' },
  },
  {
    id: 'station-p',
    eyebrow: 'February 2014 · Station P, 50°N 145°W',
    title: 'A number nobody expected',
    body: ['A winter survey along Line P found the upper 100 metres more than 2.5 °C warmer than normal. At the surface, February averaged 8.25 °C against a normal of 6.03 °C: the warmest February there in 42 years.'],
    quote: { text: '…the single biggest climate anomaly I am aware of anywhere in modern history.', cite: 'Howard Freeland, March 2014' },
    refs: ['original'],
    readout: { value: 2.2, digits: 1, unit: ' °C', signed: true, label: 'surface anomaly at Station P', color: WARM },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2014-02-01', point: { lat: 50, lon: -145 } },
    camera: { center: [-147, 47], zoom: 3.7, pitch: 35, bearing: -10 },
    line: { coords: LINE_P, label: 'Line P' },
  },
  {
    id: 'blob',
    align: 'right',
    eyebrow: 'June 11, 2014 · Northeast Pacific',
    title: 'The Blob takes shape',
    body: [
      'A stubborn ridge of high pressure kept winter storms away, and the summer\'s heat stayed in the water. At its peak the Blob covered about nine million square kilometres, an area almost as large as Canada.',
      'The map now shows NOAA\'s marine heatwave categories.',
    ],
    refs: ['original'],
    readout: { value: 86.3, digits: 1, unit: '%', label: 'of the NE Pacific region in a marine heatwave', color: '#ffff80' },
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: '2014-06-11', region: 'ne_pacific' },
    camera: { center: [-140, 49], zoom: 2.9, pitch: 20 },
  },
  {
    id: 'oregon',
    eyebrow: 'Autumn 2014 · Off Newport, Oregon',
    title: 'Down the coast',
    body: ['By autumn the warmth reached all the way down the coast. The cell off Newport stayed in a heatwave from September 19, 2014, to May 1, 2015, peaking at Category 3, Severe.'],
    readout: { value: 225, digits: 0, unit: ' days', label: 'in a heatwave without a break', color: HOT },
    view: { ...STORY_BASE, variable: 'mhw', period: 'daily', date: '2014-12-24', point: { lat: 44.67, lon: -124.55 } },
    camera: { center: [-127.5, 43.5], zoom: 4.6, pitch: 50, bearing: -25 },
  },
  {
    id: 'june-2012',
    align: 'right',
    eyebrow: 'June 2012',
    title: 'Before…',
    body: ['June 2012 fell in one of the northeast Pacific\'s coolest years on record.'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2012-06-01', region: 'ne_pacific' },
    camera: { center: [-135, 45], zoom: 3, pitch: 45, bearing: 15 },
  },
  {
    id: 'june-2015',
    align: 'right',
    eyebrow: 'June 2015',
    title: '…and after',
    body: ['Three years later, warm water lined the coast from Alaska to California. Averaged over the NE Pacific region, it was the warmest June on record.'],
    readout: { value: 1.53, digits: 2, unit: ' °C', signed: true, label: 'NE Pacific region, June 2015', color: WARM },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-06-01', region: 'ne_pacific' },
    camera: { center: [-135, 45], zoom: 3, pitch: 45, bearing: 15 },
  },
  {
    id: 'bc',
    eyebrow: '2015 · British Columbia',
    title: 'It came to BC, and stayed',
    body: ['Offshore, heatwave extent peaked in 2014. In BC\'s waters the peak came a year later, and by April 1, 2016, 99.97% of BC\'s waters were in a marine heatwave.'],
    readout: { value: 73.5, digits: 1, unit: '%', label: 'of BC\'s waters in a heatwave on an average day of 2015', color: HOT },
    view: { ...STORY_BASE, variable: 'mhw', period: 'monthly', date: '2015-07-01', region: 'pacific_bioregions' },
    camera: { center: [-130, 51.5], zoom: 4.3, pitch: 40, bearing: -15 },
  },
  {
    id: 'land',
    align: 'right',
    eyebrow: 'February 2015 · Interior British Columbia',
    title: 'A mild winter on land',
    body: ['Warm water offshore and mild weather inland arrived together. BC\'s waters had their warmest February on record, and nights around Kamloops and Prince George ran well above normal.'],
    readout: { value: 4.1, digits: 1, unit: ' °C', signed: true, label: 'overnight lows near Kamloops', color: WARM },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-02-01', region: 'pacific_bioregions', landLayer: 'tmin', landMode: 'anomaly' },
    line: { coords: [[-120.33, 50.67]], label: 'Kamloops' },
    camera: { center: [-125, 51.5], zoom: 4.4, pitch: 30, bearing: 0 },
  },
  {
    id: 'impacts',
    align: 'center',
    eyebrow: '2014–2017',
    title: 'What the heat did',
    body: ['Warm water was only the start. Fisheries and Oceans Canada\'s scientists, and others along the coast, followed it through the food web.'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-06-01', region: 'pacific_bioregions' },
    camera: { center: [-134, 50], zoom: 3.4 },
  },
  {
    id: 'food-web',
    eyebrow: '2015 · West coast of Vancouver Island',
    title: 'Poorer food at the bottom of the chain',
    body: [
      'Surveys west of Vancouver Island caught more and more southern copepods, which are poor food for fish, and fewer of the sub-Arctic species usually found there.',
      'The warm surface layer also kept nutrients from mixing up from below through the winter of 2014–15.',
    ],
    refs: ['dfo2015'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-06-01', region: 'pacific_bioregions' },
    camera: { center: [-127.5, 48.8], zoom: 5.2, pitch: 45, bearing: -20 },
  },
  {
    id: 'seabirds',
    align: 'right',
    eyebrow: 'Winter 2014–15 · Triangle Island, BC',
    title: 'Seabirds starved',
    body: [
      'Cassin\'s auklets had a banner breeding season in 2014 on Triangle Island, off the northwest tip of Vancouver Island and the largest colony in the world. That fall and winter, young auklets died in huge numbers along the coast from California to BC.',
      'A year later it was the common murres: about 62,000 dead or dying birds washed ashore from California to Alaska, and the total may have approached a million.',
      'It is happening again. Off California, where the water has been in a marine heatwave for a year, starving pelicans, cormorants and murres have been washing ashore through 2026.',
    ],
    photo: {
      src: '/story-assets/blob/img/murres.webp',
      alt: 'Dozens of dead common murres, white bellies up, among driftwood on a rocky beach.',
      credit: 'Dead murres in Prince William Sound, Alaska, 2015–16. Photo: David Irons, USFWS (public domain)',
      href: 'https://www.fws.gov/media/common-murre-die-gulf-alaska',
    },
    readout: { value: 62000, digits: 0, unit: '', label: 'common murres washed ashore, 2015–16', color: IMPACT },
    refs: ['dfo2014', 'piatt2020', 'ap2026', 'ctv2026'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2014-11-01', point: { lat: 50.86, lon: -129.08 } },
    camera: { center: [-131, 50.6], zoom: 5, pitch: 45, bearing: 10 },
  },
  {
    id: 'toxic-bloom',
    eyebrow: 'Summer 2015 · California to Alaska',
    title: 'A toxic bloom',
    body: [
      'The largest and longest-lasting harmful algal bloom on the West Coast in at least 15 years stretched from California\'s Channel Islands to Alaska. Its toxin, domoic acid, shut Washington\'s razor clam fishery and Dungeness crab and razor clam harvests in parts of northern California.',
      'Off Vancouver Island the bloom came early, in May, and lasted into August, but only three areas there were closed to shellfish harvesting.',
    ],
    photo: {
      src: '/story-assets/blob/img/clam-diggers.webp',
      alt: 'Clam diggers with shovels on a wide, wet beach on the Washington coast.',
      credit: 'Clam diggers on the Washington coast. Photo: NOAA National Ocean Service',
      href: 'https://oceanservice.noaa.gov/news/sep15/westcoast-habs.html',
    },
    readout: { value: 9.2, digits: 1, prefix: '$', unit: 'M', label: 'lost to Washington\'s razor clam closure', color: IMPACT },
    refs: ['noaaHab', 'dfo2015'],
    view: { ...STORY_BASE, variable: 'mhw', period: 'monthly', date: '2015-07-01', region: 'ne_pacific' },
    camera: { center: [-126, 42], zoom: 3.6, pitch: 45, bearing: -15 },
  },
  {
    id: 'salmon',
    align: 'right',
    eyebrow: '2016 · Fraser River',
    title: 'The lowest sockeye run on record',
    body: [
      'Salmon that went to sea in 2015 met the warm water at its worst, and DFO expected fewer of them to come home. In 2016 the Fraser River\'s sockeye run was the smallest in a record more than 100 years long.',
      'Not every stock suffered: sockeye on the west coast of Vancouver Island and the Central Coast beat their forecasts. But in 2017, sockeye indicator stocks declined together along the whole coast.',
    ],
    readout: { value: 853000, digits: 0, unit: '', label: 'Fraser River sockeye returned in 2016', color: IMPACT },
    refs: ['dfo2015', 'dfo2016', 'dfo2017'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-08-01', point: { lat: 49.25, lon: -123.55 } },
    camera: { center: [-125.2, 49.6], zoom: 5.6, pitch: 50, bearing: -10 },
  },
  {
    id: 'newcomers',
    eyebrow: '2014–2017 · Haida Gwaii and Vancouver Island',
    title: 'Visitors from the south',
    body: [
      'Warm water carried southern species north. Albacore tuna were unusually abundant northwest of Haida Gwaii in 2014, and ocean sunfish turned up in BC waters.',
      'By June 2017 the surface had cooled, as the map shows, but pyrosomes, colonies of gelatinous animals, swarmed along the whole BC coast, clogging fishing gear and washing up on Vancouver Island and Haida Gwaii. DFO scientists suspect the warm years behind them.',
    ],
    photo: {
      src: '/story-assets/blob/img/pyrosomes.webp',
      alt: 'A DFO technician on a fishing vessel sorts a conveyor belt piled with pyrosomes.',
      credit: 'Alaina Dowling sorting a trawl catch of mostly pyrosomes, spring 2017. Photo: Linnea Flostrand, DFO',
      href: 'https://waves-vagues.dfo-mpo.gc.ca/library-bibliotheque/40717914.pdf',
    },
    refs: ['dfo2015', 'dfo2017'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2017-06-01', region: 'pacific_bioregions' },
    camera: { center: [-131.5, 52.5], zoom: 4.6, pitch: 40, bearing: 15 },
  },
  {
    id: 'cod',
    align: 'right',
    eyebrow: '2017–2020 · Gulf of Alaska',
    title: 'A fishery closed',
    body: ['Pacific cod in the Gulf of Alaska fell by 71% between the 2015 and 2017 surveys. With the stock at a historic low, the US federal cod fishery there was closed for 2020, the first time it had shut for lack of fish.'],
    readout: { value: 71, digits: 0, unit: '%', label: 'fewer Pacific cod, 2015 to 2017 surveys', color: IMPACT },
    refs: ['barbeaux2020', 'alaskaPublic2019'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2015-08-01', region: 'gulf_of_alaska' },
    camera: { center: [-148, 55.5], zoom: 4, pitch: 35, bearing: 0 },
  },
  {
    id: 'now',
    eyebrow: 'September 2025 · Now',
    title: 'Back to now',
    body: ['September 2025 was the warmest September on record across the NE Pacific region, and on September 9, 93.5% of it was in a marine heatwave, more than on any day of the original Blob. Across the record, the region\'s heatwave extent is rising by about 6 percentage points a decade.'],
    readout: { value: 1.37, digits: 2, unit: ' °C', signed: true, label: 'NE Pacific region, September 2025', color: WARM },
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2025-09-01', region: 'ne_pacific' },
    camera: { center: [-145, 44], zoom: 2.6, pitch: 15 },
  },
  {
    id: 'outro',
    align: 'center',
    outro: true,
    eyebrow: 'Ocean Surface Temperature Atlas',
    title: 'Explore it yourself',
    body: ['Every map above is NOAA data drawn live by OSTA. Open it at any date, place or region since 1985.'],
    view: { ...STORY_BASE, variable: 'anom', period: 'monthly', date: '2025-09-01', region: 'ne_pacific' },
    camera: { center: [-160, 30], zoom: 1.7 },
  },
]
</script>
