import { defineConfig } from 'vite';
import solid from 'vite-plugin-solid';
import { resolve } from 'node:path';

export default defineConfig({
  base: '/static/dist/',
  plugins: [solid()],
  resolve: {
    alias: {
      '~': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8767',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8767',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../opendream/static/dist',
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2022',
  },
});
