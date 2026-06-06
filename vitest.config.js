import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./frontend/src/__tests__/setup.js'],
    include: ['frontend/src/**/*.{test,spec}.{js,jsx}'],
  },
  resolve: {
    extensions: ['.js', '.jsx'],
  },
});
