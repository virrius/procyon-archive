import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В контейнере исходники лежат на bind-mount: inotify оттуда не доходит,
// поэтому файлы опрашиваем, а HMR-клиенту сообщаем внешний порт.
const poll = process.env.VITE_POLL === '1'
const hmrPort = Number(process.env.VITE_HMR_PORT || 0)

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': { target: process.env.API_URL || 'http://localhost:8000', changeOrigin: true } as never },
    watch: poll ? { usePolling: true, interval: 400 } : undefined,
    hmr: hmrPort ? { clientPort: hmrPort } : undefined,
  },
})
