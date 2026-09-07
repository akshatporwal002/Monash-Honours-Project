import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Isolated Task 16 localhost acceptance. Production keeps the regular Vite config.
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost', port: 5266, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8166', changeOrigin: true } },
  },
})
