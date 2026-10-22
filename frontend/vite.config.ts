import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'CERT_CONSOLE_');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { '/api': env.CERT_CONSOLE_API_URL || 'http://127.0.0.1:8000' },
    },
  };
});
