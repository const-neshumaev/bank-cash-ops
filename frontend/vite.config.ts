import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// The dev server proxies API calls to the backend so the browser talks to a
// single origin. Override the target with VITE_API_PROXY_TARGET when needed.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        // Host shared SDK (`frontend/src`) and vertical module frontends.
        // Module frontends are exposed under `./modules` inside the frontend
        // root (bind mount in development, copy in production), so Node module
        // resolution finds the frontend's `node_modules` from their sources.
        '@app': fileURLToPath(new URL('./src', import.meta.url)),
        '@modules': fileURLToPath(new URL('./modules', import.meta.url)),
      },
    },
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      // Docker Desktop on Windows does not always deliver filesystem events
      // from bind mounts, so Vite misses edits and keeps serving stale modules.
      // Polling makes hot reload reliable in development.
      watch: {
        usePolling: true,
      },
      // The HMR client reloads the whole page whenever its websocket drops.
      // Docker Desktop on Windows may close an idle socket long before the
      // default 30s keep-alive ping, so ping much more often to keep it alive.
      hmr: {
        clientPort: 5173,
        timeout: 5000,
      },
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
        '/admin': { target: proxyTarget, changeOrigin: true },
        '/static': { target: proxyTarget, changeOrigin: true },
      },
    },
  }
})
