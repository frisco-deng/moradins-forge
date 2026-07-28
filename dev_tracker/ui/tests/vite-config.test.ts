/* @vitest-environment node */

import { describe, expect, it } from "vitest";

import { isWslRuntime, resolveManualChunk, resolveTrackerUiHost, resolveTrackerUiPort } from "../vite.config";

describe("vite config network defaults", () => {
  it("prefers explicit TRACKER_UI_HOST when configured", () => {
    const host = resolveTrackerUiHost({ TRACKER_UI_HOST: "192.168.1.10" }, "linux", "6.6.0");
    expect(host).toBe("192.168.1.10");
  });

  it("defaults to 0.0.0.0 in WSL", () => {
    const host = resolveTrackerUiHost({ WSL_DISTRO_NAME: "wsl-test-distro" }, "linux", "6.6.0");
    expect(host).toBe("0.0.0.0");
  });

  it("defaults to 127.0.0.1 outside WSL", () => {
    const host = resolveTrackerUiHost({}, "linux", "6.6.0");
    expect(host).toBe("127.0.0.1");
  });

  it("detects WSL from microsoft kernel release", () => {
    expect(isWslRuntime({}, "linux", "6.6.87.2-microsoft-standard-WSL2")).toBe(true);
    expect(isWslRuntime({}, "linux", "6.6.87.2-generic")).toBe(false);
  });

  it("resolves valid TRACKER_UI_PORT values", () => {
    expect(resolveTrackerUiPort("5273")).toBe(5273);
    expect(resolveTrackerUiPort("3000")).toBe(3000);
  });

  it("falls back to default port when TRACKER_UI_PORT is invalid", () => {
    expect(resolveTrackerUiPort(undefined)).toBe(5273);
    expect(resolveTrackerUiPort("")).toBe(5273);
    expect(resolveTrackerUiPort("0")).toBe(5273);
    expect(resolveTrackerUiPort("-1")).toBe(5273);
    expect(resolveTrackerUiPort("65536")).toBe(5273);
    expect(resolveTrackerUiPort("not-a-number")).toBe(5273);
  });

  it("maps heavy vendor domains into deterministic manual chunks", () => {
    expect(resolveManualChunk("/repo/node_modules/react-router-dom/dist/index.js")).toBe("vendor-react");
    expect(resolveManualChunk("/repo/node_modules/lucide-react/dist/lucide-react.js")).toBe("vendor-icons");
    expect(resolveManualChunk("/repo/node_modules/@xyflow/react/dist/esm/index.js")).toBe("vendor-flow");
    expect(resolveManualChunk("/repo/node_modules/framer-motion/dist/es/index.mjs")).toBe("vendor-motion");
    expect(resolveManualChunk("/repo/node_modules/remark-parse/index.js")).toBe("vendor-markdown");
  });

  it("leaves app source and unrelated modules to default chunking", () => {
    expect(resolveManualChunk("/repo/src/pages/ProjectBuilderPage.tsx")).toBeUndefined();
    expect(resolveManualChunk("/repo/node_modules/date-fns/index.js")).toBeUndefined();
  });
});
