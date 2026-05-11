import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vitest/config";

import { resolveTrackerUiHost, resolveTrackerUiPort } from "./vite.config";

const uiHost = resolveTrackerUiHost();
const uiPort = resolveTrackerUiPort(process.env.TRACKER_UI_PORT);

export default defineConfig({
  plugins: [react()],
  server: {
    host: uiHost,
    port: uiPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
  test: {
    include: ["tests/**/*.browser.test.ts", "tests/**/*.browser.test.tsx"],
    browser: {
      enabled: true,
      provider: playwright(),
      headless: true,
      instances: [{ browser: "chromium", name: "deploy-map-browser" }],
      viewport: {
        width: 1440,
        height: 960,
      },
    },
  },
});
