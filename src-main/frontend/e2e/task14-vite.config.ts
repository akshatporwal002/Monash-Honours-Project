import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Isolated local Task 14 acceptance fixture. Production uses the normal Vite config.
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost', port: 5244, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8144', changeOrigin: true } },
  },
})
