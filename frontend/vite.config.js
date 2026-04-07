import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT) || 5173,
  },
  preview: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT) || 4173,
    strictPort: false,
    allowedHosts: [
      'dashboard.pontis.one',
      'glistening-youth-production.up.railway.app',
      '.railway.app',
      'localhost'
    ]
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    copyPublicDir: true,
    rollupOptions: {
      output: {
        manualChunks: undefined
      }
    }
  }
})