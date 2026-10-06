import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

// Plain vitest, not @nuxt/test-utils: everything under test here is a pure
// module (`app/utils/*`, the store's exported helpers), which is the reason those
// modules are kept pure. Anything needing a Nuxt runtime is checked in a browser.
export default defineConfig({
  resolve: {
    alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) },
  },
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
  },
})
