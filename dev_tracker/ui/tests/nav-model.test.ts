import { describe, expect, it } from "vitest";

import {
  DEPLOY_WORKSPACE_ITEMS,
  findActivePrimaryNavId,
  findWorkspaceSecondaryItems,
  NAV_ITEMS,
  PRIMARY_NAV_ITEMS,
  PROJECT_WORKSPACE_ITEMS,
  REVIEW_WORKSPACE_ITEMS,
  SETTINGS_WORKSPACE_ITEMS,
} from "../src/lib/nav";

describe("nav model", () => {
  it("defines the workspace-first primary navigation", () => {
    expect(PRIMARY_NAV_ITEMS.map((group) => group.label)).toEqual([
      "Home",
      "Projects",
      "Deploy",
      "Payload",
      "Reviews",
      "Docs",
      "Settings",
    ]);
  });

  it("exposes deploy, review, settings, and project sub-navigation", () => {
    expect(DEPLOY_WORKSPACE_ITEMS.map((item) => item.path)).toEqual([
      "/deploy/quick-start",
      "/deploy/readiness",
      "/deploy/map",
      "/deploy/builder",
      "/deploy/status",
    ]);
    expect(REVIEW_WORKSPACE_ITEMS.map((item) => item.path)).toEqual([
      "/reviews/queue",
      "/reviews/changes",
      "/reviews/exchange",
      "/reviews/archive",
    ]);
    expect(SETTINGS_WORKSPACE_ITEMS.map((item) => item.path)).toEqual([
      "/settings/preferences",
      "/settings/system",
      "/settings/help",
    ]);
    expect(PROJECT_WORKSPACE_ITEMS.map((item) => item.path)).toEqual([
      "overview",
      "delivery/features",
      "governance",
      "topology/project",
      "docs",
      "operations/loops",
    ]);
  });

  it("keeps flattened workspace routes available for command palette search", () => {
    const allPaths = NAV_ITEMS.map((item) => item.path);
    expect(allPaths).toContain("/home");
    expect(allPaths).toContain("/projects");
    expect(allPaths).toContain("/deploy");
    expect(allPaths).toContain("/payload");
    expect(allPaths).toContain("/reviews");
    expect(allPaths).toContain("/docs");
    expect(allPaths).toContain("/settings");
  });

  it("maps routes to primary and secondary navigation groups", () => {
    expect(findActivePrimaryNavId("/home")).toBe("home");
    expect(findActivePrimaryNavId("/projects")).toBe("projects");
    expect(findActivePrimaryNavId("/deploy/builder")).toBe("deploy");
    expect(findActivePrimaryNavId("/payload")).toBe("payload");
    expect(findActivePrimaryNavId("/reviews/queue")).toBe("reviews");
    expect(findActivePrimaryNavId("/docs")).toBe("docs");
    expect(findActivePrimaryNavId("/settings/system")).toBe("settings");
    expect(findActivePrimaryNavId("/project/manager/overview")).toBe("projects");
    expect(findActivePrimaryNavId("/does-not-exist")).toBe("home");

    expect(findWorkspaceSecondaryItems("/deploy/map")).toEqual(DEPLOY_WORKSPACE_ITEMS);
    expect(findWorkspaceSecondaryItems("/reviews/queue")).toEqual(REVIEW_WORKSPACE_ITEMS);
    expect(findWorkspaceSecondaryItems("/settings/help")).toEqual(SETTINGS_WORKSPACE_ITEMS);
    expect(findWorkspaceSecondaryItems("/home")).toEqual([]);
  });
});
