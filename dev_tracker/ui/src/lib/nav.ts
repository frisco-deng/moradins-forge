import {
  BookOpenText,
  ClipboardCheck,
  FolderKanban,
  House,
  Package2,
  Rocket,
  Settings2,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

export interface SecondaryNavItem {
  id: string;
  path: string;
  label: string;
}

export type PrimaryWorkspaceId = "home" | "projects" | "deploy" | "payload" | "reviews" | "docs" | "settings";

export const PRIMARY_NAV_ITEMS: NavItem[] = [
  {
    id: "home",
    path: "/home",
    label: "Home",
    description: "Manager command center",
    icon: House,
  },
  {
    id: "projects",
    path: "/projects",
    label: "Projects",
    description: "Tracked repositories and project workspaces",
    icon: FolderKanban,
  },
  {
    id: "deploy",
    path: "/deploy",
    label: "Deploy",
    description: "Optional diagnostics, readiness, build, and verify workflows",
    icon: Rocket,
  },
  {
    id: "payload",
    path: "/payload",
    label: "Payload",
    description: "Moradin payload and kit workspace",
    icon: Package2,
  },
  {
    id: "reviews",
    path: "/reviews",
    label: "Reviews",
    description: "Approvals, activity, and audit history",
    icon: ClipboardCheck,
  },
  {
    id: "docs",
    path: "/docs",
    label: "Docs",
    description: "Global docs explorer",
    icon: BookOpenText,
  },
  {
    id: "settings",
    path: "/settings",
    label: "Settings",
    description: "Preferences, diagnostics, and help",
    icon: Settings2,
  },
];

export const DEPLOY_WORKSPACE_ITEMS: SecondaryNavItem[] = [
  { id: "deploy-quick-start", path: "/deploy/quick-start", label: "Quick Start" },
  { id: "deploy-readiness", path: "/deploy/readiness", label: "Readiness" },
  { id: "deploy-map", path: "/deploy/map", label: "Deploy Map" },
  { id: "deploy-builder", path: "/deploy/builder", label: "Builder" },
  { id: "deploy-status", path: "/deploy/status", label: "Verify" },
];

export const REVIEW_WORKSPACE_ITEMS: SecondaryNavItem[] = [
  { id: "reviews-queue", path: "/reviews/queue", label: "Review Queue" },
  { id: "reviews-changes", path: "/reviews/changes", label: "Change Feed" },
  { id: "reviews-exchange", path: "/reviews/exchange", label: "Activity" },
  { id: "reviews-archive", path: "/reviews/archive", label: "Archive" },
];

export const SETTINGS_WORKSPACE_ITEMS: SecondaryNavItem[] = [
  { id: "settings-preferences", path: "/settings/preferences", label: "Preferences" },
  { id: "settings-system", path: "/settings/system", label: "System" },
  { id: "settings-help", path: "/settings/help", label: "Help" },
];

export const PROJECT_WORKSPACE_ITEMS: SecondaryNavItem[] = [
  { id: "project-overview", path: "overview", label: "Overview" },
  { id: "project-delivery-features", path: "delivery/features", label: "Delivery" },
  { id: "project-governance", path: "governance", label: "Governance" },
  { id: "project-topology-project", path: "topology/project", label: "Topology" },
  { id: "project-docs", path: "docs", label: "Docs" },
  { id: "project-operations-loops", path: "operations/loops", label: "Operations" },
];

export const NAV_ITEMS: NavItem[] = PRIMARY_NAV_ITEMS;

function isActivePath(pathname: string, path: string) {
  return pathname === path || pathname.startsWith(`${path}/`);
}

export function findActivePrimaryNavId(pathname: string): PrimaryWorkspaceId {
  if (pathname.startsWith("/project/")) {
    return "projects";
  }

  const active = PRIMARY_NAV_ITEMS.find((item) => isActivePath(pathname, item.path));
  return (active?.id as PrimaryWorkspaceId | undefined) ?? "home";
}

export function findWorkspaceSecondaryItems(pathname: string): SecondaryNavItem[] {
  if (pathname.startsWith("/deploy/")) {
    return DEPLOY_WORKSPACE_ITEMS;
  }
  if (pathname.startsWith("/reviews/")) {
    return REVIEW_WORKSPACE_ITEMS;
  }
  if (pathname.startsWith("/settings/")) {
    return SETTINGS_WORKSPACE_ITEMS;
  }
  return [];
}

export function isNavPathActive(pathname: string, path: string) {
  if (path === "/home") {
    return pathname === "/home";
  }
  return isActivePath(pathname, path);
}
