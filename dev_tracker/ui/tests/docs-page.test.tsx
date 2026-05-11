import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-07T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 3,
    docs_human_owned_context: 1,
    docs_system_managed: 1,
    docs_generated: 1,
    phase_count: 4,
    stage_count: 8,
    stage_done_count: 4,
    loop_run_count: 31,
    open_gap_count: 0,
    changelog_entry_count: 31,
    awaiting_human_review_count: 0,
    implemented_feature_count: 10,
    active_guidance_count: 3,
    estimated_cycles_remaining: 2,
    estimated_loops_remaining: 1,
    archive_entry_count: 1,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: { version: "LoopStateV1", run_count: 31, last_run_id: "cycle_031", last_plan_file: "plan.md", last_result: "success", halt_reason: "", next_action: "", history: [] },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 31, awaiting_human_review_count: 0, approved_count: 30, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 10, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 3, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 1, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 2,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-031",
      date: "2026-03-07",
      cycle_id: "cycle_031",
      loop_id: "loop_hup0010",
      cycles_completed: 31,
      estimated_cycles_remaining: 2,
      estimated_loops_remaining: 1,
      stages_remaining: 4,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0.85,
      next_cycle_type: "commissioning_loop",
      reviewer_action_required: "rework_before_closed_beta_signoff",
      notes: "ok",
    },
    rows: [],
  },
  archive_register: { version: "ArchiveRegisterV1", row_count: 1, update_count: 0, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
  topology: { version: "TopologySnapshotV1", namespaces: [], boundaries: [] },
  project_overview: {
    version: "ProjectOverviewV1",
    mission: "Harness",
    architecture_goals: [],
    active_objective_count: 1,
    active_objectives: [],
    phase_status_summary: { completed: 1, pending: 3, other: 0 },
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
      path: "docs/exec_plans/commissioning/active/plan_2026-03-07_hup0010_beta_integration_track.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-07T00:00:00.000Z",
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
    coverage_percent: 100,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-03-07T00:00:00.000Z",
    next_action: "pause",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/beta-integration",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-07 | docs page",
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
      word_count: 120,
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
      word_count: 220,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# HUP-0014 Upgrade Package",
    },
    {
      version: "DocRecordV1",
      id: "archive-provenance",
      relative_path: "docs/archive/integration/2026-03-27_harness_vnext_inputs/index.md",
      section: "archive",
      title: "Harness vNext Inputs Archive",
      status: "archived",
      owner: "platform-operations",
      last_reviewed: "2026-03-27",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Harness vNext Inputs Archive", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 80,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Harness vNext Inputs Archive",
    },
    {
      version: "DocRecordV1",
      id: "entrypoint",
      relative_path: "docs/00_overview/engineer_entrypoint.md",
      section: "00_overview",
      title: "Engineer Entrypoint",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-07",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Engineer Entrypoint", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 40,
      has_frontmatter: true,
      classification: "human_owned_context",
      content: "# Engineer Entrypoint",
    },
    {
      version: "DocRecordV1",
      id: "quick-start",
      relative_path: "docs/11_ops/quick_start.md",
      section: "11_ops",
      title: "Quick Start",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-07",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Quick Start", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 50,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Quick Start",
    },
    {
      version: "DocRecordV1",
      id: "loop-state",
      relative_path: "Harness/artifacts/control/loop_state.md",
      section: "artifacts",
      title: "Loop State",
      status: "generated-contract",
      owner: "docs-build-pipeline",
      last_reviewed: "2026-03-07",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Loop State", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 100,
      has_frontmatter: true,
      classification: "generated",
      content: "---\ngenerated: true\n---\n# Loop State",
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
    generated_at: "2026-03-07T00:00:00.000Z",
    summary: {},
  },
};

describe("docs page", () => {
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

  it("filters docs by classification and renders the label column", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/docs"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2, name: "Docs Explorer" })).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText("Search title/path/headings/content")).toBeInTheDocument();
    expect(screen.queryByText("Active Upgrade Package")).not.toBeInTheDocument();
    expect(screen.queryByText("Archived Provenance")).not.toBeInTheDocument();
    expect(screen.getAllByText("Human-Owned Context").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByDisplayValue("All classifications"), "generated");
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: "Engineer Entrypoint" })).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Loop State" })).toBeInTheDocument();
    });
  });
});
