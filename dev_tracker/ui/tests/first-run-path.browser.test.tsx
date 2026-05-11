import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-17T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 12,
    docs_human_owned_context: 1,
    docs_system_managed: 9,
    docs_generated: 2,
    phase_count: 4,
    stage_count: 8,
    stage_done_count: 6,
    loop_run_count: 32,
    open_gap_count: 0,
    changelog_entry_count: 32,
    awaiting_human_review_count: 0,
    implemented_feature_count: 9,
    active_guidance_count: 3,
    estimated_cycles_remaining: 1,
    estimated_loops_remaining: 1,
    archive_entry_count: 1,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: {
    version: "LoopStateV1",
    run_count: 32,
    last_run_id: "cycle_032_hup0010_mvp_sandbox_closeout",
    last_plan_file: "report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md",
    last_result: "success",
    halt_reason: "await_next_scope",
    next_action: "target_next_project_repo",
    history: [],
  },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 32, awaiting_human_review_count: 0, approved_count: 32, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 9, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 3, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 1, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 1,
    latest_estimated_loops_remaining: 1,
    latest: {
      gate_id: "HGS-032",
      date: "2026-03-17",
      cycle_id: "cycle_032_hup0010_mvp_sandbox_closeout",
      loop_id: "loop_hup0010_builder_mvp",
      cycles_completed: 32,
      estimated_cycles_remaining: 1,
      estimated_loops_remaining: 1,
      stages_remaining: 1,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0.96,
      next_cycle_type: "commissioning_loop",
      reviewer_action_required: "ready_for_next_scope",
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
    phase_status_summary: { completed: 2, pending: 0, other: 0 },
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
      title: "Report",
      path: "docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-17T00:00:00.000Z",
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
    generated_at: "2026-03-17T00:00:00.000Z",
    next_action: "continue",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/p2-s4-builder-loop-simplification",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-17 | beta closeout",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    {
      version: "DocRecordV1",
      id: "quick-start",
      relative_path: "docs/11_ops/quick_start.md",
      section: "11_ops",
      title: "Quick Start",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-17",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Quick Start", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 10,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Quick Start",
    },
    {
      version: "DocRecordV1",
      id: "visual-reference",
      relative_path: "docs/design_docs/project_builder_visual_reference.md",
      section: "design_docs",
      title: "Project Builder Visual Reference",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-17",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Project Builder Visual Reference", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 10,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Project Builder Visual Reference",
    },
    {
      version: "DocRecordV1",
      id: "builder-runbook",
      relative_path: "docs/11_ops/project_builder_runbook.md",
      section: "11_ops",
      title: "Project Builder Runbook",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-17",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Project Builder Runbook", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 10,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Project Builder Runbook",
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
    generated_at: "2026-03-17T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    bind_host: "127.0.0.1",
    ui_port: 5273,
    preferred_urls: ["http://localhost:5273/"],
    browser_access_summary: "Use localhost, WSL browser access, or SSH local port forwarding.",
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
  existing_project_mode_enabled: true,
  known_repos: [],
  recent_operations: [],
};

const mockBuilderProviders = {
  version: "BuilderProviderListV1",
  providers: [
    {
      provider_id: "none",
      label: "Deterministic Local",
      capabilities: ["deterministic_fallback"],
      availability_status: "available",
      detail: "ok",
      default_model: "deterministic-v1",
    },
  ],
};

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

function stubFirstRunFetch() {
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
      if (url.includes("/api/builder/status")) {
        return new Response(JSON.stringify(mockBuilderStatus), { status: 200 });
      }
      if (url.includes("/api/builder/providers")) {
        return new Response(JSON.stringify(mockBuilderProviders), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }),
  );
}

test("renders quick start for the canonical first-run path in browser mode", async () => {
  stubFirstRunFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/deploy/quick-start"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(
    screen.getByRole("main").getByText(
      "Guided first-run onboarding for the current deploy flow. Learn the route order, preview a safe example, and keep the longer runbook as secondary help.",
    ),
  ).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Quick Start → Readiness → Deploy Map → Builder → Verify")).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Dismiss tutorial" })).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Deploy Example", { exact: true })).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("link", { name: "Preview Builder Example" })).toBeVisible();
});

test("supports dismissing and explicitly resuming the guided quick-start tutorial", async () => {
  stubFirstRunFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/deploy/quick-start"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("button", { name: "Dismiss tutorial" })).toBeVisible();
  await screen.getByRole("button", { name: "Dismiss tutorial" }).click();
  await expect.element(
    screen.getByText("Tutorial dismissed. Open Quick Start to resume the guided walkthrough."),
  ).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Resume Tutorial" })).toBeVisible();
  await screen.getByRole("button", { name: "Resume Tutorial" }).click();
  await expect.element(screen.getByRole("button", { name: "Dismiss tutorial" })).toBeVisible();
});

test("renders deploy map for the canonical first-run path in browser mode", async () => {
  stubFirstRunFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/deploy/map"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByRole("button", { name: /Current Project Sidecar/i })).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("heading", { name: "Baseline Harness Tree", level: 3 })).toBeVisible();
});

test("renders builder for the canonical first-run path in browser mode", async () => {
  stubFirstRunFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/deploy/builder"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByRole("heading", { name: "Target Repo", level: 3 })).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("heading", { name: "Project Context", level: 3 })).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("heading", { name: "Deploy Harness", level: 3 })).toBeVisible();
  await expect.element(screen.getByRole("main").getByText(/Allowlisted root:/)).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Explainability: Flow Map And Payload Fill")).toBeVisible();
});
