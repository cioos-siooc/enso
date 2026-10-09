<template>
  <div>
    <!-- The app shell is a fixed-height column (app.vue); a story scrolls inside
         its own container, which is why the root is a wrapper around it. -->
    <div class="h-full overflow-y-auto bg-default font-serif text-[1.125rem] leading-[1.65] text-default">
      <main class="px-5 pb-16">
        <!-- ============ hero ============ -->
        <header class="mx-auto grid w-full max-w-280 items-center gap-10 py-10 md:grid-cols-[minmax(0,1fr)_minmax(0,36rem)] md:gap-12 md:py-14">
          <div class="flex flex-col gap-6">
            <span class="font-data text-xs uppercase tracking-wider text-muted">CIOOS Pacific · Ocean Surface Temperature Atlas</span>
            <h1 class="font-display text-[clamp(2.4rem,6.4vw,4.6rem)] font-extrabold leading-[1.02] tracking-[-0.01em] text-balance text-highlighted [font-stretch:118%]">
              A Fever on Canada's Pacific Coast
            </h1>
            <p class="text-xl">
              In late 2013 a patch of unusually warm water appeared in the Gulf of Alaska. It became one of the largest and longest marine heatwaves on record, stretching from the Bering Sea to Baja California, and on British Columbia's coast its effects lasted longer than farther south. Scientists called it the Blob.
            </p>
            <p>
              This is its story, retold with the Ocean Surface Temperature Atlas (OSTA). Every map, chart and number below is a view in OSTA that you can open and explore for yourself.
            </p>
            <UButton :to="storyLink({ v: 'anom', p: 'monthly', d: '2014-02-01', r: 'ne_pacific' })" target="_blank" label="Open OSTA" trailing-icon="i-mdi-open-in-new" size="lg" class="self-start font-sans" />
          </div>
          <figure class="flex flex-col gap-2.5">
            <StoryPlayer :frames="heroFrames" base="/story-assets/blob/hero" alt="Monthly sea surface temperature anomaly over the North Pacific on a globe" />
            <figcaption class="font-data text-xs leading-relaxed text-muted">
              Monthly sea surface temperature anomaly, September 2013 to December 2016, as OSTA draws it. Red is warmer than the 1991–2020 normal for that time of year, blue cooler. In OSTA, the play button in the time bar plays any span, daily, weekly or monthly.
            </figcaption>
          </figure>
        </header>

        <nav class="mx-auto flex w-full max-w-280 flex-wrap items-center gap-2 border-y border-default py-4" aria-label="OSTA features in this story">
          <span class="mr-2 font-data text-xs uppercase tracking-wider text-muted">Features in this story</span>
          <!-- Plain anchors, not NuxtLink: the router scrolls the window on a
               hash, and this page scrolls its own container instead. -->
          <a
            v-for="f in features"
            :key="f.label"
            :href="`#${f.at}`"
            class="rounded-md bg-elevated px-2 py-1 font-sans text-xs font-medium text-default ring ring-default ring-inset transition-colors hover:bg-accented"
          >{{ f.label }}</a>
        </nav>

        <!-- ============ 1 ============ -->
        <StoryChapter id="station-p" eyebrow="February 2014 · Station P, 50°N 145°W" title="A storm, a survey and a number nobody expected">
          <template #readout>
            <StoryReadout kind="anom" :value="2.2">surface anomaly <b class="text-highlighted">+2.2 °C</b></StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>In February 2014 the Canadian Coast Guard vessel CCGS <i>John P. Tully</i> sailed out along Line P, a line of 26 sampling stations running 1,400 kilometres west of Vancouver Island and visited since 1956. A big storm caught the survey, and the post-cruise report recorded "almost constant high winds and large seas."</p>
            <p>When the data were in, they showed water in the upper 100 metres of the Gulf of Alaska more than 2.5 °C warmer than normal. Howard Freeland, scientist emeritus at Fisheries and Oceans Canada's Institute of Ocean Sciences, had already seen float readings so far out of line that he suspected the instruments. They were working.</p>
            <StoryQuote cite="Howard Freeland, writing to a NOAA colleague, March 2014">
              “A deviation from normal of 4.5 standard deviations is the single biggest climate anomaly I am aware of anywhere in modern history. It really is huge.”
            </StoryQuote>
            <p>The satellite record at Station P, the far end of Line P, tells the same story from the surface. In February 2014 the sea there averaged <Num>8.25 °C</Num> against a normal of <Num>6.03 °C</Num>. That is <Num>+2.2 °C</Num>, the warmest February at that spot in 42 years of record. January 2014, at <Num>+2.3 °C</Num>, is the warmest month relative to normal in the cell's entire record.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/papa.webp"
            :to="links.papa"
            alt="OSTA with a point selected at Station P: the map shows a warm patch in the Gulf of Alaska, the side panel reads +2.2 °C for February 2014 and ranks 2014 first of 42 Februaries, and the chart below spikes in early 2014."
          >
            OSTA at Station P, February 2014. Left: the cell's numbers and every February since 1985, warmest first. Bottom: its monthly anomaly, zoomed to 2011–2019, with the map's month marked in amber.
          </StoryFigure>
          <StoryTry
            :to="links.papa"
            :chips="['Point timeseries', 'Monthly and annual rankings', 'Daily / Weekly / Monthly']"
            :facts="[
              { term: '1st', desc: 'February 2014 among 42 Februaries at Station P' },
              { term: '1st', desc: '2014 among 42 years there, at +1.59 °C for the year' },
              { term: '158 days', desc: 'its heatwave without a break, 7 December 2013 to 13 May 2014' },
            ]"
          >
            Click anywhere on the ocean. OSTA picks the nearest 0.05° grid cell, about 5 km across, and charts its daily record back to 1985. Daily, Weekly and Monthly change how the chart and the map are averaged. The panel on the left ranks the map's month against the same month in every other year; switch it to Year to rank whole years.
          </StoryTry>
          <div class="mx-auto w-full max-w-160">
            <StoryQuote cite="Richard Dewey, Ocean Networks Canada, February 2016. Poor surf at Tofino cancelled its 2013 competition while oceanographers were still unaware of what was happening.">
              “The people that were the first to point out what was happening were the surfers.”
            </StoryQuote>
          </div>
        </StoryChapter>

        <!-- ============ 2 ============ -->
        <StoryChapter id="blob" eyebrow="June 2014 · Northeast Pacific" title="The Blob takes shape">
          <template #readout>
            <StoryReadout kind="extent" :value="86.3">area in a heatwave <b class="text-highlighted">86.3%</b></StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>Washington State climatologist Nick Bond named it the Blob in 2014. At its peak it covered about nine million square kilometres, an area larger than Australia. Temperatures generally ran 1 to 4 °C above seasonal norms. That may sound small to anyone used to daily swings in air temperature, but across most of the northeast Pacific, 1.5 °C above normal is already very unusual.</p>
            <p>The cause was a lack of strong winter storms. Normally, cold air and winter storms cool the thin, sun-warmed surface layer, and storm waves stir it into the colder water below. From the fall of 2013, a persistent high-pressure system over the Gulf of Alaska meant weaker winds and fewer storms. The summer's heat stayed in the water, and over successive calm winters it built downward.</p>
            <p>OSTA has a named region for it, NE Pacific (the Blob), from 40 to 60°N and 160 to 125°W. With the ocean layer set to MHW, a region's number becomes heatwave extent: the share of its ocean area in a marine heatwave that day. On 11 June 2014 that share was <Num>86.3%</Num>, the 17th most widespread day in 15,251 days of record. Through 2014, more than half of the region was in a heatwave on 249 days. In 2013 it had been 5.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/nepac_mhw.webp"
            :to="links.nepac"
            alt="OSTA with the NE Pacific (the Blob) region selected on the MHW layer for 11 June 2014: nearly the whole outlined region is yellow (Moderate), the panel reads 86.3%, and the chart shows heatwave extent from 1985 with a cluster of peaks after 2013."
          >
            NE Pacific (the Blob) on 11 June 2014, MHW layer. The map draws NOAA's heatwave categories in NOAA's own colours; the panel and chart report the region's heatwave extent.
          </StoryFigure>
          <StoryTry
            :to="links.nepac"
            :chips="['Named regions', 'Heatwave categories', 'Heatwave extent', 'Region notes']"
            :facts="[
              { term: '249 days', desc: 'in 2014 with more than half the region in a heatwave' },
              { term: '55%', desc: 'of the region in a heatwave on an average day of 2014' },
            ]"
          >
            Switch the ocean layer to MHW, then choose Region and pick NE Pacific (the Blob) from the North Pacific group. The camera flies to the region and the chart and panel switch to its area mean. The ⓘ beside the region name explains why the region exists and how its edges are drawn, with references.
          </StoryTry>

          <aside class="mx-auto flex w-full max-w-160 flex-col gap-4 border-l-2 border-default pl-5 text-base" aria-labelledby="what-is">
            <h3 id="what-is" class="font-display text-lg font-bold text-highlighted">What counts as a marine heatwave</h3>
            <p>Many researchers use the definition of Hobday and colleagues (2016): water warmer than the 90th percentile of past measurements for that place and time of year, for at least five days in a row. Hobday and colleagues (2018) then named categories by how far the water goes past that threshold, in multiples of the gap between the threshold and the long-term mean. NOAA Coral Reef Watch, whose daily product OSTA draws, uses those four and adds a fifth, open-ended class: Beyond extreme.</p>
            <ul class="grid grid-cols-2 gap-2 font-data text-xs sm:grid-cols-5" role="list">
              <li v-for="c in categories" :key="c.name" class="flex flex-col gap-1">
                <span class="h-2.5 rounded-sm" :style="{ background: c.color }" />
                <b class="font-medium text-highlighted">{{ c.name }}</b>
                <span class="text-muted">{{ c.gap }}</span>
              </li>
            </ul>
            <p>OSTA shows two different baselines and says which one you are reading under every chart. The anomaly is measured against a 1991–2020 daily mean. The heatwave category is NOAA's, measured against a fixed 1985–2012 90th percentile. Because they use different statistics and different years, an anomaly value does not convert into a category.</p>
          </aside>
        </StoryChapter>

        <!-- ============ 3 ============ -->
        <StoryChapter id="oregon" eyebrow="Autumn 2014 · Off Newport, Oregon" title="Down the coast">
          <template #readout>
            <StoryReadout kind="anom" :value="4">daily peak <b class="text-highlighted">+4.0 °C</b>, off the scale</StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>By autumn 2014, satellites, buoys and floats showed the warmth all the way down the west coast of North America. NOAA scientists recorded spikes 7 °C above average at a buoy off Oregon.</p>
            <p>A satellite cell is not a buoy. Each value in OSTA is a daily analysis for a cell about 5 km across, not a reading from one instrument at one spot, and it need not match a buoy's spikes. Even so, the cell off Newport reached <Num>+4.0 °C</Num> on 7 October 2014, at <Num>17.5 °C</Num>. Its heatwave began on 19 September 2014 and lasted 225 days, to 1 May 2015, peaking at Category 3, Severe. No day in that cell's record has been worse.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/oregon.webp"
            :to="links.oregon"
            alt="OSTA on the MHW layer for 24 December 2014 with a point off Newport, Oregon: the coast from Washington to California is in a heatwave, the panel reads Category 3 Severe and lists the longest heatwave as 225 days, 19 September 2014 to 1 May 2015."
          >
            A cell off Newport, Oregon, on 24 December 2014. The panel's Longest heatwave card counts the run for you.
          </StoryFigure>
          <StoryTry
            :to="links.oregon"
            :chips="['Heatwave runs', 'Daily categories']"
            :facts="[
              { term: '225 days', desc: '19 September 2014 to 1 May 2015' },
              { term: 'Cat 3', desc: 'Severe, the worst day in that cell\'s record' },
            ]"
          >
            With MHW on, click a cell. The panel shows the day's category, how many days of the last year were heatwave days, whether the cell is in a heatwave now, and the longest unbroken heatwave in its record with its dates and peak category.
          </StoryTry>
        </StoryChapter>

        <!-- ============ 4 ============ -->
        <StoryChapter id="ashore" eyebrow="June 2015 · Gulf of Alaska to California" title="The warmth moves to the coast">
          <template #readout>
            <StoryReadout kind="anom" :value="1.53">NE Pacific, June 2015 <b class="text-highlighted">+1.53 °C</b></StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>The surface warmth had reached much of the Pacific coast of North America by late summer 2014. Below the surface it moved more slowly. Over the winter of 2015 the warm layer deepened, to 300 metres in places, and the deep Blob reached the continental shelf in 2015. Put two Junes side by side and the change at the surface is plain. June 2012 fell in one of the region's coolest years on record. In June 2015 warm water lined the coast from Alaska to California.</p>
            <p>Averaged over the NE Pacific region, June 2015 was <Num>+1.53 °C</Num>, the warmest June on record there, and 2015 was the region's warmest year.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/swipe.webp"
            :to="links.swipe"
            alt="OSTA in swipe compare on a flat map: left of the divider, June 2012, the Gulf of Alaska is blue; right of it, June 2015, the water along the coast from Alaska to California is deep red."
          >
            Swipe compare, June 2012 (left) against June 2015 (right). The chart marks both months: MAP in amber, CMP in blue.
          </StoryFigure>
          <StoryTry
            :to="links.swipe"
            :chips="['Swipe compare', 'Globe / Flat', 'Adjustable colour range']"
            :facts="[
              { term: '1st', desc: 'June 2015 among 42 Junes in the NE Pacific region' },
              { term: '+1.07 °C', desc: '2015 for the region, its warmest year' },
            ]"
          >
            Press Date next to Compare in the time bar. A second map opens on the same bucket a year earlier; set its date, then drag the divider to wipe between the two. Both halves share the camera, the colour scale and the selection, so only the date changes. Globe and Flat switch the projection.
          </StoryTry>
        </StoryChapter>

        <!-- ============ 5 ============ -->
        <StoryChapter id="bc" eyebrow="2015–2016 · British Columbia" title="The Blob comes to British Columbia, and stays">
          <template #readout>
            <StoryReadout kind="extent" :value="99.97">BC waters in a heatwave, 1 April 2016 <b class="text-highlighted">99.97%</b></StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>British Columbia's coast is a maze of islands, channels and deep fjords, and the Blob's story there is longer than farther south. Put BC's waters and the whole NE Pacific region on one chart and BC's peak comes later.</p>
            <p>Across the NE Pacific region, heatwave extent peaked in 2014. In BC's waters, the peak came a year later: through 2015 an average of <Num>73.5%</Num> of them were in a heatwave, and more than half were on 284 of 365 days. In 2016 BC's waters stayed above half on 192 days, against 85 for the wider region. On 1 April 2016, <Num>99.97%</Num> of BC's waters were in a marine heatwave.</p>
            <p>Every month from December 2014 to July 2015 is still the warmest of its kind on record in BC's waters, and 2015, 2016 and 2014 are its three warmest years.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/bc_vs_offshore.webp"
            :to="links.bc"
            alt="OSTA with Pacific Bioregions (DFO) as selection A and NE Pacific (the Blob) as B, monthly MHW extent zoomed to 2011–2019: the violet offshore line rises first in 2014, the green BC line peaks higher in 2015 and stays up into 2016."
          >
            A: Pacific Bioregions (DFO), in green, outlined on the map. B: NE Pacific (the Blob), in violet. Monthly heatwave extent, zoomed to 2011–2019.
          </StoryFigure>
          <StoryTry
            :to="links.bc"
            :chips="['Polygon regions', 'Compare A and B', 'CSV download']"
            :facts="[
              { term: '2014', desc: 'NE Pacific region\'s peak: 55% on an average day' },
              { term: '2015', desc: 'BC\'s peak: 73.5% of its waters on an average day' },
              { term: '8 months', desc: 'December 2014 to July 2015, each still a record' },
            ]"
          >
            Pick Pacific Bioregions (DFO) from Canadian waters. OSTA draws its real outline, the union of Fisheries and Oceans Canada's four Pacific marine bioregions, and averages only the cells inside it. Then open Compare and choose NE Pacific (the Blob): it joins the chart as a second line, B. Download data saves both series as one CSV.
          </StoryTry>

          <aside class="mx-auto flex w-full max-w-160 flex-col gap-4 border-l-2 border-default pl-5 text-base" aria-labelledby="below">
            <h3 id="below" class="font-display text-lg font-bold text-highlighted">Below what the satellites can see</h3>
            <p>The satellite data in OSTA cover only the sea surface, and by that measure the Blob ended in 2016. In BC's waters an average of only 8.4% of the area was in a surface heatwave in 2017.</p>
            <p>The heat had not left. Line P and Argo floats found abnormally warm water at depth offshore through the end of 2018. Along the coast, BC's fjords are closed at their mouths by underwater sills left by glaciers. Seasonal upwelling and downwelling carried the Blob's warm water over the sills, and it settled in the deep basins behind them, where it stayed long after the surface had cooled (Jackson et al., 2018).</p>
            <p>Those profiles come from ships, floats and moorings, not satellites. Many are in the <a href="https://catalogue.cioospacific.ca/" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">CIOOS Pacific data catalogue</a>.</p>
          </aside>
        </StoryChapter>

        <!-- ============ 6 ============ -->
        <StoryChapter id="land" eyebrow="Winter 2014–15 · Interior British Columbia" title="A mild winter on land">
          <template #readout>
            <StoryReadout kind="anom" :value="4.1" :range="8">Kamloops nights, February 2015 <b class="text-highlighted">+4.1 °C</b> on the land scale, ±8 °C</StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>Warm water offshore and mild weather inland arrived together that winter. OSTA can draw NOAA Climate Prediction Center land data over the ocean, so both can be read on one map.</p>
            <p>In February 2015, daily minimum temperatures averaged <Num>+4.1 °C</Num> above the 1991–2020 normal around Kamloops and <Num>+3.5 °C</Num> around Prince George. BC's waters that month were <Num>+1.8 °C</Num>, their warmest February on record.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/land.webp"
            :to="links.land"
            alt="OSTA for February 2015 with the land Tmin anomaly overlay on: BC's interior and the Pacific Northwest are red on land as well as at sea; point B sits near Kamloops, and the chart has the ocean anomaly on the left axis and the land anomaly on the right."
          >
            February 2015: ocean anomaly at sea, overnight-low anomaly on land. A is BC's waters; B is a land cell near Kamloops, plotted on the chart's right-hand axis.
          </StoryFigure>
          <StoryTry
            :to="links.land"
            :chips="['Land overlay', 'Tmin / Tmax / Precip', 'Two-axis chart']"
            :facts="[
              { term: '+4.1 °C', desc: 'overnight lows near Kamloops, February 2015' },
              { term: '+3.5 °C', desc: 'near Prince George, same month' },
            ]"
          >
            In the Layers card, set Land to Tmin, Tmax or Precip, then choose Anomaly (for precipitation, % of normal or mm vs normal). The land layer has its own legend and is cut exactly to the coastline. Alt-click a town to add it as point B: the chart draws land on a second axis beside the ocean.
          </StoryTry>
        </StoryChapter>

        <!-- ============ 7 ============ -->
        <StoryChapter id="world" eyebrow="1997–2019 · Around the world" title="The Blob was not alone">
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>The term marine heatwave was coined after 2011, when water off Western Australia ran 3 to 5 °C above average along 2,000 km of coastline and caused massive kelp forest die-offs. Looking back through the records, researchers found that the frequency of marine heatwaves had doubled over the preceding 30 years. Holbrook and colleagues (2020) catalogued the major events and their causes.</p>
            <p>OSTA covers the whole ocean, and many of those events have a named region of their own. Each card opens that region in OSTA at the event's warmest month.</p>
          </div>
          <div class="mx-auto grid w-full max-w-280 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            <StoryEvent v-for="ev in events" :key="ev.title" v-bind="ev" />
          </div>
          <p class="mx-auto w-full max-w-160 font-data text-xs leading-relaxed text-muted">
            Anomalies are each region's area mean for that month. "In a heatwave" is the region's highest daily heatwave extent during the event. Drivers and effects follow Holbrook et al. (2020).
          </p>
        </StoryChapter>

        <!-- ============ 8 ============ -->
        <StoryChapter id="now" eyebrow="September 2025 – October 2026 · Now" title="The northeast Pacific has a new record">
          <template #readout>
            <StoryReadout kind="extent" :value="93.5">NE Pacific in a heatwave, 9 September 2025 <b class="text-highlighted">93.5%</b></StoryReadout>
          </template>
          <div class="mx-auto flex w-full max-w-160 flex-col gap-5">
            <p>The original Blob no longer holds all of the region's records. September 2025 averaged <Num>16.3 °C</Num> across the NE Pacific region, <Num>+1.37 °C</Num> above normal and the warmest September on record, just ahead of 2014. On 9 September 2025, <Num>93.5%</Num> of the region was in a marine heatwave: the most widespread day in 15,251 days of record, beyond any day of the original Blob. Across the whole record, the region's heatwave extent is rising by about 6 percentage points a decade.</p>
            <p>The Blob was followed by the 2015–16 El Niño: in November 2015, Niño 3.4 was <Num>+2.81 °C</Num>, its warmest November since the satellite record began in 1985. As of October 2026, the ribbon under OSTA's header reports a very strong El Niño under way, with Niño 3.4 at <Num>+2.65 °C</Num> for July to September 2026. That index follows the method of NOAA's Oceanic Niño Index but uses NOAA's CoralTemp data and a fixed 1991–2020 baseline, so it will not match NOAA's official value exactly.</p>
            <p>OSTA updates daily, so the numbers on this page will age. The links will still open the same views.</p>
          </div>
          <StoryFigure
            src="/story-assets/blob/img/now.webp"
            :to="links.now"
            alt="OSTA for September 2025 with the NE Pacific (the Blob) region: the whole region is warm, the ranking panel puts 2025 first of 42 Septembers with 2014 and 2016 next, and the header ribbon reads Very strong El Niño."
          >
            NE Pacific (the Blob), September 2025: first of 42 Septembers, with 2014 and 2016 next. The red ribbon under the header is OSTA's one-line summary of the current ENSO state.
          </StoryFigure>
          <StoryTry
            :to="links.now"
            :chips="['ENSO ribbon', 'Shareable links', 'Updated daily']"
            :facts="[
              { term: '1st', desc: 'September 2025 among 42 Septembers in the NE Pacific' },
              { term: '93.5%', desc: '9 September 2025, the most widespread heatwave day on record there' },
            ]"
          >
            Click the ribbon under the header to jump to Niño 3.4, and its ⓘ for how the index is computed. Every view in OSTA has its own address: copy the URL from your browser to share exactly what you are looking at, including the date, layer, point, region and comparison. That is how every link on this page was made.
          </StoryTry>
        </StoryChapter>

        <!-- ============ ending ============ -->
        <section class="mx-auto flex w-full max-w-160 flex-col items-start gap-5 pt-24">
          <h2 class="font-display text-[clamp(1.8rem,3.6vw,2.6rem)] font-[750] leading-[1.05] text-highlighted [font-stretch:112%]">Explore the ocean yourself</h2>
          <p>OSTA maps daily sea surface temperature, its anomaly and NOAA's marine heatwave category for the global ocean at 0.05°, from 1985 to yesterday, with land temperature and precipitation on top.</p>
          <UButton to="/" target="_blank" label="Open OSTA" trailing-icon="i-mdi-open-in-new" size="lg" class="font-sans" />
        </section>

        <footer class="mx-auto mt-20 flex w-full max-w-160 flex-col gap-4 border-t border-default pt-10 text-sm leading-relaxed text-muted">
          <h2 class="font-display text-xl font-bold text-highlighted [font-stretch:112%]">Sources and credits</h2>
          <p>Numbers were read from OSTA on 8 October 2026, with ocean data through 3 October 2026, and the images are screenshots of OSTA. Sea surface temperature: NOAA Coral Reef Watch CoralTemp v3.1, daily at 0.05°. Anomaly: against a 1991–2020 daily climatology. Marine heatwave category: NOAA Coral Reef Watch Marine Heatwave v1.0.1, against NOAA's 1985–2012 90th percentile. Land temperature: NOAA CPC Global Unified, 0.5°. Station P is the grid cell nearest 50°N 145°W. Basemap © Mapbox © OpenStreetMap. Quotes, the Line P account and the heatwave drivers and effects come from the original story; every figure was read from NOAA's data in OSTA, not estimated.</p>
          <p>Retold from <a href="https://cioospacific.ca/ressource/a-fever-on-canadas-pacific-coast/" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">A Fever on Canada's Pacific Coast</a>, created by Tyee Bridge, Jonathan Kellogg, Mat Brown, Mercedes Minck, Jeremy Latham and Jorin Weatherston of the Hakai Institute, for CIOOS Pacific.</p>
          <ol class="flex list-decimal flex-col gap-2 pl-5">
            <li v-for="r in references" :key="r.text">
              {{ r.text }} <i v-if="r.journal">{{ r.journal }}</i><template v-if="r.doi">. <a :href="`https://doi.org/${r.doi}`" target="_blank" rel="noopener" class="text-primary underline underline-offset-3">doi:{{ r.doi }}</a></template>
            </li>
          </ol>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * "A Fever on Canada's Pacific Coast", the CIOOS Pacific story about the
 * 2013-16 marine heatwave, retold with OSTA's own views. Every image is a
 * screenshot of the app (public/story-assets/blob/) and every number was read
 * from the API on 8 October 2026; the links open the same views.
 */
