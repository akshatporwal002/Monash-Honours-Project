import { apiUrl } from './e2e/urls'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'test-results/e2e-dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: `${frontendRoot}index.html`,
        e2e: `${frontendRoot}e2e.html`,
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: apiUrl,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: Number(process.env.QUANTUMLEARN_E2E_WEB_PORT ?? 4173),
    strictPort: true,
    proxy: {
      '/api': {
        target: apiUrl,
        changeOrigin: true,
      },
    },
  },
})
