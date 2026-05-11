import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-08T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 4,
    docs_human_owned_context: 1,
    docs_system_managed: 2,
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
    archive_entry_count: 0,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: { version: "LoopStateV1", run_count: 1, last_run_id: "cycle_001", last_plan_file: "plan.md", last_result: "success", halt_reason: "", next_action: "review", history: [] },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 1, awaiting_human_review_count: 0, approved_count: 1, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 1, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 1, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 0, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 1,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-001",
      date: "2026-03-08",
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
  archive_register: { version: "ArchiveRegisterV1", row_count: 0, update_count: 0, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
  topology: {
    version: "TopologySnapshotV1",
    namespaces: [{ namespace: "api", intent: "runtime", containers_services: "svc-api" }],
    boundaries: [{ service: "svc-api", primary_role: "serve", owns: "api", does_not_own: "db", key_contracts: "http" }],
  },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "mission",
    architecture_goals: [],
    active_objective_count: 0,
    active_objectives: [],
    phase_status_summary: { completed: 0, pending: 1, other: 0 },
  },
  service_inventory: {
    version: "ServiceInventoryV1",
    planned_count: 2,
    implemented_count: 1,
    planned_only_count: 1,
    unmapped_implementation_count: 0,
    rows: [
      { service: "svc-api", domain: "platform", phase_target: "S01", implementation_surface: "apps/api", status: "implemented" },
      { service: "svc-worker", domain: "platform", phase_target: "S02", implementation_surface: "", status: "planned_only" },
    ],
  },
  harness_help: {
    version: "HarnessHelpV1",
    flows: [],
    skills: [],
    conventions: [],
    guidelines: [],
    proposal: {
      title: "Plan",
      path: "docs/exec_plans/commissioning/active/plan.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-08T00:00:00.000Z",
    pending_approvals: 0,
    pending_total: 0,
    queues: [],
    zero_state: { updates: true, upgrades: true, tooling: true, suggestions: true },
    reconciliation: { status: "pass", issues: [] },
  },
  route_context_coverage: { version: "RouteContextCoverageV1", router_route_count: 1, context_route_count: 1, coverage_percent: 100, missing_in_context: [], extra_in_context: [], rows: [] },
  human_review_summary: { version: "HumanReviewSummaryV1", generated_at: "2026-03-08T00:00:00.000Z", next_action: "continue", pending_total: 0, project_review: [], harness_review: [], notes: [] },
  git: { version: "GitStateV1", branch: "main", short_sha: "abc123", last_commit: "abc123", dirty: false, markdown_changed_count: 0, markdown_changed_files: [], grouped_by_section: {} },
  docs: [],
};

const mockStatus = {
  api: "TrackerControlStatusV1",
  runtime_state: { last_sync_at: "", last_sync_result: "success", last_sync_duration_ms: 30, sync_count: 1, syncing: false, last_error: "" },
  runtime_snapshot: {},
  tracker_snapshot: { version: "TrackerSnapshotV6", generated_at: "2026-03-08T00:00:00.000Z", summary: {} },
};

describe("project topology page", () => {
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
        if (url.includes("/api/git")) {
          return new Response(JSON.stringify(mockSnapshot.git), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("respects query filters and lets the operator clear the service filter", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/project/manager/topology/project?status=awaiting&service=svc-worker"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(within(screen.getByRole("banner")).getByText("/repo")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "svc-worker" })).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "svc-api" })).not.toBeInTheDocument();
    expect(screen.getByText("Service svc-worker")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear Service Filter" }));

    await waitFor(() => {
      expect(screen.queryByText("Service svc-worker")).not.toBeInTheDocument();
    });
  });
});
