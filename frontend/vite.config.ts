import { execSync } from 'node:child_process'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// Inside Docker the API is reachable as `backend`; running bare it is localhost.
const apiTarget = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000'

function resolveAppVersion(): string {
  const fromEnv = process.env.VITE_APP_VERSION?.trim()
  if (fromEnv) return fromEnv
  try {
    const sha = execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
    if (sha) return sha
  } catch {
    // The frontend Docker stage has no .git; CI passes VITE_APP_VERSION instead.
  }
  return 'dev'
}

function appVersionPlugin(version: string): Plugin {
  const payload = JSON.stringify({ version })
  return {
    name: 'lockin-app-version',
    config() {
      return {
        define: {
          'import.meta.env.VITE_APP_VERSION': JSON.stringify(version),
        },
      }
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url?.split('?')[0] === '/version.json') {
          res.setHeader('Content-Type', 'application/json')
          res.setHeader('Cache-Control', 'no-cache')
          res.end(payload)
          return
        }
        next()
      })
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'version.json',
        source: payload,
      })
    },
  }
}

const appVersion = resolveAppVersion()

export default defineConfig({
  plugins: [react(), tailwindcss(), appVersionPlugin(appVersion)],
  server: {
    host: true,
    headers: {
      'Service-Worker-Allowed': '/',
    },
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/mcp': { target: apiTarget, changeOrigin: true },
      '/oauth': { target: apiTarget, changeOrigin: true },
      '/.well-known': { target: apiTarget, changeOrigin: true },
    },
  },
})
