import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api -> FastAPI backend on :8000 so the frontend can call relative URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
