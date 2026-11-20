import { defineConfig } from "vitest/config";

// Test-only config, kept separate from vite.config.ts so the production build
// (`tsc -b && vite build`) type-checks cleanly against the top-level Vite types
// (which do not include Vitest's `test` key). Vitest loads this file at runtime.
export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
