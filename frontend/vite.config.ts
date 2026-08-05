import { copyFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'

// maplibre-gl loads its worker script at runtime from a URL built off a
// template string, not a static literal - Vite's build can't follow that to
// emit the file as an asset, so it's silently missing from dist/assets and
// the browser 404s on it (nginx's SPA fallback then masks the 404 as an
// index.html response, which is what actually breaks the map). The worker
// file itself has a further static `import ... from "./maplibre-gl-shared.mjs"`
// - since we're copying the worker in by hand, outside Vite's module graph,
// that import is never bundled/inlined either, so its target has to be
// copied alongside it. Copy both into the build output so the runtime
// requests resolve.
function copyMaplibreWorker(): Plugin {
  let outDir = 'dist'
  const files = ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']
  return {
    name: 'copy-maplibre-worker',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
    },
    closeBundle() {
      for (const file of files) {
        const src = fileURLToPath(new URL(`./node_modules/maplibre-gl/dist/${file}`, import.meta.url))
        copyFileSync(src, resolve(outDir, 'assets', file))
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), copyMaplibreWorker()],
  // maplibre-gl loads its parser worker via a relative ESM import that
  // breaks when routed through Vite's dep pre-bundling cache.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
