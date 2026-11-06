import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Forward API calls to the local FastAPI backend (backend/app.py).
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
