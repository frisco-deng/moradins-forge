import { render, screen, waitFor, within } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-02-23T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 10,
    docs_human_owned_context: 1,
    docs_system_managed: 8,
    docs_generated: 1,
    phase_count: 2,
    stage_count: 3,
    stage_done_count: 1,
    loop_run_count: 4,
    open_gap_count: 0,
    changelog_entry_count: 1,
    awaiting_human_review_count: 0,
    implemented_feature_count: 1,
    active_guidance_count: 1,
    estimated_cycles_remaining: 2,
    estimated_loops_remaining: 1,
    archive_entry_count: 1,
    markdown_changed_count: 1,
  },
  phases: {
    version: "PhaseBoardV1",
    phase_count: 1,
    stage_count: 1,
    stage_done_count: 0,
    phases: [
      {
        phase_number: 1,
        title: "Contract",
        phase_status: "pending",
        stages: [],
        done_when: [],
        checklist_total: 1,
        checklist_done: 0,
        completion: 0,
      },
    ],
  },
  loop_state: {
    version: "LoopStateV1",
    run_count: 4,
    last_run_id: "cycle_004",
    last_plan_file: "plan.md",
    last_result: "success",
    halt_reason: "awaiting",
    next_action: "review",
    history: [],
  },
  capability_gaps: {
    version: "CapabilityGapV1",
    open_count: 0,
    in_progress_count: 0,
    blocked_count: 0,
    rows: [],
  },
  changelog: {
    version: "ChangelogV1",
    entry_count: 1,
    awaiting_human_review_count: 0,
    approved_count: 1,
    rows: [],
  },
  current_features: {
    version: "CurrentFeaturesV1",
    implemented_count: 1,
    pending_count: 0,
    rows: [],
  },
  current_guidance: {
    version: "CurrentGuidanceV1",
    active_count: 1,
    rows: [],
  },
  loop_processes: {
    version: "LoopProcessesV1",
    row_count: 1,
    rows: [],
  },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 2,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-1",
      date: "2026-02-24",
      cycle_id: "cycle_004",
      loop_id: "loop-main",
      cycles_completed: 4,
      estimated_cycles_remaining: 2,
      estimated_loops_remaining: 1,
      stages_remaining: 3,
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
  archive_register: {
    version: "ArchiveRegisterV1",
    row_count: 1,
    update_count: 1,
    upgrade_review_count: 0,
    suggestion_count: 0,
    rows: [],
  },
  policies: {
    version: "PolicyDomainSummaryV1",
    domains: [],
  },
  topology: {
    version: "TopologySnapshotV1",
    namespaces: [],
    boundaries: [],
  },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "Docs-first harness for an enterprise, multi-container, agentic RAG platform.",
    architecture_goals: [],
    active_objective_count: 0,
    active_objectives: [],
    phase_status_summary: {
      completed: 0,
      pending: 0,
      other: 0,
    },
  },
  service_inventory: {
    version: "ServiceInventoryV1",
    planned_count: 0,
    implemented_count: 0,
    planned_only_count: 0,
    unmapped_implementation_count: 0,
    rows: [],
  },
  harness_help: {
    version: "HarnessHelpV1",
    flows: [],
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
    branch: "ai-bootstrap",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-02-23 | init",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-02-23T00:00:00.000Z",
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
    generated_at: "2026-02-23T00:00:00.000Z",
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
    generated_at: "2026-02-23T00:00:00.000Z",
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

describe("app smoke", () => {
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
    window.history.replaceState({}, "", "/");
  });

  it("renders the home launchpad with context rail and primary navigation", async () => {
    render(
      <TrackerProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(within(screen.getByRole("banner")).getByText("No repo selected")).toBeInTheDocument();
    });

    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Codex ready/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Command Palette/i })).toBeInTheDocument();

    const sidebar = screen.getAllByRole("navigation", { name: "Primary navigation" })[0]!;
    expect(within(sidebar).getByRole("link", { name: /Home/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Projects/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Deploy/i })).toBeInTheDocument();

    const contextRail = screen.getByLabelText("Context rail");
    expect(within(contextRail).getByText("Current Objective")).toBeInTheDocument();
    expect(within(contextRail).getByText("Current Context")).toBeInTheDocument();
    expect(within(contextRail).getByText("Blockers And Approvals")).toBeInTheDocument();
  });
});
