import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { formatPercent, loadAssistantRun, loadAssistantRuns, loadTrackerSnapshot, resolveRelatedPath } from "../src/lib/loaders";

const validSnapshotPayload = {
  version: "TrackerSnapshotV4",
  generated_at: "2026-02-24T00:00:00.000Z",
  repo_root: "/repo",
  summary: {},
  phases: { version: "PhaseBoardV1" },
  loop_state: { version: "LoopStateV1" },
  capability_gaps: { version: "CapabilityGapV1" },
  changelog: { version: "ChangelogV1" },
  current_features: { version: "CurrentFeaturesV1" },
  current_guidance: { version: "CurrentGuidanceV1" },
  loop_processes: { version: "LoopProcessesV1" },
  human_gate_stats: { version: "HumanGateStatsV1" },
  archive_register: { version: "ArchiveRegisterV1" },
  policies: { version: "PolicyDomainSummaryV1" },
  topology: { version: "TopologySnapshotV1" },
  project_overview: { version: "ProjectOverviewV1" },
  service_inventory: { version: "ServiceInventoryV1" },
  harness_help: { version: "HarnessHelpV1" },
  git: { version: "GitStateV1" },
  docs: [{ version: "DocRecordV1" }],
};

describe("frontend loader utilities", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("formats percent values", () => {
    expect(formatPercent(0.625)).toBe("63%");
  });

  it("resolves related doc paths", () => {
    expect(resolveRelatedPath("docs/03_architecture/system_context.md", "container_topology.md")).toBe(
      "docs/03_architecture/container_topology.md",
    );
    expect(resolveRelatedPath("docs/03_architecture/system_context.md", "../11_ops/codex_run_loop.md")).toBe(
      "docs/11_ops/codex_run_loop.md",
    );
  });

  it("accepts tracker snapshots and upgrades V4 payloads to V6", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(validSnapshotPayload), { status: 200 }));

    const snapshot = await loadTrackerSnapshot();
    expect(snapshot).not.toBeNull();
    expect(snapshot?.version).toBe("TrackerSnapshotV6");
    expect(snapshot?.review_queue.version).toBe("ReviewQueueV1");
    expect(snapshot?.human_review_summary.version).toBe("HumanReviewSummaryV1");
  });

  it("rejects stale tracker snapshot version markers", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          ...validSnapshotPayload,
          version: "TrackerSnapshotV3",
        }),
        { status: 200 },
      ),
    );

    const snapshot = await loadTrackerSnapshot();
    expect(snapshot).toBeNull();
  });

  it("rejects tracker snapshots missing newly required sections", async () => {
    const { harness_help: _harnessHelp, ...missingHarnessHelp } = validSnapshotPayload;

    fetchMock.mockResolvedValue(new Response(JSON.stringify(missingHarnessHelp), { status: 200 }));

    const snapshot = await loadTrackerSnapshot();
    expect(snapshot).toBeNull();
  });

  it("loads assistant activity payloads when versions match", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            version: "AssistantRunListResponseV1",
            generated_at: "2026-03-09T00:00:00.000Z",
            active_run_id: "assistant_1",
            runs: [],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            version: "AssistantRunResponseV1",
            run_id: "assistant_1",
            assistant: "codex_cli",
            source_mode: "docs",
            status: "running",
            stage: "running_cli",
            prompt: "Do work",
            stdout: "",
            stderr: "",
            started_at: "2026-03-09T00:00:00.000Z",
            updated_at: "2026-03-09T00:00:01.000Z",
            exit_code: null,
            artifact_paths: {
              json: "Harness/artifacts/control/assistant_runs/assistant_1.json",
              markdown: "Harness/artifacts/control/assistant_runs/assistant_1.md",
            },
          }),
          { status: 200 },
        ),
      );

    const runs = await loadAssistantRuns();
    const run = await loadAssistantRun("assistant_1");

    expect(runs?.version).toBe("AssistantRunListResponseV1");
    expect(run?.version).toBe("AssistantRunResponseV1");
    expect(run?.status).toBe("running");
  });
});
