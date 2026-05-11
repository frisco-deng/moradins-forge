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
    docs_total: 12,
    docs_human_owned_context: 1,
    docs_system_managed: 9,
    docs_generated: 2,
    phase_count: 4,
    stage_count: 8,
    stage_done_count: 5,
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
  phases: {
    version: "PhaseBoardV1",
    phase_count: 4,
    stage_count: 8,
    stage_done_count: 5,
    phases: [
      { phase_number: 1, title: "Contract", phase_status: "completed", stages: [], done_when: [], checklist_total: 1, checklist_done: 1, completion: 1 },
      { phase_number: 2, title: "Builder", phase_status: "completed", stages: [], done_when: [], checklist_total: 1, checklist_done: 1, completion: 1 },
      { phase_number: 3, title: "Polish", phase_status: "in_progress", stages: [], done_when: [], checklist_total: 2, checklist_done: 1, completion: 0.5 },
      { phase_number: 4, title: "Review", phase_status: "pending", stages: [], done_when: [], checklist_total: 1, checklist_done: 0, completion: 0 },
    ],
  },
  loop_state: {
    version: "LoopStateV1",
    run_count: 31,
    last_run_id: "cycle_031",
    last_plan_file: "plan.md",
    last_result: "success",
    halt_reason: "beta_integration_followup_required",
    next_action: "execute_hup0010_beta_integration_track",
    history: [],
  },
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
      date: "2026-03-08",
      cycle_id: "cycle_031",
      loop_id: "loop_hup0010",
      cycles_completed: 31,
      estimated_cycles_remaining: 2,
      estimated_loops_remaining: 1,
      stages_remaining: 3,
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
    active_objectives: [
      {
        objective_id: "OBJ-1",
        goal: "Finish beta",
        in_scope: "Overview polish",
        out_of_scope: "Registry work",
        stop_conditions: "Reviewer signoff",
      },
    ],
    phase_status_summary: { completed: 2, pending: 2, other: 0 },
  },
  service_inventory: {
    version: "ServiceInventoryV1",
    planned_count: 3,
    implemented_count: 2,
    planned_only_count: 1,
    unmapped_implementation_count: 0,
    rows: [
      {
        domain: "control",
        service: "builder",
        phase_target: "Phase 3",
        implementation_surface: "ui",
        status: "implemented",
      },
      {
        domain: "control",
        service: "deploy-map",
        phase_target: "Phase 3",
        implementation_surface: "ui",
        status: "implemented",
      },
      {
        domain: "ops",
        service: "system-status",
        phase_target: "Phase 4",
        implementation_surface: "ui",
        status: "planned_only",
      },
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
      path: "docs/exec_plans/commissioning/active/plan_2026-03-07_hup0010_beta_integration_track.md",
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
    generated_at: "2026-03-08T00:00:00.000Z",
    next_action: "pause",
    pending_total: 0,
    project_review: [],
    harness_review: [],
    notes: [],
  },
  git: {
    version: "GitStateV1",
    branch: "harness/ui-polish",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-08 | overview progress",
    dirty: false,
    markdown_changed_count: 0,
    markdown_changed_files: [],
    grouped_by_section: {},
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
    generated_at: "2026-03-08T00:00:00.000Z",
    summary: {},
  },
  ui_access: {
    runtime_mode: "linux",
    bind_host: "127.0.0.1",
    ui_port: 9100,
    preferred_urls: ["http://localhost:9100/"],
    browser_access_summary: "Use localhost.",
    remote_ssh_tunnel_example: "ssh -L 9100:127.0.0.1:9100 linux-box",
    execution_host_summary: "Assistant commands run on the Linux host that launched this harness.",
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
      detail: "codex command detected",
    },
    claude_code: {
      assistant: "claude_code",
      label: "Claude Code CLI",
      command: "claude",
      args: ["--print"],
      terminal_command_template: "printf '%s\\n' '<paste prompt here>' | claude --print",
      availability_status: "unavailable",
      detail: "claude command not detected",
    },
  },
};

