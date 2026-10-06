import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The single project-root .env feeds both backend and frontend.
// Only INSTAGRAM_URL is exposed to the browser; secrets are never read here.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  return {
    plugins: [react()],
    define: {
      __INSTAGRAM_URL__: JSON.stringify(env.INSTAGRAM_URL || ''),
    },
    server: {
      port: 5173,
      proxy: { '/api': process.env.API_PROXY || 'http://127.0.0.1:8000' },
    },
    build: { sourcemap: false },
  }
})
