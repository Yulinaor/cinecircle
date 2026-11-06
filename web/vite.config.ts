import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The API only allows http://localhost:5173 (CORS), so fail loudly instead of moving to 5174.
  server: { port: 5173, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Cold first test + parallel workers on a busy machine can exceed the 5 s default; the
    // Testing Library asyncUtilTimeout (3 s) still reports missing elements well before this.
    testTimeout: 15000,
  },
})
