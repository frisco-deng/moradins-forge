import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { OVERVIEW_ACTIVE_PROJECT_KEY } from "../src/lib/overview-project";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV4",
  generated_at: "2026-03-05T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 10,
    docs_non_generated: 3,
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
      completion_percent: 0.3,
      next_cycle_type: "implementation_loop",
      reviewer_action_required: "continue",
      notes: "ok",
    },
    rows: [],
  },
  archive_register: { version: "ArchiveRegisterV1", row_count: 0, update_count: 0, upgrade_review_count: 0, suggestion_count: 0, rows: [] },
  policies: { version: "PolicyDomainSummaryV1", domains: [] },
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
      path: "docs/exec_plans/commissioning/completed/plan.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  git: {
    version: "GitStateV1",
    branch: "main",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-05 | init",
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
    version: "TrackerSnapshotV4",
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

describe("project status page", () => {
  beforeEach(() => {
    localStorage.setItem(OVERVIEW_ACTIVE_PROJECT_KEY, "existing-project");
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
          return new Response(
            JSON.stringify({
              version: "BuilderStatusV1",
              allowlisted_root: "<LOCAL_PROJECTS_ROOT>",
              existing_project_mode_enabled: true,
              known_repos: [
                {
                  name: "existing-project",
                  path: "<LOCAL_PROJECTS_ROOT>/existing-project",
                  git_initialized: true,
                },
              ],
              recent_operations: [],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/builder/project-status/history")) {
          return new Response(
            JSON.stringify({
              version: "ProjectStatusHistoryResponseV1",
              generated_at: "2026-03-05T12:01:00.000Z",
              target_repo: "existing-project",
              target_slug: "existing-project-abcd1234",
              retention_max_entries: 50,
              total_entries: 1,
              entries: [
                {
                  history_id: "status_2026-03-05T12-00-00-000Z",
                  generated_at: "2026-03-05T12:00:00.000Z",
                  overall_status: "attention",
                  critical_count: 1,
                  high_count: 1,
                  medium_count: 1,
                  low_count: 0,
                  action_total: 3,
                  storage_path: "<REPO_ROOT>/Harness/artifacts/control/project_status_history/existing-project-abcd1234/status_2026-03-05T12-00-00-000Z.json",
                  trend: {
                    critical_delta: 0,
                    high_delta: 0,
                  },
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/builder/project-status")) {
          return new Response(
            JSON.stringify({
              version: "ProjectStatusReportV1",
              generated_at: "2026-03-05T12:00:00.000Z",
              target_repo: "existing-project",
              session_id: "disc_123",
              summary: {
                overall_status: "attention",
                critical_count: 1,
                high_count: 1,
                medium_count: 1,
                low_count: 0,
                action_total: 3,
              },
              critical_focus: ["Resolve pending approvals"],
              domain_health: [
                {
                  domain_id: "delivery",
                  label: "Delivery Pipeline",
                  status: "risk",
                  summary: "No CI pipeline configuration detected.",
                },
              ],
              actions: [
                {
                  action_id: "queue-pending-approvals",
                  severity: "critical",
                  title: "Resolve pending approvals",
                  description: "1 approval item remains open.",
                  route: "/review",
                  depends_on: [],
                  source: "review_queue.pending_approvals",
                },
              ],
              alignment_state: {
                version: "AlignmentStateV1",
                generated_at: "2026-03-05T12:00:00.000Z",
                session_id: "disc_123",
                target_repo: "existing-project",
                workflow_type: "existing_project",
                selected_profile: "internal_tooling",
                target_mode: "local",
                target_path: "<LOCAL_PROJECTS_ROOT>/existing-project",
                locked_project_goal: "Adopt Moradins Harness into the existing repo existing-project.",
                approval_state: "approved",
                next_recommended_phase_id: "phase_1",
                source_breakdown: {
                  seed_template: 8,
                  profile_overlay: 1,
                  user_filled: 2,
                  scan_derived: 3,
                  manual_required: 0,
                },
                summary: {
                  satisfied_count: 4,
                  manual_required_count: 2,
                  missing_count: 1,
                  deferred_count: 0,
                  critical_count: 1,
                  high_count: 2,
                  medium_count: 0,
                  low_count: 0,
                  overall_status: "critical",
                },
                next_recommended_action: {
                  item_id: "review_queue_pending_approvals",
                  label: "Resolve pending human approvals",
                  route: "/reviews/queue",
                  next_action: "1 approval item(s) remain open before execution should continue.",
                },
                items: [
                  {
                    item_id: "review_queue_pending_approvals",
                    label: "Resolve pending human approvals",
                    status: "manual_required",
                    severity: "critical",
                    source_type: "manual_required",
                    owner: "operator",
                    recommended_route: "/reviews/queue",
                    evidence_paths: [],
                    next_action: "1 approval item(s) remain open before execution should continue.",
                  },
                ],
              },
              project_scan: {
                version: "ProjectBaselineScanV1",
                scanned_at: "2026-03-05T12:00:00.000Z",
                target_repo: "existing-project",
                target_path: "<LOCAL_PROJECTS_ROOT>/existing-project",
                file_count: 20,
                detected: {
                  languages: ["typescript"],
                  package_managers: ["node", "npm"],
                  lockfiles: ["package-lock.json"],
                  ci_surfaces: [],
                  test_surfaces: [],
                  deployment_surfaces: [],
                  infra_surfaces: [],
                  governance_surfaces: ["README.md"],
                },
                critical_gaps: ["No CI pipeline definition detected."],
                summary: {
                  language_count: 1,
                  package_manager_count: 2,
                  ci_surface_count: 0,
                  test_surface_count: 0,
                  critical_gap_count: 1,
                },
              },
            }),
            { status: 200 },
          );
        }
        if (/\/api\/assistant\/run(?:$|\?)/.test(url)) {
          return new Response(
            JSON.stringify({
              version: "AssistantRunResponseV1",
              run_id: "assistant_run_project_status",
              assistant: "codex_cli",
              source_mode: "project_status",
              status: "pass",
              stage: "completed",
              prompt: "prompt",
              exit_code: 0,
              stdout: "ok",
              stderr: "",
              started_at: "2026-03-09T00:00:00.000Z",
              updated_at: "2026-03-09T00:00:01.000Z",
              artifact_paths: {
                json: "Harness/artifacts/control/assistant_runs/assistant_run_project_status.json",
                markdown: "Harness/artifacts/control/assistant_runs/assistant_run_project_status.md",
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
    localStorage.clear();
  });

  it("renders project status and actionable queue", async () => {
    const user = userEvent.setup();
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/deploy/status?target=existing-project&session=disc_123"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /Refresh Status Report/i })[0]).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getAllByText("Resolve pending approvals").length).toBeGreaterThan(0);
    });

    await user.click(screen.getAllByRole("button", { name: /Refresh Status Report/i })[0]);
    await waitFor(() => {
      expect(screen.getByText(/overall: attention/)).toBeInTheDocument();
    });
    expect(screen.getByText("Alignment Summary")).toBeInTheDocument();
    expect(screen.getByText(/next phase phase_1/i)).toBeInTheDocument();
    expect(screen.getByText("History (1)")).toBeInTheDocument();
    await user.click(screen.getByText("History (1)"));
    expect(screen.getByText("2026-03-05T12:00:00.000Z")).toBeInTheDocument();
  });

  it("reuses the pinned current project when verify opens without query params", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/deploy/status"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("existing-project")).toBeInTheDocument();
    });

    expect(screen.getAllByText("current project existing-project")[0]).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Use Current Selected Project" })[0]).toBeEnabled();
    await waitFor(() => {
      expect(screen.getAllByText(/overall: attention/)[0]).toBeInTheDocument();
    });
  });

  it("runs the selected assistant from the project status action bar", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.mocked(fetch);

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/deploy/status?target=existing-project&session=disc_123"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: /Refresh Status Report/i })[0]).toBeInTheDocument();
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
      expect(payload.source_mode).toBe("project_status");
      expect(payload.execution_scope).toBe("local_repo");
      expect(payload.target_repo).toBe("existing-project");
      expect(typeof payload.prompt).toBe("string");
      expect(payload.prompt.length).toBeGreaterThan(0);
    });
  });
});