useSeoMeta({
  title: 'A Fever on Canada\'s Pacific Coast · OSTA',
  description: 'The 2013–16 marine heatwave known as the Blob, retold with the Ocean Surface Temperature Atlas.',
})

const links = {
  papa: storyLink({ v: 'anom', p: 'monthly', d: '2014-02-01', at: '50.00,-145.00' }),
  nepac: storyLink({ v: 'mhw', p: 'daily', d: '2014-06-11', r: 'ne_pacific' }),
  oregon: storyLink({ v: 'mhw', p: 'daily', d: '2014-12-24', at: '44.67,-124.55' }),
  swipe: storyLink({ v: 'anom', p: 'monthly', d: '2012-06-01', c: '2015-06-01', at: '50.00,-145.00' }),
  bc: storyLink({ v: 'mhw', p: 'monthly', d: '2015-07-01', r: 'pacific_bioregions', r2: 'ne_pacific' }),
  land: storyLink({ v: 'anom', p: 'monthly', d: '2015-02-01', land: 'tmin', lm: 'anomaly', r: 'pacific_bioregions', at2: '50.67,-120.33' }),
  now: storyLink({ v: 'anom', p: 'monthly', d: '2025-09-01', r: 'ne_pacific' }),
}

/** September 2013 to December 2016, one frame a month. */
const heroFrames: string[] = []
for (let y = 2013; y <= 2016; y++) {
  for (let m = y === 2013 ? 9 : 1; m <= 12; m++) heroFrames.push(`${y}-${String(m).padStart(2, '0')}-01`)
}

