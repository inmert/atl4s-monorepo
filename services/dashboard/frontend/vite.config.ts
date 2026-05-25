import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy points at the dashboard backend (host networking, port 8090).
// In the Docker image the backend serves the built assets directly, so
// this only matters when running `npm run dev` against a running backend.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8090',
      '/healthz': 'http://localhost:8090',
      '/ws': { target: 'ws://localhost:8090', ws: true },
    },
  },
});
