import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      // Proxy all /api/v1/* and /health to FastAPI during development
      '/api': 'http://localhost:9428',
      '/health': 'http://localhost:9428'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
