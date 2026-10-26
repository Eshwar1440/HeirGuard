/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Read VITE_* values from the repo-root .env; process env (Docker, Vercel) also works.
  envDir: '..',
  server: { host: true, port: 5173 },
  test: { include: ['src/**/*.test.ts', 'src/**/*.test.tsx'] },
})
