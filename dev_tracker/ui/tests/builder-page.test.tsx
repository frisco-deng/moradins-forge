import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { OVERVIEW_ACTIVE_PROJECT_KEY } from "../src/lib/overview-project";
import { TrackerProvider } from "../src/lib/tracker-context";

const mockSnapshot = {
  version: "TrackerSnapshotV4",
  generated_at: "2026-03-02T00:00:00.000Z",
  repo_root: "/repo",
  summary: {
    docs_total: 10,
    docs_non_generated: 2,
    docs_generated: 8,
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
      date: "2026-03-02",
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
      path: "docs/exec_plans/commissioning/completed/dev_tracker_ui_reorganization_update_plan_2026-02-24.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
  },
  git: {
    version: "GitStateV1",
    branch: "harness/bootstrap",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-02 | bootstrap",
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
    generated_at: "2026-03-02T00:00:00.000Z",
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

describe("builder page", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.setItem(
      "moradin_forge_workbench_settings_v1",
      JSON.stringify({
        ambientBackground: true,
        reducedMotion: false,
        theme: "dark",
        tooltipsEnabled: true,
        preferredAssistant: "codex_cli",
        defaultDiscoveryProvider: "none",
        defaultDiscoveryModel: "",
        defaultSshProfileId: "ssh-profile-1",
        sshProfiles: [
          {
            id: "ssh-profile-1",
            label: "Remote Builder",
            target_id: "remote-builder",
            connection_mode: "ssh",
            host: "remote.example",
            user: "ops",
            port: 22,
            allowlisted_root: "/srv/work",
            profile_label: "remote-builder",
            auth_method: "ssh_agent",
            pem_path: "",
            known_hosts_mode: "strict",
          },
        ],
      }),
    );
    localStorage.setItem(OVERVIEW_ACTIVE_PROJECT_KEY, "existing-project");
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
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
      if (url.includes("/api/builder/providers")) {
        return new Response(
          JSON.stringify({
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
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/builder/repo-completeness")) {
        return new Response(
          JSON.stringify({
            version: "BuilderRepoCompletenessResponseV1",
            target_repo: "existing-project",
            profile: "harness_core",
            checked_at: "2026-03-02T12:30:00.000Z",
            summary: {
              total: 3,
              pass_count: 2,
              missing_count: 1,
            },
            groups: [
              {
                group_id: "goal",
                label: "Goal Coverage",
                checks: [
                  {
                    check_id: "goal-project-spec",
                    label: "Project goal artifact exists",
                    status: "missing",
                    detail: "not found",
                    path: "docs/product_specs",
                  },
                ],
              },
            ],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/builder/create-local-repo")) {
        return new Response(
          JSON.stringify({
            version: "CreateLocalRepoResponseV1",
            status: "created",
            repo_path: "<LOCAL_PROJECTS_ROOT>/demo-project",
            message: "ok",
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/discovery/session/start")) {
        return new Response(
          JSON.stringify({
            version: "DiscoverySessionV1",
            session_id: "disc_20260302_123000_abcd12",
            status: "intake",
            created_at: "2026-03-02T12:30:00.000Z",
            updated_at: "2026-03-02T12:30:00.000Z",
            intake: {
              input_mode: "onboarding",
              project_prompt: "",
              project_goal: "Goal",
              users: "Users",
              constraints: "",
              timeline: "",
              integrations: "",
              compliance: "",
              deployment_target: "",
              other_context: "",
            },
            questions: [],
            answers: {},
            synthesis: null,
            approval: {
              required: true,
              approved: false,
              approval_artifact_path: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/approval_required.md",
            },
            artifacts: {
              session_json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/session.json",
            },
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/discovery/session/generate")) {
        return new Response(
          JSON.stringify({
            version: "DiscoverySessionV1",
            session_id: "disc_20260302_123000_abcd12",
            status: "synthesized",
            created_at: "2026-03-02T12:30:00.000Z",
            updated_at: "2026-03-02T12:31:00.000Z",
            intake: {
              input_mode: "onboarding",
              project_prompt: "",
              project_goal: "Goal",
              users: "Users",
              constraints: "",
              timeline: "",
              integrations: "",
              compliance: "",
              deployment_target: "",
              other_context: "Legacy monorepo with strict approvals",
            },
            questions: [],
            answers: {},
            synthesis: {
              summary: "Build a repo-specific harness deployment path with approval gates.",
              recommended_profile: "web_app",
              must_haves: ["Approval-safe bootstrap", "Project-specific docs"],
              open_questions: [],
              product_spec: {
                intent: "Goal",
                target_users: ["Users"],
                constraints: ["Deterministic checks"],
                milestones: ["Phase 1"],
              },
              design: {
                components: ["UI", "Control API"],
                data_flows: ["Discovery to deploy"],
                risks: ["Scope creep"],
              },
              plan: {
                workstreams: ["Deploy harness", "Plan phases"],
                initial_backlog: ["Hydrate docs", "Create phase plan"],
              },
            },
            approval: {
              required: true,
              approved: false,
              approval_artifact_path: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/approval_required.md",
            },
            artifacts: {
              session_json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/session.json",
              synthesis_markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/synthesis.md",
            },
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/builder/generate-from-discovery")) {
        return new Response(
          JSON.stringify({
            version: "GenerateProjectRepoResponseV1",
            status: "created",
            destination_path: "<LOCAL_PROJECTS_ROOT>/demo-project",
            profile: "web_app",
            session_id: "disc_20260302_123000_abcd12",
            harness_seed_version: "0.1.0",
            generated_files: ["README.md", "docs/00_overview/implementation_phases.md"],
            template_fill_map_artifact_paths: {
              json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/template_fill_map.json",
              markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/template_fill_map.md",
            },
            validation: {
              status: "pass",
              checks: [{ name: "seed", status: "pass", detail: "ok" }],
            },
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/discovery/session/build-follow-on-plan")) {
        return new Response(
          JSON.stringify({
            version: "DiscoveryFollowOnPlanResponseV1",
            session_id: "disc_20260302_123000_abcd12",
            target_repo: "demo-project",
            workflow_type: "new_project",
            selected_profile: "web_app",
            generated_at: "2026-03-02T12:32:00.000Z",
            phase_plan: {
              summary: "Three-phase rollout for demo-project.",
              next_recommended_phase_id: "phase_1",
              phases: [
                {
                  phase_id: "phase_1",
                  title: "Hydrate Harness And Lock Scope",
                  objective: "Hydrate the repo and lock scope.",
                  deliverables: ["Fill placeholders", "Align docs"],
                  execution_focus: "Keep edits bounded.",
                },
                {
                  phase_id: "phase_2",
                  title: "Build The Core Project Path",
                  objective: "Build the main path.",
                  deliverables: ["Implement core flow"],
                  execution_focus: "Stay scoped.",
                },
                {
                  phase_id: "phase_3",
                  title: "Validate And Prepare Rollout",
                  objective: "Validate and prepare rollout.",
                  deliverables: ["Run checks"],
                  execution_focus: "Capture evidence.",
                },
              ],
            },
            alignment_state: {
              version: "AlignmentStateV1",
              generated_at: "2026-03-02T12:32:00.000Z",
              session_id: "disc_20260302_123000_abcd12",
              target_repo: "demo-project",
              workflow_type: "new_project",
              selected_profile: "web_app",
              target_mode: "local",
              target_path: "<LOCAL_PROJECTS_ROOT>/demo-project",
              locked_project_goal: "Goal",
              approval_state: "pending",
              next_recommended_phase_id: "phase_1",
              source_breakdown: {
                seed_template: 4,
                profile_overlay: 1,
                user_filled: 2,
                scan_derived: 1,
                manual_required: 0,
              },
              summary: {
                satisfied_count: 3,
                manual_required_count: 1,
                missing_count: 0,
                deferred_count: 0,
                critical_count: 1,
                high_count: 0,
                medium_count: 0,
                low_count: 0,
                overall_status: "critical",
              },
              next_recommended_action: {
                item_id: "approval_gate",
                label: "Resolve discovery approval gate",
                route: "/deploy/builder",
                next_action: "Mark the approval artifact before generation, deploy continuation, or assistant-backed alignment review.",
              },
              items: [],
            },
            prompts: [
              {
                prompt_id: "bootstrap_hydration",
                title: "Bootstrap Hydration",
                summary: "Hydrate the harness.",
                prompt: "Hydrate the harness for demo-project.",
              },
              {
                prompt_id: "phase_planning",
                title: "Build Project Phases",
                summary: "Plan the phases.",
                prompt: "Plan the phases for demo-project.",
              },
              {
                prompt_id: "phase_1_execution",
                title: "Implement Phase 1",
                summary: "Implement only phase 1.",
                prompt: "Implement only phase_1 for demo-project.",
              },
              {
                prompt_id: "run_all_phases",
                title: "Run All Phases",
                summary: "Run the full phase sequence.",
                prompt: "Run all phases for demo-project.",
              },
            ],
            artifact_paths: {
              bootstrap_prompt_markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/bootstrap_prompt.md",
              phase_plan_json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/phase_plan.json",
              phase_plan_markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/phase_plan.md",
              execution_prompts_json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/execution_prompts.json",
              execution_prompts_markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/execution_prompts.md",
              alignment_state_json: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/alignment_state.json",
              alignment_state_markdown: "Harness/artifacts/control/discovery_sessions/disc_20260302_123000_abcd12/alignment_state.md",
            },
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/builder/remote/ssh/execute")) {
        return new Response(
          JSON.stringify({
            version: "RemoteSshExecuteResponseV1",
            status: "pass",
            command: "ls -- 'existing-project/.moradins-harness'",
            stdout: "AGENTS.md\nREADME.md\n",
            stderr: "",
            exit_code: 0,
          }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    });

    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("renders the staged builder flow and builds follow-on prompts from structured intake", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/builder"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    expect(
      await screen.findByRole("heading", { level: 2, name: "Methodical multi-repo harness control" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Allowlisted root:/)).toBeInTheDocument();

    expect(screen.getByRole("heading", { level: 3, name: "Target Repo" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Project Context" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Deploy Harness" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Build Project Phases" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Run Phase Prompt" })).toBeInTheDocument();
    expect(screen.getByText("current project existing-project")).toBeInTheDocument();

    const explainabilitySummary = screen.getByText("Explainability: Flow Map And Payload Fill");
    const explainabilityDetails = explainabilitySummary.closest("details");
    expect(explainabilityDetails).not.toHaveAttribute("open");

    const advancedSummary = screen.getByText("Advanced: Repo Utilities And Remote Checks");
    const advancedDetails = advancedSummary.closest("details");
    expect(advancedDetails).not.toHaveAttribute("open");

    await user.click(advancedSummary);
    expect(advancedDetails).toHaveAttribute("open");
    expect(screen.getByLabelText("Repo Name")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Repo Name"), "demo-project");
    await user.click(screen.getByRole("button", { name: "Create Repo" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/builder/create-local-repo",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    await user.type(screen.getByLabelText("Destination Repo"), "demo-project");
    await user.type(screen.getByLabelText("Project Goal"), "Goal");
    await user.type(screen.getByLabelText("Users"), "Users");
    await user.type(screen.getByLabelText("Other Context"), "Legacy monorepo with strict approvals");
    await user.click(screen.getByRole("button", { name: "Start Discovery Session" }));

    await waitFor(() => {
      expect(screen.getByText(/session disc_20260302_123000_abcd12/i)).toBeInTheDocument();
    });

    const discoveryStartCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/discovery/session/start"));
    const discoveryStartBody = JSON.parse(String(discoveryStartCall?.[1]?.body ?? "{}"));
    expect(discoveryStartBody.intake.other_context).toBe("Legacy monorepo with strict approvals");

    await user.click(screen.getByRole("button", { name: "Generate Questions / Synthesis" }));

    await waitFor(() => {
      expect(screen.getByText(/Build a repo-specific harness deployment path/)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Generate Project Repo" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/builder/generate-from-discovery",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    await user.click(screen.getByRole("button", { name: "Build Project Phases" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/discovery/session/build-follow-on-plan",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    expect(screen.getByRole("button", { name: /Bootstrap Hydration/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Implement Phase 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run All Phases/i })).toBeInTheDocument();
    expect(screen.getByText("Alignment Summary")).toBeInTheDocument();
    expect(screen.getByText(/Mark the approval artifact before generation/i)).toBeInTheDocument();
  });

  it("reuses the pinned current project for the current-project workflow", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/deploy/builder"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { level: 3, name: "Target Repo" })[0]).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("button", { name: /Current Project/i })[0]);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Use Current Selected Project" })[0]).toBeEnabled();
    });
    await user.click(screen.getAllByRole("button", { name: "Use Current Selected Project" })[0]);

    expect(screen.getByText("Current Selected Project")).toBeInTheDocument();
    expect(screen.getAllByText("using pinned project")[0]).toBeInTheDocument();
  });

  it("targets the selected repo when checking a remote sidecar", async () => {
    const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/builder"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { level: 3, name: "Target Repo" })[0]).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("button", { name: /Current Project/i })[0]);
    await user.selectOptions(screen.getAllByLabelText("Project Target")[0], "existing-project");
    await user.selectOptions(screen.getAllByLabelText("Deploy Location")[0], "remote_ssh");
    await user.click(screen.getAllByText("Advanced: Repo Utilities And Remote Checks")[0]);
    await user.click(screen.getByRole("button", { name: "Check Sidecar" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/builder/remote/ssh/execute",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            target: {
              id: "ssh-profile-1",
              label: "Remote Builder",
              target_id: "remote-builder",
              connection_mode: "ssh",
              host: "remote.example",
              user: "ops",
              port: 22,
              allowlisted_root: "/srv/work",
              profile_label: "remote-builder",
              auth_method: "ssh_agent",
              pem_path: "",
              known_hosts_mode: "strict",
            },
            command: "ls -- 'existing-project/.moradins-harness'",
          }),
        }),
      );
    });
  });
});
