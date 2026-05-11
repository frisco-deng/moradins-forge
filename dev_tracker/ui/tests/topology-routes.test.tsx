import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-02-24T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 12,
    docs_human_owned_context: 1,
    docs_system_managed: 10,
    docs_generated: 1,
    phase_count: 1,
    stage_count: 1,
    stage_done_count: 0,
    loop_run_count: 1,
    open_gap_count: 0,
    changelog_entry_count: 1,
    awaiting_human_review_count: 0,
    implemented_feature_count: 1,
    active_guidance_count: 1,
    estimated_cycles_remaining: 1,
    estimated_loops_remaining: 1,
    archive_entry_count: 1,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: {
    version: "LoopStateV1",
    run_count: 1,
    last_run_id: "cycle_001",
    last_plan_file: "plan.md",
    last_result: "success",
    halt_reason: "",
    next_action: "review",
    history: [],
  },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 1, awaiting_human_review_count: 0, approved_count: 1, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 1, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 1, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 1, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 1,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-1",
      date: "2026-02-24",
      cycle_id: "cycle_001",
      loop_id: "loop-main",
      cycles_completed: 1,
      estimated_cycles_remaining: 1,
      estimated_loops_remaining: 1,
      stages_remaining: 1,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0.5,
      next_cycle_type: "implementation_loop",
      reviewer_action_required: "continue",
      notes: "ok",
    },
    rows: [],
  },
  archive_register: { version: "ArchiveRegisterV1", row_count: 1, update_count: 1, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
  topology: {
    version: "TopologySnapshotV1",
    namespaces: [
      {
        namespace: "apps/services",
        containers_services: "gateway,query",
        intent: "Runtime services",
      },
    ],
    boundaries: [
      {
        service: "gateway_api",
        primary_role: "Entry API",
        owns: "Ingress",
        does_not_own: "Index storage",
        key_contracts: "contract.gateway.v1",
      },
    ],
  },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "Docs-first harness for an enterprise, multi-container, agentic RAG platform.",
    architecture_goals: [],
    active_objective_count: 1,
    active_objectives: [
      {
        objective_id: "OBJ-1",
        goal: "Ship split topology",
        in_scope: "UI IA and routing",
        out_of_scope: "service scaffolding",
        stop_conditions: "project and harness topology split validated",
      },
    ],
    phase_status_summary: { completed: 0, pending: 1, other: 0 },
  },
  service_inventory: {
    version: "ServiceInventoryV1",
    planned_count: 1,
    implemented_count: 1,
    planned_only_count: 0,
    unmapped_implementation_count: 0,
    rows: [
      {
        service: "gateway_api",
        domain: "runtime",
        phase_target: "p2",
        implementation_surface: "apps/services/gateway_api",
        status: "implemented",
      },
    ],
  },
  harness_help: {
    version: "HarnessHelpV1",
    flows: [
      {
        flow_id: "phase_execution_loop",
        title: "Phase Execution Loop",
        trigger: "approved cycle",
        steps: ["plan", "execute"],
        required_artifacts: ["changelog.md"],
        human_gates: ["approval required"],
        source_docs: ["docs/11_ops/codex_run_loop.md"],
      },
    ],
    skills: [],
    conventions: [],
    guidelines: [],
    proposal: {
      title: "Plan",
      path: "docs/exec_plans/commissioning/completed/dev_tracker_ui_reorganization_update_plan_2026-02-24.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  git: {
    version: "GitStateV1",
    branch: "harness/topology-split",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-02-24 | topology",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-02-24T00:00:00.000Z",
    pending_approvals: 0,
    pending_total: 0,
    queues: [],
    zero_state: { updates: true, upgrades: true, tooling: true, suggestions: true },
    reconciliation: { status: "pass", issues: [] },
  },
  route_context_coverage: {
    version: "RouteContextCoverageV1",
    router_route_count: 1,
    context_route_count: 1,
    coverage_percent: 1,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-02-24T00:00:00.000Z",
    next_action: "continue",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  docs: [],
};

const mockStatus = {
  api: "TrackerControlStatusV1",
  runtime_state: {
    last_sync_at: "",
    last_sync_result: "success",
    last_sync_duration_ms: 30,
    sync_count: 1,
    syncing: false,
    last_error: "",
  },
  runtime_snapshot: {},
  tracker_snapshot: {
    version: "TrackerSnapshotV6",
    generated_at: "2026-02-24T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    bind_host: "127.0.0.1",
    ui_port: 5173,
    preferred_urls: ["http://localhost:5173/"],
    browser_access_summary: "local",
    remote_ssh_tunnel_example: "ssh -L 5173:127.0.0.1:5173 host",
    execution_host_summary: "Linux host",
    public_bind_supported: false,
  },
  assistant_runtimes: {
    codex_cli: {
      assistant: "codex_cli",
      label: "Codex CLI",
      command: "codex",
      args: [],
      terminal_command_template:
        "printf '%s\\n' '<paste prompt here>' | codex exec --color never --sandbox read-only",
      availability_status: "available",
      detail: "ready",
    },
    claude_code: {
      assistant: "claude_code",
      label: "Claude Code",
      command: "claude",
      args: [],
      terminal_command_template: "claude",
      availability_status: "available",
      detail: "ready",
    },
  },
};

const mockBuilderStatus = {
  version: "BuilderStatusV1",
  allowlisted_root: "/repo/projects",
  known_repos: [],
  recent_operations: [],
};

describe("topology routes", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("tracker_snapshot_v1.json")) {
          return new Response(JSON.stringify(mockSnapshot), { status: 200 });
        }
        if (url.includes("/api/status")) {
          return new Response(JSON.stringify(mockStatus), { status: 200 });
        }
        if (url.includes("/api/builder/status")) {
          return new Response(JSON.stringify(mockBuilderStatus), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("redirects /topology to the combined project workspace view", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/topology"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Project + Harness Topology")).toBeInTheDocument();
    });
  });

  it("redirects /harness-topology into the project workspace harness view", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/harness-topology"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Phase Project Request")).toBeInTheDocument();
    });
  });
});