const mockBuilderStatus = {
  version: "BuilderStatusV1",
  existing_project_mode_enabled: true,
  allowlisted_root: ".builder_projects",
  path_disclosure_mode: "masked",
  scan_limits_defaults: {
    max_depth: 6,
    max_files: 5000,
  },
  project_status_history_retention: 50,
  known_repos: [
    { name: "alpha-project", path: ".builder_projects/alpha-project", git_initialized: true },
    { name: "beta-project", path: ".builder_projects/beta-project", git_initialized: false },
  ],
  recent_operations: [],
};

const historyByRepo = {
  "alpha-project": {
    version: "ProjectStatusHistoryResponseV1",
    generated_at: "2026-03-08T00:00:00.000Z",
    target_repo: "alpha-project",
    target_mode: "local",
    target_slug: "alpha-project",
    retention_max_entries: 50,
    total_entries: 2,
    entries: [
      {
        history_id: "alpha-1",
        generated_at: "2026-03-08T10:15:00.000Z",
        overall_status: "ready",
        critical_count: 0,
        high_count: 0,
        medium_count: 1,
        low_count: 2,
        action_total: 3,
        storage_path: "Harness/artifacts/control/project_status_history/alpha/latest.json",
        trend: { critical_delta: 0, high_delta: -1 },
      },
    ],
  },
  "beta-project": {
    version: "ProjectStatusHistoryResponseV1",
    generated_at: "2026-03-08T00:00:00.000Z",
    target_repo: "beta-project",
    target_mode: "local",
    target_slug: "beta-project",
    retention_max_entries: 50,
    total_entries: 1,
    entries: [
      {
        history_id: "beta-1",
        generated_at: "2026-03-08T11:45:00.000Z",
        overall_status: "attention",
        critical_count: 1,
        high_count: 1,
        medium_count: 2,
        low_count: 0,
        action_total: 5,
        storage_path: "Harness/artifacts/control/project_status_history/beta/latest.json",
        trend: { critical_delta: 1, high_delta: 1 },
      },
    ],
  },
};

const reportByRepo = {
  "alpha-project": {
    version: "ProjectStatusReportV1",
    generated_at: "2026-03-08T10:15:00.000Z",
    target_repo: "alpha-project",
    session_id: "",
    target_mode: "local",
    remote_target: null,
    target_path: ".builder_projects/alpha-project",
    summary: {
      overall_status: "ready",
      critical_count: 0,
      high_count: 0,
      medium_count: 1,
      low_count: 2,
      action_total: 3,
    },
    critical_focus: ["Review medium-priority project hygiene items"],
    domain_health: [
      { domain_id: "codebase", label: "Codebase Signals", status: "healthy", summary: "1 language signal detected." },
      { domain_id: "delivery", label: "Delivery Pipeline", status: "healthy", summary: "CI surface detected." },
      { domain_id: "quality", label: "Quality and Tests", status: "attention", summary: "Basic test signals found." },
      { domain_id: "governance", label: "Harness Governance Readiness", status: "healthy", summary: "Harness baseline checks pass." },
    ],
    actions: [
      {
        action_id: "alpha-action-1",
        severity: "medium",
        title: "Review medium-priority project hygiene items",
        description: "Basic hygiene items remain.",
        route: "/project-status",
        depends_on: [],
        source: "project_scan",
      },
    ],
    project_scan: {
      version: "ProjectBaselineScanV1",
      scanned_at: "2026-03-08T10:15:00.000Z",
      target_repo: "alpha-project",
      target_path: ".builder_projects/alpha-project",
      file_count: 10,
      detected: {
        languages: ["ts"],
        package_managers: ["npm"],
        lockfiles: ["package-lock.json"],
        ci_surfaces: ["github-actions"],
        test_surfaces: ["vitest"],
        deployment_surfaces: [],
        infra_surfaces: [],
        governance_surfaces: [],
      },
      critical_gaps: [],
      summary: {
        language_count: 1,
        package_manager_count: 1,
        ci_surface_count: 1,
        test_surface_count: 1,
        critical_gap_count: 0,
      },
    },
  },
  "beta-project": {
    version: "ProjectStatusReportV1",
    generated_at: "2026-03-08T11:45:00.000Z",
    target_repo: "beta-project",
    session_id: "",
    target_mode: "local",
    remote_target: null,
    target_path: ".builder_projects/beta-project",
    summary: {
      overall_status: "attention",
      critical_count: 1,
      high_count: 1,
      medium_count: 2,
      low_count: 0,
      action_total: 5,
    },
    critical_focus: ["Resolve baseline project gap"],
    domain_health: [
      { domain_id: "codebase", label: "Codebase Signals", status: "healthy", summary: "1 language signal detected." },
      { domain_id: "delivery", label: "Delivery Pipeline", status: "risk", summary: "No CI pipeline detected." },
      { domain_id: "quality", label: "Quality and Tests", status: "attention", summary: "No test surface detected." },
      { domain_id: "governance", label: "Harness Governance Readiness", status: "attention", summary: "2 harness baseline checks missing." },
    ],
    actions: [
      {
        action_id: "beta-action-1",
        severity: "high",
        title: "Resolve baseline project gap",
        description: "Critical project gap detected.",
        route: "/project-topology",
        depends_on: [],
        source: "project_scan",
      },
    ],
    project_scan: {
      version: "ProjectBaselineScanV1",
      scanned_at: "2026-03-08T11:45:00.000Z",
      target_repo: "beta-project",
      target_path: ".builder_projects/beta-project",
      file_count: 8,
      detected: {
        languages: ["py"],
        package_managers: ["uv"],
        lockfiles: ["uv.lock"],
        ci_surfaces: [],
        test_surfaces: [],
        deployment_surfaces: [],
        infra_surfaces: [],
        governance_surfaces: [],
      },
      critical_gaps: ["No test surface detected."],
      summary: {
        language_count: 1,
        package_manager_count: 1,
        ci_surface_count: 0,
        test_surface_count: 0,
        critical_gap_count: 1,
      },
    },
  },
};

