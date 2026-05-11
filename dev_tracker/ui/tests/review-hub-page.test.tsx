import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV5",
  generated_at: "2026-03-05T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 12,
    docs_non_generated: 6,
    docs_generated: 6,
    phase_count: 1,
    stage_count: 1,
    stage_done_count: 0,
    loop_run_count: 2,
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
    run_count: 2,
    last_run_id: "cycle_002",
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
      date: "2026-03-05",
      cycle_id: "cycle_002",
      loop_id: "loop-main",
      cycles_completed: 2,
      estimated_cycles_remaining: 1,
      estimated_loops_remaining: 1,
      stages_remaining: 1,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0.7,
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
    mission: "Tracker",
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
      path: "docs/exec_plans/commissioning/completed/plan.md",
      guard_text: "DO NOT EXECUTE",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-05T00:00:00.000Z",
    pending_approvals: 0,
    pending_total: 0,
    queues: [
      { queue_id: "updates", label: "Updates", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "upgrades", label: "Upgrades", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "tooling", label: "Tooling", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "suggestions", label: "Suggestions", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
      { queue_id: "governance", label: "Governance", active_docs: 0, actionable_docs: 0, implemented_docs: 0, rows: [] },
    ],
    zero_state: {
      updates: true,
      upgrades: true,
      tooling: true,
      suggestions: true,
    },
    reconciliation: {
      status: "pass",
      issues: [],
    },
  },
  route_context_coverage: {
    version: "RouteContextCoverageV1",
    router_route_count: 5,
    context_route_count: 5,
    coverage_percent: 100,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-03-05T00:00:00.000Z",
    next_action: "continue",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/review-hub",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-05 | review hub",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    {
      version: "DocRecordV1",
      id: "doc-ui-update",
      relative_path: "docs/exec_plans/updates/active/plan_2026-03-27_p0_s00_cycle_039_hup0014_ui_usability_pass.md",
      title: "Cycle 039 UI Usability Pass",
      status: "approved-plan",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-hup-package",
      relative_path: "docs/exec_plans/upgrades/active/plan_2026-03-27_hup0014_harness_vnext_upgrade_package.md",
      title: "HUP-0014 Upgrade Package",
      status: "approved",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-release-tracker",
      relative_path: "Harness/artifacts/control/release_exit_tracker.md",
      title: "Release Exit Tracker",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-release-latest",
      relative_path: "public_audit/release_reports_excluded/latest.md",
      title: "Builder Release Smoke Report",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-human-review",
      relative_path: "HUMAN_REVIEW.md",
      title: "Human Review",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-live-adoption",
      relative_path: "public_audit/release_reports_excluded/live_adoption.md",
      title: "First Live Adoption Report",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-seed-generation",
      relative_path: "public_audit/release_reports_excluded/seed_generation.md",
      title: "Goal-Driven Seed Generation Report",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-sandbox-matrix",
      relative_path: "public_audit/release_reports_excluded/sandbox_matrix.md",
      title: "Sandbox Matrix Report",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-changelog",
      relative_path: "Harness/artifacts/control/changelog.md",
      title: "Changelog",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-gate-stats",
      relative_path: "Harness/artifacts/control/human_gate_stats.md",
      title: "Human Gate Stats",
      related_docs: [],
    },
    {
      version: "DocRecordV1",
      id: "doc-tech-debt",
      relative_path: "docs/exec_plans/tech-debt-tracker.md",
      title: "Tech Debt Tracker",
      related_docs: [],
    },
  ],
};

const mockStatus = {
  api: "TrackerControlStatusV1",
  runtime_state: {
    last_sync_at: "2026-03-05T00:00:00.000Z",
    last_sync_result: "success",
    last_sync_duration_ms: 30,
    sync_count: 1,
    syncing: false,
    last_error: "",
  },
  runtime_snapshot: {},
  tracker_snapshot: {
    version: "TrackerSnapshotV5",
    generated_at: "2026-03-05T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    bind_host: "127.0.0.1",
    ui_port: 5273,
    preferred_urls: ["http://localhost:5273/", "http://127.0.0.1:5273/"],
    browser_access_summary: "Open the UI on localhost when browsing from the same Linux host. If the harness host is remote, keep the UI loopback-only and use SSH local port forwarding.",
    remote_ssh_tunnel_example: "ssh -L 5273:127.0.0.1:5273 <linux-host>",
    execution_host_summary: "Assistant commands run on the Linux host that launched the harness.",
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
      detail: "codex is available on the Linux host running this harness.",
    },
    claude_code: {
      assistant: "claude_code",
      label: "Claude Code CLI",
      command: "claude",
      args: ["--print"],
      terminal_command_template: "printf '%s\\n' '<paste prompt here>' | claude --print",
      availability_status: "available",
      detail: "claude is available on the Linux host running this harness.",
    },
  },
};

describe("review hub page", () => {
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
        if (/\/api\/assistant\/run(?:$|\?)/.test(url)) {
          return new Response(
            JSON.stringify({
              version: "AssistantRunResponseV1",
              run_id: "assistant_run_review",
              assistant: "codex_cli",
              source_mode: "review",
              status: "pass",
              stage: "completed",
              prompt: "prompt",
              exit_code: 0,
              stdout: "ok",
              stderr: "",
              started_at: "2026-03-09T00:00:00.000Z",
              updated_at: "2026-03-09T00:00:01.000Z",
              artifact_paths: {
                json: "Harness/artifacts/control/assistant_runs/assistant_run_review.json",
                markdown: "Harness/artifacts/control/assistant_runs/assistant_run_review.md",
              },
            }),
            { status: 200 },
          );
        }
        return new Response("{}", { status: 200 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders structured review sections and clear queue zero-state", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/reviews/queue"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Project Review")).toBeInTheDocument();
    });

    expect(screen.getByText("Active Review Focus")).toBeInTheDocument();
    expect(screen.getByText("HUP-0014 Upgrade Package")).toBeInTheDocument();
    expect(screen.getByText("Project Review")).toBeInTheDocument();
    expect(screen.getByText("Harness Review")).toBeInTheDocument();
    expect(screen.getByText("No pending updates/upgrades/tooling suggestions.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Release Exit Tracker" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Latest Release Report" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Seed Generation Report" })).toBeInTheDocument();
  });

  it("runs the selected assistant from the review action bar", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.mocked(fetch);

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/reviews/queue"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Project Review")).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("button", { name: "Run Selected Assistant" })[0]);

    await waitFor(() => {
      const assistantCall = fetchMock.mock.calls.find(
        ([input, init]) => /\/api\/assistant\/run(?:$|\?)/.test(String(input)) && String(init?.method ?? "GET").toUpperCase() === "POST",
      );
      expect(assistantCall).toBeTruthy();
      const init = assistantCall?.[1] as RequestInit | undefined;
      const payload = JSON.parse(String(init?.body ?? "{}"));
      expect(payload.assistant).toBe("codex_cli");
      expect(payload.source_mode).toBe("review");
      expect(payload.execution_scope).toBe("manager_repo");
      expect(typeof payload.prompt).toBe("string");
      expect(payload.prompt.length).toBeGreaterThan(0);
    });
  });
});