const features = [
  { label: 'Point timeseries', at: 'station-p' },
  { label: 'Monthly and annual rankings', at: 'station-p' },
  { label: 'Named regions', at: 'blob' },
  { label: 'Heatwave categories', at: 'blob' },
  { label: 'Heatwave runs', at: 'oregon' },
  { label: 'Swipe compare', at: 'ashore' },
  { label: 'Compare A and B', at: 'bc' },
  { label: 'CSV download', at: 'bc' },
  { label: 'Land overlay', at: 'land' },
  { label: 'Global coverage', at: 'world' },
  { label: 'ENSO ribbon', at: 'now' },
  { label: 'Shareable links', at: 'now' },
]

/** NOAA's palette, as domain.yml declares it. */
const categories = [
  { name: '1 Moderate', color: '#ffff80', gap: '1× the gap' },
  { name: '2 Strong', color: '#ffb333', gap: '2×' },
  { name: '3 Severe', color: '#ff8000', gap: '3×' },
  { name: '4 Extreme', color: '#cc4d00', gap: '4×' },
  { name: '5 Beyond extreme', color: '#991a00', gap: 'open-ended' },
]

const events = [
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '1997-11-01', r: 'nino34' }),
    src: '/story-assets/blob/img/g_nino34_1997.webp',
    alt: 'Niño 3.4 box in November 1997, filled with deep red along the equator',
    meta: '1997–98 · Equatorial Pacific · Niño 3.4',
    title: 'The 1997–98 El Niño',
    stats: ['Nov 1997 +2.42 °C', '2nd of 41 Novembers'],
    text: 'Ocean–atmosphere feedbacks. A less productive upper ocean and major losses to fisheries. Only November 2015 has been warmer here.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2003-06-01', r: 'mediterranean' }),
    src: '/story-assets/blob/img/g_med_2003.webp',
    alt: 'The Mediterranean outlined in June 2003, red across the western basin and the Tyrrhenian Sea',
    meta: '2003 · Mediterranean (IHO)',
    title: 'Mediterranean Sea',
    stats: ['Jun 2003 +1.49 °C', 'now 3rd of 42 Junes'],
    text: 'Persistent high pressure during a heatwave on land. Mass die-offs in nearshore rocky habitats. A record then, it has since been passed by June 2025 and June 2026.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2011-02-01', r: 'w_australia' }),
    src: '/story-assets/blob/img/g_ningaloo_2011.webp',
    alt: 'The Ningaloo Niño box off Western Australia in February 2011, deep red along the coast',
    meta: '2011 · Ningaloo Niño (W Australia)',
    title: 'Ningaloo Niño',
    stats: ['Feb 2011 +2.14 °C', '1st of 42 Februaries', '99.2% in a heatwave'],
    text: 'A strengthened coastal current pushed warm water into unusual areas, with links to the strong 2010–11 La Niña. Severe effects on kelp, seagrass and coral habitats, major losses to shellfish, and tropical fish found in colder water.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2012-05-01', r: 'gulf_of_maine' }),
    src: '/story-assets/blob/img/g_maine_2012.webp',
    alt: 'The Gulf of Maine outlined in May 2012, deep red across the gulf and the shelf beyond',
    meta: '2012 · Gulf of Maine (SeaVoX)',
    title: 'Northwest Atlantic',
    stats: ['May 2012 +2.38 °C', '1st of 42 Mays', '89.2% in a heatwave'],
    text: 'A long-lived high pressure system weakened the winds. Fisheries moved to unusual grounds. The next-warmest May is almost a full degree cooler.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2015-06-01', r: 'ne_pacific' }),
    src: '/story-assets/blob/img/g_blob_2015.webp',
    alt: 'The NE Pacific (the Blob) region in June 2015, red throughout with the deepest red offshore of California and Oregon',
    meta: '2013–16 · NE Pacific (the Blob)',
    title: 'The Blob',
    stats: ['Jun 2015 +1.53 °C', '1st of 42 Junes', '86.3% in a heatwave'],
    text: 'Long-term high pressure, linked to the tropics, weakened winter storms. Harmful algae and low productivity killed seabirds and marine mammals.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2016-03-01', r: 'tasman_sea' }),
    src: '/story-assets/blob/img/g_tasman_2016.webp',
    alt: 'The Tasman Sea outlined between Australia and New Zealand in March 2016, warm throughout',
    meta: '2015–16 · Tasman Sea (IHO)',
    title: 'Tasman Sea',
    stats: ['Mar 2016 +1.19 °C', '1st of 42 Marches', '82.1% in a heatwave'],
    text: 'A strengthened coastal current pushed warm water into unusual areas. Disease and deaths in aquaculture farms. March 2025 came within 0.03 °C.',
  },
  {
    to: storyLink({ v: 'anom', p: 'monthly', d: '2019-11-01', r: 'ne_pacific' }),
    src: '/story-assets/blob/img/g_blob2_2019.webp',
    alt: 'The NE Pacific (the Blob) region in November 2019, with a deep red patch in the Gulf of Alaska',
    meta: '2019 · NE Pacific (the Blob)',
    title: 'Blob 2.0',
    stats: ['Nov 2019 +1.63 °C', '1st of 41 Novembers', '88.8% in a heatwave'],
    text: 'Weak summer winds let the surface heat up. November 2019 is the warmest month relative to normal in the region\'s whole record, warmer than any month of the original Blob.',
  },
]