describe("overview page", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
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
        if (url.includes("/api/builder/project-status/history")) {
          const parsed = new URL(url, "http://localhost");
          const repo = parsed.searchParams.get("target_repo") ?? "";
          return new Response(JSON.stringify(historyByRepo[repo as keyof typeof historyByRepo] ?? historyByRepo["alpha-project"]), {
            status: 200,
          });
        }
        if (url.includes("/api/builder/project-status")) {
          const body = JSON.parse(init?.body ? String(init.body) : "{}");
          const repo = String(body.target_repo ?? "");
          return new Response(JSON.stringify(reportByRepo[repo as keyof typeof reportByRepo] ?? reportByRepo["alpha-project"]), {
            status: 200,
          });
        }
        if (/\/api\/assistant\/run(?:$|\?)/.test(url)) {
          return new Response(
            JSON.stringify({
              version: "AssistantRunResponseV1",
              run_id: "assistant_run_1",
              assistant: "codex_cli",
              source_mode: "docs",
              target_repo: "beta-project",
              status: "pass",
              stage: "completed",
              prompt: "prompt",
              stdout: "ok",
              stderr: "",
              started_at: "2026-03-09T00:00:00.000Z",
              updated_at: "2026-03-09T00:00:01.000Z",
              exit_code: 0,
              artifact_paths: {
                json: "Harness/artifacts/control/assistant_runs/assistant_run_1.json",
                markdown: "Harness/artifacts/control/assistant_runs/assistant_run_1.md",
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
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("switches project workspace overview data between manager and tracked repos", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/project/manager/overview"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(within(screen.getByRole("banner")).getByRole("button", { name: "Switch project" })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("Quick View")).toBeInTheDocument();
    });
    expect(within(screen.getByRole("banner")).getByText("/repo")).toBeInTheDocument();
    expect(screen.getByText("Phases 2/4")).toBeInTheDocument();
    expect(screen.getByLabelText("Phase progress overview")).toBeInTheDocument();
    expect(screen.getByText("Stages 5/8")).toBeInTheDocument();
    expect(screen.getByLabelText("Stage progress 5 of 8")).toBeInTheDocument();
    expect(screen.getByText("63% complete")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Switch project" }));
    await user.click(screen.getByRole("button", { name: /beta-project/i }));

    await waitFor(() => {
      expect(within(screen.getByRole("banner")).getByText(".builder_projects/beta-project")).toBeInTheDocument();
    });
    expect(screen.queryByText("Phases 2/4")).not.toBeInTheDocument();
    expect(screen.getByText("Target Summary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Codex CLI runtime status/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Update" }));

    await waitFor(() => {
      expect(screen.getByText("Update: codex_cli exit=0 status=pass")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Run JSON" })).toBeInTheDocument();
  });
});
