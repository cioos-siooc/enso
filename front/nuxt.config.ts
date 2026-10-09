// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },

  modules: ['@nuxt/ui', '@pinia/nuxt', '@nuxt/eslint'],

  css: ['~/assets/css/main.css'],

  // The stories' faces. @nuxt/fonts (through Nuxt UI) resolves families named
  // in the CSS on its own, but only at their default width: Archivo's headings
  // are set wide, which needs the `wdth` axis requested explicitly.
  fonts: {
    families: [
      {
        name: 'Archivo',
        provider: 'google',
        weights: ['400 800'],
        providerOptions: { google: { experimental: { variableAxis: { wdth: [['62', '125']] } } } },
      },
      { name: 'Literata', provider: 'google', weights: [400, 600], styles: ['normal', 'italic'] },
      { name: 'IBM Plex Mono', provider: 'google', weights: [400, 500] },
      {
        name: 'Anybody',
        provider: 'google',
        weights: ['500 900'],
        providerOptions: { google: { experimental: { variableAxis: { wdth: [['75', '150']] } } } },
      },
      { name: 'Source Serif 4', provider: 'google', weights: [400, 600], styles: ['normal', 'italic'] },
      { name: 'Martian Mono', provider: 'google', weights: [400, 500] },
    ],
  },

  app: {
    head: {
      title: 'Ocean Surface Temperature Atlas (OSTA)',
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/osta-logo.svg' }],
    },
  },

  // Dark-only, matching the ocean-acidification dashboard. Light mode is a real
  // option but nothing here has been checked in it.
  colorMode: {
    preference: 'dark',
    fallback: 'dark',
  },

  runtimeConfig: {
    // Server-only. During SSR the Nitro server is inside the compose network,
    // where the browser-facing http://localhost:9021 is its own loopback — it
    // has to reach the API by service name instead.
    apiInternalBaseUrl: process.env.API_INTERNAL_BASE_URL || 'http://api:4000',
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:9021',
      mapboxToken: process.env.NUXT_PUBLIC_MAPBOX_TOKEN || '',
      version: process.env.NUXT_PUBLIC_VERSION || 'dev',
      // Usage analytics. Empty by default: `app/plugins/posthog.client.ts`
      // returns early without a key, so dev and any deploy that does not want
      // analytics need no other change.
      posthogKey: process.env.NUXT_PUBLIC_POSTHOG_KEY || '',
      posthogHost: process.env.NUXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com',
    },
  },

  vite: {
    server: {
      // The dev server runs in a container behind a published port.
      hmr: { clientPort: Number(process.env.FRONT_PORT) || 9020 },
      watch: { usePolling: true },
    },
  },
})
