import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to FastAPI during development
      '/auth': 'http://localhost:9428',
      '/foods': 'http://localhost:9428',
      '/logs': 'http://localhost:9428',
      '/agent': 'http://localhost:9428'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
