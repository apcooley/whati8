import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to FastAPI during development
      '/auth': 'http://localhost:15853',
      '/foods': 'http://localhost:15853',
      '/logs': 'http://localhost:15853',
      '/agent': 'http://localhost:15853'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
