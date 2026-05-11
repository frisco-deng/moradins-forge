import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV4",
  generated_at: "2026-02-24T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 8,
    docs_non_generated: 1,
    docs_generated: 7,
    phase_count: 1,
    stage_count: 1,
    stage_done_count: 0,
    loop_run_count: 1,
    open_gap_count: 0,
    changelog_entry_count: 1,
    awaiting_human_review_count: 0,
    implemented_feature_count: 1,
    active_guidance_count: 1,
    estimated_cycles_remaining: 2,
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
  loop_processes: { version: "LoopProcessesV1", row_count: 2, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 2,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-1",
      date: "2026-02-24",
      cycle_id: "cycle_001",
      loop_id: "loop-main",
      cycles_completed: 1,
      estimated_cycles_remaining: 2,
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
    flows: [
      {
        flow_id: "phase_execution_loop",
        title: "Phase Execution Loop",
        trigger: "approved cycle",
        steps: ["plan", "execute", "review"],
        required_artifacts: ["changelog.md"],
        human_gates: ["approval"],
        source_docs: ["docs/11_ops/codex_run_loop.md"],
      },
      {
        flow_id: "update_cycle_loop",
        title: "Update Cycle Loop",
        trigger: "approved update scope",
        steps: ["route update", "sync docs"],
        required_artifacts: ["changelog.md"],
        human_gates: ["human continue/pause/stop"],
        source_docs: ["docs/entrypoint_guide/update_cycle_routine.md"],
      },
    ],
    skills: [
      {
        skill_id: "capability_updates",
        title: "Capability Pipeline Updates",
        purpose: "Track updates",
        source_doc: "docs/exec_plans/updates/active/index.md",
        current_items: [{ label: "UPD", path: "docs/exec_plans/updates/active/upd.md" }],
      },
    ],
    conventions: [],
    guidelines: [{ label: "Run Loop", path: "docs/11_ops/codex_run_loop.md", description: "Loop guide" }],
    proposal: {
      title: "Dev Tracker UI Reorganization Update Plan (2026-02-24)",
      path: "docs/exec_plans/commissioning/completed/dev_tracker_ui_reorganization_update_plan_2026-02-24.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  git: {
    version: "GitStateV1",
    branch: "harness/help",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-02-24 | help",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    { version: "DocRecordV1", id: "doc-1", relative_path: "docs/11_ops/codex_run_loop.md" },
    { version: "DocRecordV1", id: "doc-2", relative_path: "docs/entrypoint_guide/update_cycle_routine.md" },
    { version: "DocRecordV1", id: "doc-3", relative_path: "docs/exec_plans/updates/active/upd.md" },
    {
      version: "DocRecordV1",
      id: "doc-4",
      relative_path: "docs/exec_plans/commissioning/completed/dev_tracker_ui_reorganization_update_plan_2026-02-24.md",
    },
  ],
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
    version: "TrackerSnapshotV4",
    generated_at: "2026-02-24T00:00:00.000Z",
    summary: {},
  },
};

describe("help page", () => {
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

  it("renders generic guidance and keeps loop details in topology", async () => {
    const user = userEvent.setup();
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/help"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Example End-to-End Flow")).toBeInTheDocument();
    });

    expect(screen.getByText("Generic Quick Loops")).toBeInTheDocument();
    expect(screen.getByText("Project Management Surfaces")).toBeInTheDocument();
    expect(screen.getByText("Harness Management Surfaces")).toBeInTheDocument();
    expect(screen.getByText("Harness Process Loops (Summary)")).toBeInTheDocument();
    expect(screen.queryByText(/Click a loop card to inspect trigger/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /deploy builder/i }));
    expect(screen.getByText("Top-Level Abstractions")).toBeInTheDocument();
    expect(
      screen.getByText("Human gate: Human approval remains required before sidecar deploy execution into established projects."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Open Harness Topology").length).toBeGreaterThan(0);
  });
});
