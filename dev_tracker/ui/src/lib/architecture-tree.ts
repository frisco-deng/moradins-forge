export type ArchitecturePathType = "file" | "directory";
export type ArchitectureStatus = "pass" | "missing" | "unknown";

export interface ArchitectureTreeLeaf {
  id: string;
  label: string;
  path: string;
  pathType: ArchitecturePathType;
  description: string;
}

export interface ArchitectureTreeNode {
  id: string;
  label: string;
  description: string;
  entries: ArchitectureTreeLeaf[];
}

export const HARNESS_ARCHITECTURE_TREE: ArchitectureTreeNode[] = [
  {
    id: "foundations",
    label: "Foundations",
    description: "Core policy and onboarding entry points.",
    entries: [
      {
        id: "foundation-agents",
        label: "Agent policy root",
        path: "AGENTS.md",
        pathType: "file",
        description: "Execution guardrails and authority boundaries.",
      },
      {
        id: "foundation-entry",
        label: "Engineer entrypoint",
        path: "docs/00_overview/engineer_entrypoint.md",
        pathType: "file",
        description: "Initial read path for all harness work.",
      },
      {
        id: "foundation-engineer-index",
        label: "Engineer entry index",
        path: "docs/engineer_entry/index.md",
        pathType: "file",
        description: "Scope and constraints for implementation work.",
      },
    ],
  },
  {
    id: "architecture",
    label: "Architecture",
    description: "Topology, service boundaries, and system context.",
    entries: [
      {
        id: "architecture-index",
        label: "Architecture index",
        path: "docs/03_architecture/index.md",
        pathType: "file",
        description: "Architecture map and deep links.",
      },
      {
        id: "architecture-topology",
        label: "Container topology",
        path: "docs/03_architecture/container_topology.md",
        pathType: "file",
        description: "Deployment/runtime topology.",
      },
      {
        id: "architecture-services",
        label: "Service catalog",
        path: "docs/00_overview/service_catalog.md",
        pathType: "file",
        description: "Target and implemented service inventory.",
      },
    ],
  },
  {
    id: "governance",
    label: "Loop Governance",
    description: "Loop process policy, checklists, and control artifacts.",
    entries: [
      {
        id: "governance-run-loop",
        label: "Codex run loop",
        path: "docs/11_ops/codex_run_loop.md",
        pathType: "file",
        description: "Human-gated planner/implementer cycle contract.",
      },
      {
        id: "governance-gate",
        label: "Cycle gate checklist",
        path: "docs/15_checklists/agent_cycle_gate.md",
        pathType: "file",
        description: "Mandatory closeout acceptance checks.",
      },
      {
        id: "governance-changelog",
        label: "Control changelog",
        path: "Harness/artifacts/control/changelog.md",
        pathType: "file",
        description: "Cycle-by-cycle auditable decisions and approvals.",
      },
    ],
  },
  {
    id: "tooling",
    label: "Tooling and Builder",
    description: "Local control API, scripts, and skill registry surfaces.",
    entries: [
      {
        id: "tooling-branch-hygiene",
        label: "Branch hygiene script",
        path: "scripts/check_branch_hygiene.py",
        pathType: "file",
        description: "Deterministic branch/routing gate.",
      },
      {
        id: "tooling-control-api",
        label: "Control API runtime",
        path: "dev_tracker/ui/scripts/control-api.mjs",
        pathType: "file",
        description: "Builder, discovery, and sync API orchestration.",
      },
      {
        id: "tooling-skills-index",
        label: "Skill registry",
        path: "skills/index.md",
        pathType: "file",
        description: "Approved repository-local skill inventory.",
      },
    ],
  },
];

export function resolveArchitectureStatus(
  existingPaths: Set<string>,
  leaf: ArchitectureTreeLeaf,
  explicitStatus?: ArchitectureStatus,
): ArchitectureStatus {
  if (explicitStatus) {
    return explicitStatus;
  }

  if (leaf.pathType === "directory") {
    return Array.from(existingPaths).some((value) => value === leaf.path || value.startsWith(`${leaf.path}/`))
      ? "pass"
      : "missing";
  }

  return existingPaths.has(leaf.path) ? "pass" : "missing";
}
