import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Inside Docker the API is reachable as `backend`; running bare it is localhost.
const apiTarget = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
