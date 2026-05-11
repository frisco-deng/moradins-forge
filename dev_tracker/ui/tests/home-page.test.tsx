import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-27T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 8,
    docs_human_owned_context: 1,
    docs_system_managed: 6,
    docs_generated: 1,
    phase_count: 6,
    stage_count: 14,
    stage_done_count: 14,
    loop_run_count: 39,
    open_gap_count: 0,
    changelog_entry_count: 39,
    awaiting_human_review_count: 1,
    implemented_feature_count: 12,
    active_guidance_count: 3,
    estimated_cycles_remaining: 0,
    estimated_loops_remaining: 0,
    archive_entry_count: 5,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: {
    version: "LoopStateV1",
    run_count: 39,
    last_run_id: "cycle_039_hup0014_ui_usability_pass",
    last_plan_file: "plan.md",
    last_result: "success",
    halt_reason: "awaiting_human_review",
    next_action: "review_hup0014_ui_usability_pass",
    history: [],
  },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: {
    version: "ChangelogV1",
    entry_count: 39,
    awaiting_human_review_count: 1,
    approved_count: 38,
    rows: [
      {
        entry_id: "CHG-039",
        date: "2026-03-27",
        cycle_id: "cycle_039_hup0014_ui_usability_pass",
        phase_stage: "p0-s00",
        change_type: "ui-governance-usability",
        summary: "UI usability pass awaiting review",
        docs_updated: "HomePage.tsx",
        human_gate_decision: "pending",
        approval_ref: "pending_cycle_039_ui_usability_review",
        approval_status: "awaiting_human_review",
      },
    ],
  },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 12, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 3, rows: [] },
  loop_processes: {
    version: "LoopProcessesV1",
    row_count: 1,
    rows: [],
  },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 0,
    latest_estimated_loops_remaining: 0,
    latest: {
      gate_id: "HGS-039",
      date: "2026-03-27",
      cycle_id: "cycle_039_hup0014_ui_usability_pass",
      loop_id: "loop_hup0014_ui_usability",
      cycles_completed: 39,
      estimated_cycles_remaining: 0,
      estimated_loops_remaining: 0,
      stages_remaining: 0,
      pending_approvals: 1,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 2,
      completion_percent: 1,
      next_cycle_type: "update_loop",
      reviewer_action_required: "review_ui_usability_pass_and_route_follow_on",
      notes: "awaiting review",
    },
    rows: [],
  },
  archive_register: { version: "ArchiveRegisterV1", row_count: 5, update_count: 0, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
  topology: { version: "TopologySnapshotV1", namespaces: [], boundaries: [] },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "Harness",
    architecture_goals: [],
    active_objective_count: 1,
    active_objectives: [{ goal: "Improve operator usability", in_scope: "Cycle 039 governance surfaces" }],
    phase_status_summary: { completed: 6, pending: 0, other: 0 },
  },
  service_inventory: {
    version: "ServiceInventoryV1",
    planned_count: 1,
    implemented_count: 1,
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
      path: "docs/exec_plans/updates/active/plan_2026-03-27_p0_s00_cycle_039_hup0014_ui_usability_pass.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-27T00:00:00.000Z",
    pending_approvals: 1,
    pending_total: 1,
    queues: [
      { queue_id: "updates", label: "Updates", active_docs: 1, actionable_docs: 1, implemented_docs: 0, rows: [] },
      { queue_id: "upgrades", label: "Upgrades", active_docs: 5, actionable_docs: 5, implemented_docs: 0, rows: [] },
      { queue_id: "tooling", label: "Tooling", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "suggestions", label: "Suggestions", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "governance", label: "Governance", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
    ],
    zero_state: { updates: false, upgrades: false, tooling: true, suggestions: true },
    reconciliation: { status: "pass", issues: [] },
  },
  route_context_coverage: {
    version: "RouteContextCoverageV1",
    router_route_count: 4,
    context_route_count: 4,
    coverage_percent: 100,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-03-27T00:00:00.000Z",
    next_action: "pause",
    pending_total: 1,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/p0-s00-cycle-039-hup0014-ui-usability-pass",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-27 | ui usability pass",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    {
      version: "DocRecordV1",
      id: "cycle-039-plan",
      relative_path: "docs/exec_plans/updates/active/plan_2026-03-27_p0_s00_cycle_039_hup0014_ui_usability_pass.md",
      section: "exec_plans",
      title: "Cycle 039 UI Usability Pass",
      status: "approved-plan",
      owner: "platform-operations",
      last_reviewed: "2026-03-27",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Cycle 039 UI Usability Pass", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 100,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Cycle 039 UI Usability Pass",
    },
    {
      version: "DocRecordV1",
      id: "hup-0014-plan",
      relative_path: "docs/exec_plans/upgrades/active/plan_2026-03-27_hup0014_harness_vnext_upgrade_package.md",
      section: "exec_plans",
      title: "HUP-0014 Upgrade Package",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-27",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "HUP-0014 Upgrade Package", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 100,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# HUP-0014 Upgrade Package",
    },
    {
      version: "DocRecordV1",
      id: "commissioning-plan",
      relative_path: "docs/exec_plans/commissioning/active/plan_2026-03-22_p5_release_exit_and_sandbox_testing.md",
      section: "exec_plans",
      title: "Release Exit Commissioning Plan",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-22",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Release Exit Commissioning Plan", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 100,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Release Exit Commissioning Plan",
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
    version: "TrackerSnapshotV6",
    generated_at: "2026-03-27T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    execution_host_summary: "Linux local host",
  },
  assistant_runtimes: {
    codex_cli: { availability_status: "available" },
    claude_code: { availability_status: "available" },
  },
  remote_ssh: {
    mode: "guarded",
  },
};

describe("home page", () => {
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

  it("surfaces current active work and the pending human gate", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/home"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Current Active Work")).toBeInTheDocument();
    });

    expect(screen.getByText("HUP-0014 Upgrade Package")).toBeInTheDocument();
    expect(screen.getByText("Cycle 039 UI Usability Pass")).toBeInTheDocument();
    expect(screen.getByText("Release Exit Commissioning Plan")).toBeInTheDocument();
    expect(screen.getByText("cycle_039_hup0014_ui_usability_pass")).toBeInTheDocument();
  });
});
