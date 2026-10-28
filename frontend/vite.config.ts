import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // En conteneur / environnement de preview, on laisse passer tous les hôtes
    allowedHosts: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND, ws: true, changeOrigin: true },
    },
  },
  resolve: {
    alias: { '@': '/src' },
  },
})
