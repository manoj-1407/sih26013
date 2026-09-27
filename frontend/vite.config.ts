import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8013',
    },
  },
  build: {
    // For local development builds, output to ../static so FastAPI can serve it.
    // In Docker, the multi-stage build overrides this with --outDir /frontend/dist.
    outDir: '../static',
    emptyOutDir: true,
  },
});
