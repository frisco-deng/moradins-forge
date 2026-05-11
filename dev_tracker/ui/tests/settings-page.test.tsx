import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
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
  qa_signals: {
    version: "QaSignalsV1",
    generated_at: "2026-03-02T00:00:00.000Z",
    engineer_entry_guard: { status: "pass", detail: {} },
    branch_hygiene: { status: "pass", detail: {} },
    documentation_review: { status: "warn", detail: { reason: "required_keys_missing_or_empty" } },
  },
  git: {
    version: "GitStateV1",
    branch: "harness/v2-closeout",
    short_sha: "abc123",
    last_commit: "abc123 | 2026-03-02 | settings qa",
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

describe("settings page", () => {
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

  it("renders user preference controls and system-status link", async () => {
    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/settings/preferences"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Beta Access Model")).toBeInTheDocument();
    });

    expect(screen.getByText("Beta Access Model")).toBeInTheDocument();
    expect(screen.getByText("Assistant Runtimes")).toBeInTheDocument();
    expect(screen.getByText("Show tooltips")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open System Status" })).toBeInTheDocument();
  });

  it(
    "saves SSH profiles for builder and system-status selection",
    async () => {
      const user = userEvent.setup();

    render(
      <TrackerProvider>
        <MemoryRouter initialEntries={["/settings/preferences"]}>
          <App />
        </MemoryRouter>
      </TrackerProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Saved SSH Profiles")).toBeInTheDocument();
    });

    await user.type(screen.getAllByLabelText("Profile Label")[0], "Staging Sidecar");
    await user.type(screen.getAllByLabelText("Host")[0], "ops.example.internal");
    await user.type(screen.getAllByLabelText("User")[0], "deployer");
    await user.clear(screen.getAllByLabelText("Port")[0]);
    await user.type(screen.getAllByLabelText("Port")[0], "2222");
    await user.type(screen.getAllByLabelText("Allowlisted Root")[0], "/srv/projects");
    await user.selectOptions(screen.getAllByLabelText("Auth Method")[0], "pem_path");
    await user.type(screen.getAllByLabelText("PEM Path")[0], "/keys/deploy.pem");
    await user.click(screen.getAllByRole("button", { name: "Save SSH Profile" })[0]);

    await waitFor(() => {
      expect(screen.getAllByText("Staging Sidecar").length).toBeGreaterThan(0);
    });

    const preferredProfile = screen.getAllByLabelText("Preferred SSH Profile")[0] as HTMLSelectElement;
    expect(preferredProfile.value).not.toBe("");
    expect(screen.getByText("PEM: /keys/deploy.pem")).toBeInTheDocument();
    const persisted = JSON.parse(localStorage.getItem("moradin_forge_workbench_settings_v1") ?? "{}");
    expect(Array.isArray(persisted.sshProfiles)).toBe(true);
    expect(persisted.sshProfiles[0]?.label).toBe("Staging Sidecar");
    expect(persisted.sshProfiles[0]?.auth_method).toBe("pem_path");
    expect(persisted.defaultSshProfileId).toBeTruthy();
    },
    10_000,
  );
});
