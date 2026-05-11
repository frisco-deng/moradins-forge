import os from "node:os";
import { playwright } from "@vitest/browser-playwright";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const DEFAULT_UI_PORT = 5273;

function normalizeModuleId(id: string): string {
  return id.replaceAll("\\", "/");
}

export function resolveManualChunk(id: string): string | undefined {
  const normalizedId = normalizeModuleId(id);
  if (!normalizedId.includes("/node_modules/")) {
    return undefined;
  }

  if (
    normalizedId.includes("/node_modules/react/") ||
    normalizedId.includes("/node_modules/react-dom/") ||
    normalizedId.includes("/node_modules/react-router/") ||
    normalizedId.includes("/node_modules/react-router-dom/")
  ) {
    return "vendor-react";
  }

  if (normalizedId.includes("/node_modules/lucide-react/")) {
    return "vendor-icons";
  }

  if (normalizedId.includes("/node_modules/@xyflow/")) {
    return "vendor-flow";
  }

  if (
    normalizedId.includes("/node_modules/framer-motion/") ||
    normalizedId.includes("/node_modules/gsap/")
  ) {
    return "vendor-motion";
  }

  if (
    normalizedId.includes("/node_modules/react-markdown/") ||
    normalizedId.includes("/node_modules/mdast-") ||
    normalizedId.includes("/node_modules/micromark") ||
    normalizedId.includes("/node_modules/hast-") ||
    normalizedId.includes("/node_modules/remark-") ||
    normalizedId.includes("/node_modules/rehype-") ||
    normalizedId.includes("/node_modules/unist-") ||
    normalizedId.includes("/node_modules/vfile") ||
    normalizedId.includes("/node_modules/property-information") ||
    normalizedId.includes("/node_modules/space-separated-tokens") ||
    normalizedId.includes("/node_modules/comma-separated-tokens")
  ) {
    return "vendor-markdown";
  }

  return undefined;
}

export function resolveTrackerUiPort(rawPort: string | undefined): number {
  const parsed = Number(rawPort);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return DEFAULT_UI_PORT;
  }
  return parsed;
}

export function isWslRuntime(
  env: NodeJS.ProcessEnv = process.env,
  platform: string = process.platform,
  release: string = os.release(),
): boolean {
  if (platform !== "linux") {
    return false;
  }
  if (Boolean(env.WSL_DISTRO_NAME) || Boolean(env.WSL_INTEROP)) {
    return true;
  }
  return release.toLowerCase().includes("microsoft");
}

export function resolveTrackerUiHost(
  env: NodeJS.ProcessEnv = process.env,
  platform: string = process.platform,
  release: string = os.release(),
): string {
  const configuredHost = String(env.TRACKER_UI_HOST ?? "").trim();
  if (configuredHost) {
    return configuredHost;
  }
  return isWslRuntime(env, platform, release) ? "0.0.0.0" : "127.0.0.1";
}

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
  preview: {
    host: uiHost,
    port: uiPort,
    strictPort: true,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: resolveManualChunk,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    exclude: ["tests/**/*.browser.test.ts", "tests/**/*.browser.test.tsx"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
    },
    browser: {
      enabled: false,
      provider: playwright(),
      headless: true,
      instances: [{ browser: "chromium" }],
      viewport: {
        width: 1440,
        height: 960,
      },
    },
  },
});
