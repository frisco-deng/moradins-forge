import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";
import { OVERVIEW_MANAGER_PROJECT_ID } from "../src/lib/overview-project";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-03T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 16,
    docs_human_owned_context: 2,
    docs_system_managed: 10,
    docs_generated: 4,
    phase_count: 2,
    stage_count: 3,
    stage_done_count: 1,
    loop_run_count: 3,
    open_gap_count: 0,
    changelog_entry_count: 2,
    awaiting_human_review_count: 0,
    implemented_feature_count: 2,
    active_guidance_count: 2,
    estimated_cycles_remaining: 1,
    estimated_loops_remaining: 1,
    archive_entry_count: 1,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: {
    version: "LoopStateV1",
    run_count: 3,
    last_run_id: "cycle_003",
    last_plan_file: "plan.md",
    last_result: "success",
    halt_reason: "",
    next_action: "review",
    history: [],
  },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 2, awaiting_human_review_count: 0, approved_count: 2, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 2, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 2, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 2, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 1,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-1",
      date: "2026-03-03",
      cycle_id: "cycle_003",
      loop_id: "loop-main",
      cycles_completed: 3,
      estimated_cycles_remaining: 1,
      estimated_loops_remaining: 1,
      stages_remaining: 1,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0.75,
      next_cycle_type: "implementation_loop",
      reviewer_action_required: "continue",
      notes: "ok",
    },
    rows: [],
  },
  archive_register: { version: "ArchiveRegisterV1", row_count: 1, update_count: 1, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
  topology: { version: "TopologySnapshotV1", namespaces: [], boundaries: [] },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "Docs-first harness for an enterprise, multi-container, agentic RAG platform.",
    architecture_goals: [],
    active_objective_count: 0,
    active_objectives: [],
    phase_status_summary: { completed: 0, pending: 1, other: 0 },
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
    branch: "harness/nav-groups",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-03 | nav",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-03T00:00:00.000Z",
    pending_approvals: 0,
    pending_total: 0,
    queues: [],
    zero_state: { updates: true, upgrades: true, tooling: true, suggestions: true },
    reconciliation: { status: "pass", issues: [] },
  },
  route_context_coverage: {
    version: "RouteContextCoverageV1",
    router_route_count: 10,
    context_route_count: 10,
    coverage_percent: 1,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-03-03T00:00:00.000Z",
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
    generated_at: "2026-03-03T00:00:00.000Z",
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
  known_repos: [{ name: "alpha-app", path: "/repo/projects/alpha-app", git_initialized: true }],
  recent_operations: [],
};

describe("workspace navigation", () => {
  beforeEach(() => {
    localStorage.setItem("mh_overview_active_project_v1", OVERVIEW_MANAGER_PROJECT_ID);
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

  it("renders label-first primary navigation on deploy routes", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/deploy/builder"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: "Deploy workspace navigation" })).toBeInTheDocument();
    });

    const sidebar = screen.getAllByRole("navigation", { name: "Primary navigation" })[0]!;
    expect(within(sidebar).getByRole("link", { name: /Home/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Projects/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Deploy/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Payload/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Reviews/i })).toBeInTheDocument();
    expect(within(sidebar).getByRole("link", { name: /Settings/i })).toBeInTheDocument();

    expect(screen.getAllByRole("link", { name: "Quick Start" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Deploy Map" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Builder" }).length).toBeGreaterThan(0);
  });

  it("shows current project tabs inside project workspace routes", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/project/manager/overview"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
    });

    expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Delivery" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Governance" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Topology" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Operations" }).length).toBeGreaterThan(0);
  });

  it("returns to the pinned project workspace when Projects is clicked from another workspace", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/project/manager/overview"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
    });

    const sidebar = screen.getAllByRole("navigation", { name: "Primary navigation" })[0]!;

    await user.click(within(sidebar).getByRole("link", { name: /Deploy/i }));

    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: "Deploy workspace navigation" })).toBeInTheDocument();
    });

    await user.click(within(sidebar).getByRole("link", { name: /Projects/i }));

    await waitFor(() => {
      expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
    });

    expect(screen.queryByText("Tracked Projects")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Overview" }).length).toBeGreaterThan(0);
  });
});
