import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// В разработке запросы к серверу идут через прокси Vite — без CORS.
// В продакшене FastAPI сам раздаёт собранный dashboard/dist, всё на одном порту.
const SERVER = process.env.HM_SERVER ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': SERVER,
      '/health': SERVER,
      '/live': { target: SERVER, ws: true },
    },
  },
})
