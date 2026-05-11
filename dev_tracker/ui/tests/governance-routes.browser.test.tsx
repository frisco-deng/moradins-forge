import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import App from "../src/App";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV6",
  generated_at: "2026-03-29T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 14,
    docs_human_owned_context: 1,
    docs_system_managed: 11,
    docs_generated: 2,
    phase_count: 6,
    stage_count: 14,
    stage_done_count: 14,
    loop_run_count: 40,
    open_gap_count: 0,
    changelog_entry_count: 40,
    awaiting_human_review_count: 0,
    implemented_feature_count: 14,
    active_guidance_count: 4,
    estimated_cycles_remaining: 0,
    estimated_loops_remaining: 0,
    archive_entry_count: 5,
    markdown_changed_count: 0,
  },
  phases: { version: "PhaseBoardV1", phase_count: 0, stage_count: 0, stage_done_count: 0, phases: [] },
  loop_state: {
    version: "LoopStateV1",
    run_count: 40,
    last_run_id: "cycle_039_hup0014_ui_usability_pass",
    last_plan_file: "plan_2026-03-27_p0_s00_cycle_039_hup0014_ui_usability_pass.md",
    last_result: "success",
    halt_reason: "",
    next_action: "execute_refocus_and_proof_pass",
    history: [],
  },
  capability_gaps: { version: "CapabilityGapV1", open_count: 0, in_progress_count: 0, blocked_count: 0, rows: [] },
  changelog: { version: "ChangelogV1", entry_count: 40, awaiting_human_review_count: 0, approved_count: 40, rows: [] },
  current_features: { version: "CurrentFeaturesV1", implemented_count: 14, pending_count: 0, rows: [] },
  current_guidance: { version: "CurrentGuidanceV1", active_count: 4, rows: [] },
  loop_processes: { version: "LoopProcessesV1", row_count: 1, rows: [] },
  human_gate_stats: {
    version: "HumanGateStatsV1",
    row_count: 1,
    latest_estimated_cycles_remaining: 0,
    latest_estimated_loops_remaining: 0,
    latest: {
      gate_id: "HGS-040",
      date: "2026-03-29",
      cycle_id: "cycle_040_ui_governance_gan_polish",
      loop_id: "loop_ui_governance_gan_polish",
      cycles_completed: 40,
      estimated_cycles_remaining: 0,
      estimated_loops_remaining: 0,
      stages_remaining: 0,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 2,
      completion_percent: 1,
      next_cycle_type: "update_loop",
      reviewer_action_required: "review_refocus_and_proof_results",
      notes: "proof refresh in progress",
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
    active_objectives: [{ goal: "Prove the sidecar and seed workflows", in_scope: "Cycle 040 release proof + UI polish" }],
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
      title: "Cycle 040 Plan",
      path: "docs/exec_plans/updates/active/plan_2026-03-27_p0_s00_cycle_040_ui_governance_gan_polish.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  review_queue: {
    version: "ReviewQueueV1",
    generated_at: "2026-03-29T00:00:00.000Z",
    pending_approvals: 0,
    pending_total: 0,
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
    router_route_count: 8,
    context_route_count: 8,
    coverage_percent: 100,
    missing_in_context: [],
    extra_in_context: [],
    rows: [],
  },
  human_review_summary: {
    version: "HumanReviewSummaryV1",
    generated_at: "2026-03-29T00:00:00.000Z",
    next_action: "pause",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/p0-s00-cycle-040-ui-governance-gan-polish",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-29 | refocus and proof",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
  },
  docs: [
    {
      version: "DocRecordV1",
      id: "cycle-040-plan",
      relative_path: "docs/exec_plans/updates/active/plan_2026-03-27_p0_s00_cycle_040_ui_governance_gan_polish.md",
      section: "exec_plans",
      title: "Plan 2026-03-27 P0 S00 Cycle 040 UI Governance GAN Polish",
      status: "approved-plan",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Cycle 040", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Cycle 040",
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
      headings: [{ level: 1, text: "HUP-0014", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# HUP-0014",
    },
    {
      version: "DocRecordV1",
      id: "release-latest",
      relative_path: "public_audit/release_reports_excluded/latest.md",
      section: "Harness",
      title: "Builder Release Smoke Report",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Builder Release Smoke Report", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: false,
      classification: "generated",
      content: "# Builder Release Smoke Report",
    },
    {
      version: "DocRecordV1",
      id: "seed-generation",
      relative_path: "public_audit/release_reports_excluded/seed_generation.md",
      section: "Harness",
      title: "Goal-Driven Seed Generation Report",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Goal-Driven Seed Generation Report", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: false,
      classification: "generated",
      content: "# Goal-Driven Seed Generation Report",
    },
    {
      version: "DocRecordV1",
      id: "live-adoption",
      relative_path: "public_audit/release_reports_excluded/live_adoption.md",
      section: "Harness",
      title: "First Live Adoption Report",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "First Live Adoption Report", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: false,
      classification: "generated",
      content: "# First Live Adoption Report",
    },
    {
      version: "DocRecordV1",
      id: "sandbox-matrix",
      relative_path: "public_audit/release_reports_excluded/sandbox_matrix.md",
      section: "Harness",
      title: "Sandbox Matrix Report",
      status: "approved",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Sandbox Matrix Report", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: false,
      classification: "generated",
      content: "# Sandbox Matrix Report",
    },
    {
      version: "DocRecordV1",
      id: "human-review",
      relative_path: "HUMAN_REVIEW.md",
      section: "root",
      title: "Human Review",
      status: "completed",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Human Review", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Human Review",
    },
    {
      version: "DocRecordV1",
      id: "release-tracker",
      relative_path: "Harness/artifacts/control/release_exit_tracker.md",
      section: "Harness",
      title: "Release Exit Tracker",
      status: "completed",
      owner: "platform-operations",
      last_reviewed: "2026-03-29",
      related_docs: [],
      source_refs: [],
      heading_count: 1,
      headings: [{ level: 1, text: "Release Exit Tracker", line: 1 }],
      checklist_total: 0,
      checklist_done: 0,
      word_count: 120,
      has_frontmatter: true,
      classification: "system_managed",
      content: "# Release Exit Tracker",
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
    generated_at: "2026-03-29T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    bind_host: "127.0.0.1",
    ui_port: 5273,
    preferred_urls: ["http://localhost:5273/"],
    browser_access_summary: "Use localhost or SSH local port forwarding.",
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

function stubGovernanceFetch() {
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
      return new Response("{}", { status: 200 });
    }),
  );
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

test("renders the home governance focus in browser mode", async () => {
  stubGovernanceFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/home"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByText("Current Active Work")).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("No project pinned")).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("link", { name: "Open Diagnostics" })).toBeVisible();
  await expect.element(
    screen.getByRole("main").getByText("Plan 2026-03-27 P0 S00 Cycle 040 UI Governance GAN Polish"),
  ).toBeVisible();
});

test("renders the docs governance focus in browser mode", async () => {
  stubGovernanceFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/docs"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByText("Docs Explorer")).toBeVisible();
  await expect.element(screen.getByRole("main").getByPlaceholder("Search title/path/headings/content")).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Goal-Driven Seed Generation Report")).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Active Upgrade Package")).not.toBeInTheDocument();
});

test("renders the review queue artifact set in browser mode", async () => {
  stubGovernanceFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/reviews/queue"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByText("Review Artifacts")).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("link", { name: "Seed Generation Report" })).toBeVisible();
});

test("renders activity routing in browser mode", async () => {
  stubGovernanceFetch();

  const screen = await render(
    <TrackerProvider>
      <MemoryRouter initialEntries={["/reviews/exchange"]}>
        <App />
      </MemoryRouter>
    </TrackerProvider>,
  );

  await expect.element(screen.getByRole("main").getByText("Rolling change feed for the work that actually moved.")).toBeVisible();
  await expect.element(screen.getByRole("main").getByText("Current Governed Work", { exact: true })).toBeVisible();
  await expect.element(screen.getByRole("main").getByRole("link", { name: "Open Review Queue" })).toBeVisible();
});
