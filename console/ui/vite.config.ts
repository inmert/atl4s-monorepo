import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy points at the console backend (port 8089). The backend serves the
// built assets in production, so this only matters when running `npm run dev`
// against a running console backend.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8089',
      '/healthz': 'http://localhost:8089',
      '/ws': { target: 'ws://localhost:8089', ws: true },
    },
  },
});
