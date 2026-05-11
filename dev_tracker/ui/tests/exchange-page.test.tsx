import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExchangePage } from "../src/pages/ExchangePage";

const mockUseTracker = vi.hoisted(() => vi.fn());

vi.mock("../src/lib/tracker-context", () => ({
  useTracker: () => mockUseTracker(),
}));

const snapshot = {
  summary: {
    estimated_cycles_remaining: 2,
    estimated_loops_remaining: 1,
  },
  changelog: {
    awaiting_human_review_count: 1,
    approved_count: 1,
    rows: [
      {
        entry_id: "CHG-100",
        cycle_id: "cycle_100",
        phase_stage: "p1-s1",
        change_type: "update",
        summary: "Updated policy coverage docs.",
        docs_updated: "docs/12_governance/policy.md",
        human_gate_decision: "pending",
        approval_ref: "gate://cycle_100",
        approval_status: "awaiting_human_review",
      },
    ],
  },
  current_features: {
    pending_count: 1,
    rows: [
      {
        feature_id: "FEAT-100",
        capability: "Policy review routing",
        source_phase_stage: "p1-s1",
        owner: "ops",
        evidence_link: "docs/11_ops/evidence.md",
        status: "pending",
      },
    ],
  },
  current_guidance: {
    active_count: 1,
    rows: [
      {
        guidance_id: "GUIDE-100",
        rule: "Require review queue checks before release",
        enforcement_anchor: "docs/12_governance/index.md",
        operator_action: "review",
        status: "active",
      },
    ],
  },
  loop_processes: {
    row_count: 1,
    rows: [
      {
        process_id: "LP-100",
        process_type: "approval",
        trigger: "review queue update",
        steps_summary: "review -> approve -> merge",
        required_artifacts: "approval note",
        human_gate: "required",
        next_cycle_rule: "continue",
      },
    ],
  },
  archive_register: {
    row_count: 1,
    update_count: 3,
    upgrade_review_count: 1,
    suggestion_count: 2,
  },
  human_gate_stats: {
    latest: {
      estimated_cycles_remaining: 2,
      estimated_loops_remaining: 1,
    },
  },
  capability_gaps: {
    open_count: 1,
  },
  git: {
    branch: "harness/exchange-ui",
  },
  docs: [
    {
      id: "doc-update-1",
      title: "Queued Update Plan",
      relative_path: "docs/exec_plans/updates/active/upd_refresh_policy.md",
      status: "draft",
      owner: "ops",
    },
    {
      id: "doc-upgrade-1",
      title: "Queued Upgrade Review",
      relative_path: "docs/exec_plans/upgrades/active/upg_tracker_shell.md",
      status: "draft",
      owner: "ops",
    },
    {
      id: "doc-tooling-1",
      title: "Tooling Alignment",
      relative_path: "docs/exec_plans/tooling/active/tool_queue.md",
      status: "draft",
      owner: "ops",
    },
    {
      id: "doc-suggestion-1",
      title: "Queued Suggestion",
      relative_path: "docs/exec_plans/implementation/active/sug_exchange_refactor.md",
      status: "draft",
      owner: "ops",
    },
    {
      id: "doc-commissioning-1",
      title: "Release Exit Commissioning Plan",
      relative_path: "docs/exec_plans/commissioning/active/plan_2026-03-22_p5_release_exit_and_sandbox_testing.md",
      status: "approved",
      owner: "ops",
    },
    {
      id: "doc-archive-1",
      title: "Harness vNext Inputs Archive",
      relative_path: "docs/archive/integration/2026-03-27_harness_vnext_inputs/index.md",
      status: "archived",
      owner: "ops",
    },
  ],
  review_queue: {
    pending_approvals: 1,
    pending_total: 1,
  },
} as const;

describe("exchange page", () => {
  beforeEach(() => {
    class IntersectionObserverMock {
      observe() {}

      unobserve() {}

      disconnect() {}
    }

    vi.stubGlobal("IntersectionObserver", IntersectionObserverMock);
    mockUseTracker.mockReturnValue({
      snapshot,
      settings: {
        theme: "dark",
        ambientBackground: true,
        reducedMotion: false,
        tooltipsEnabled: true,
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders activity-first review context", async () => {
    render(
      <MemoryRouter>
        <ExchangePage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Current Governed Work")).toBeInTheDocument();
    expect(screen.getByText("Rolling change feed for the work that actually moved.")).toBeInTheDocument();
    expect(screen.getByText("Rolling Change Feed")).toBeInTheDocument();
    expect(screen.getByText("Open Review Queue")).toBeInTheDocument();
    expect(screen.getByText("Queued Update Plan")).toBeInTheDocument();
    expect(screen.getByText("Queued Upgrade Review")).toBeInTheDocument();
    expect(screen.getByText("1 pending approvals")).toBeInTheDocument();
    expect(screen.queryByText("Animated Governance Feed")).toBeNull();
  });
});
