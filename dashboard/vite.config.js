import { createReadStream, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// this file is ESM ("type": "module"), so derive the directory rather than
// leaning on Vite's __dirname shim
const DEV_DATA_ROOT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../data/predictions'
)

// Serve the pipeline's local output at /dev-data during `npm run dev`, so the
// dashboard can be developed against freshly generated predictions without
// deploying to S3 first. Opt in by pointing the app at it:
//
//   VITE_API_URL=/dev-data/predictions.json \
//   VITE_HISTORY_URL=/dev-data/history/engine_{id}.json npm run dev
//
// Dev-only and outside the build, so nothing here reaches production. `data/`
// is gitignored, hence the deployed API stays the default.
function devDataPlugin() {
  return {
    name: 'condition-mon-dev-data',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/dev-data', (req, res, next) => {
        // strip the query string and reject any attempt to climb out of data/
        const rel = decodeURIComponent((req.url || '').split('?')[0])
        const file = resolve(DEV_DATA_ROOT, '.' + rel)
        if (!file.startsWith(DEV_DATA_ROOT) || !existsSync(file)) return next()
        res.setHeader('Content-Type', 'application/json')
        createReadStream(file).pipe(res)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), devDataPlugin()],
})
