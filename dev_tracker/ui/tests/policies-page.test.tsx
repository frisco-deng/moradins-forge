import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const generalDocId = "ZG9jcy8wMF9vdmVydmlldy9hcmNoaXRlY3R1cmUubWQ";

const mockSnapshot = {
  version: "TrackerSnapshotV4",
  generated_at: "2026-03-03T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 3,
    docs_non_generated: 3,
    docs_generated: 0,
    phase_count: 1,
    stage_count: 1,
    stage_done_count: 0,
    loop_run_count: 1,
    open_gap_count: 0,
    changelog_entry_count: 0,
    awaiting_human_review_count: 0,
    implemented_feature_count: 0,
    active_guidance_count: 0,
    estimated_cycles_remaining: 1,
    estimated_loops_remaining: 1,
    archive_entry_count: 0,
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
  changelog: { version: "ChangelogV1", entry_count: 0, awaiting_human_review_count: 0, approved_count: 0, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 0, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 0, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 0, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 1,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-1",
      date: "2026-03-03",
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
  policies: {
    version: "PolicyDomainSummaryV1",
    domains: [
      {
        domain: "general",
        doc_count: 1,
        missing_owner_count: 1,
        missing_status_count: 1,
        stale_review_count: 1,
        doc_ids: [generalDocId],
      },
    ],
  },
  topology: { version: "TopologySnapshotV1", namespaces: [], boundaries: [] },
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
    branch: "harness/policies",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-03 | policies",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    {
      version: "DocRecordV1",
      id: generalDocId,
      relative_path: "docs/00_overview/architecture.md",
      section: "00_overview",
      title: "Architecture",
      status: "",
      owner: "",
      last_reviewed: "",
      has_frontmatter: false,
      headings: [],
      content: "# Architecture",
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
    generated_at: "2026-03-03T00:00:00.000Z",
    summary: {},
  },
};

describe("policies page", () => {
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

  it("routes review to attention docs and renders frontmatter helper", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/project/manager/governance"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Review by domain")).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("button", { name: "Review" })[0]!);

    expect(screen.getByText("Docs Needing Attention")).toBeInTheDocument();
    expect(screen.getByText("Frontmatter Draft")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Draft" })).toBeInTheDocument();
  });
});
