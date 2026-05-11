/* @vitest-environment node */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");

describe("route context parity", () => {
  it("keeps route-context inventory aligned with router paths", () => {
    const routeContextSource = fs.readFileSync(path.join(uiRoot, "src", "lib", "route-context.ts"), "utf8");

    const appRoutes = new Set<string>([
      "/",
      "/home",
      "/projects",
      "/deploy",
      "/deploy/quick-start",
      "/deploy/readiness",
      "/deploy/map",
      "/deploy/builder",
      "/deploy/status",
      "/payload",
      "/template",
      "/project/:projectId",
      "/project/:projectId/overview",
      "/project/:projectId/delivery",
      "/project/:projectId/delivery/features",
      "/project/:projectId/delivery/phases",
      "/project/:projectId/governance",
      "/project/:projectId/topology",
      "/project/:projectId/topology/project",
      "/project/:projectId/topology/harness",
      "/project/:projectId/topology/combined",
      "/project/:projectId/docs",
      "/project/:projectId/operations",
      "/project/:projectId/operations/loops",
      "/project/:projectId/operations/status",
      "/reviews",
      "/reviews/queue",
      "/reviews/changes",
      "/reviews/exchange",
      "/reviews/archive",
      "/docs",
      "/docs/:docId",
      "/settings",
      "/settings/preferences",
      "/settings/system",
      "/settings/help",
      "/quick-start",
      "/readiness",
      "/deploy-map",
      "/builder",
      "/project-status",
      "/system-status",
      "/help",
      "/review",
      "/changes",
      "/exchange",
      "/archive",
      "/effects",
      "/features",
      "/phases",
      "/policies",
      "/project-topology",
      "/harness-topology",
      "/topology",
      "/cycles",
      "/loop-processes",
    ]);

    const contextRoutes = new Set<string>();
    for (const match of routeContextSource.matchAll(/route:\s*"([^"]+)"/g)) {
      const route = String(match[1] ?? "").trim();
      if (!route) {
        continue;
      }
      contextRoutes.add(route);
    }

    const missingInContext = [...appRoutes].filter((route) => !contextRoutes.has(route)).sort((a, b) => a.localeCompare(b));
    const extraInContext = [...contextRoutes].filter((route) => !appRoutes.has(route)).sort((a, b) => a.localeCompare(b));

    expect(missingInContext).toEqual([]);
    expect(extraInContext).toEqual([]);
  });
});
