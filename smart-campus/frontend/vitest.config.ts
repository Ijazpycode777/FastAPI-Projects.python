import { defineConfig } from "vitest/config";
import path from "node:path";
import react from "@vitejs/plugin-react";

// Test-only config, kept separate from vite.config.ts so the production build
// (`tsc -b && vite build`) type-checks cleanly against the top-level Vite types
// (which do not include Vitest's `test` key). Vitest loads this file at runtime.
// The `@` alias + react plugin mirror vite.config.ts so test files import the
// same way the app does (JSX in .tsx tests needs the react transform too).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
