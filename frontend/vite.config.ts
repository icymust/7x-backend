import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // maplibre-gl loads its parser worker via a relative ESM import that
  // breaks when routed through Vite's dep pre-bundling cache.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
