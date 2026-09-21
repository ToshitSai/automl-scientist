import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    tailwindcss(),
    react()
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    },
    watch: {
      ignored: [
        '**/backend/**',
        '**/database/**',
        '**/agents/**',
        '**/sandbox/**',
        '**/datasets/**',
        '**/uploaded_datasets/**',
        '**/__pycache__/**',
        '**/*.py',
        '**/*.pyc',
        '**/*.parquet',
        '**/*.csv'
      ]
    }
  }
});
