import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // @vitejs/plugin-react and vitest bundle different vite copies; the types disagree, the runtime does not.
  plugins: [react() as never],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./vitest.setup.ts"], testTimeout: 20000, include: ["src/**/*.test.{ts,tsx}"] },
});