const references = [
  { text: 'Marine Heatwaves International Working Group.' },
  { text: 'Oliver et al. (2021). Marine heatwaves.', journal: 'Annual Review of Marine Science', doi: '10.1146/annurev-marine-032720-095144' },
  { text: 'Holbrook et al. (2020). Keeping pace with marine heatwaves.', journal: 'Nature Reviews Earth & Environment', doi: '10.1038/s43017-020-0068-4' },
  { text: 'Jackson et al. (2018). Warming from recent marine heatwave lingers in deep British Columbia fjord.', journal: 'Geophysical Research Letters', doi: '10.1029/2018GL078971' },
  { text: 'Cavole et al. (2016). Biological impacts of the 2013–2015 warm-water anomaly in the northeast Pacific: winners, losers, and the future.', journal: 'Oceanography', doi: '10.5670/oceanog.2016.32' },
  { text: 'Hobday et al. (2016). A hierarchical approach to defining marine heatwaves.', journal: 'Progress in Oceanography', doi: '10.1016/j.pocean.2015.12.014' },
  { text: 'Hobday et al. (2018). Categorizing and naming marine heatwaves.', journal: 'Oceanography', doi: '10.5670/oceanog.2018.205' },
  { text: 'Freeland et al. (2019). \'The Blob\' – or, how unusual were ocean temperatures in the northeast Pacific during 2014–2018?', journal: 'Deep Sea Research Part I', doi: '10.1016/j.dsr.2019.06.007' },
]

/** An inline number: tabular, a touch brighter than the text around it. */
const Num = defineComponent((_, { slots }) => () => h('span', { class: 'tabular-nums font-semibold text-highlighted' }, slots.default?.()))
</script>
