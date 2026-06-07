import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyHttp = env.VITE_PROXY_HTTP || 'http://localhost:8900'
  const proxyWs = env.VITE_PROXY_WS || 'ws://localhost:8000'

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5111,
      proxy: {
        '/api': {
          target: proxyHttp,
          changeOrigin: true,
          ws: true,
        },
      }
    },
    preview: {
      host: '0.0.0.0',
      port: 3000
    }
  }
})
