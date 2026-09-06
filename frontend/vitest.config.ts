/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Frontend unit/component test config (scaffold-frontend-testing skill, ADR-0015).
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx,js,jsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'cobertura'],
      reportsDirectory: '../.data/coverage/frontend',
      include: ['src/**/*.{ts,tsx,js,jsx}'],
      exclude: ['src/**/*.{test,spec}.*', 'src/**/*.d.ts', '**/main.{ts,tsx}'],
    },
  },
})
