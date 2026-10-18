import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, requests to /api are forwarded to the Python server,
// so the browser never has to deal with CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
