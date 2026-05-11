import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReadinessPage } from "../src/pages/ReadinessPage";

const readinessPayload = {
  version: "MoradinToolingReadinessV1",
  generated_at: "2026-05-03T00:00:00.000Z",
  request_only: true,
  payload_manifest: {
    manifest_path: "Harness/moradin_payload/manifest.yaml",
    payload_id: "moradin_harness_payload",
    payload_version: "0.2.0-alpha",
    include_count: 42,
    exclude_count: 4,
    sidecar_default_dir: ".moradins-harness",
  },
  summary: {
    total: 2,
    present_count: 1,
    missing_count: 1,
    manual_count: 0,
    required_missing_count: 0,
    optional_missing_count: 1,
    overall_status: "optional_attention",
  },
  groups: [
    {
      group_id: "host_baseline",
      label: "Host Baseline",
      required: true,
      summary: { total: 1, present_count: 1, missing_count: 0, manual_count: 0 },
      checks: [
        {
          tool_id: "git",
          label: "Git",
          required: true,
          status: "present",
          command: "git",
          detected_path: "/usr/bin/git",
          version: "git version 2.45.0",
          detail: "Git is available.",
          install_commands: [],
          verify_command: "git --version",
          runbook_refs: [],
        },
      ],
    },
    {
      group_id: "optional_scanners",
      label: "Optional Scanners",
      required: false,
      summary: { total: 1, present_count: 0, missing_count: 1, manual_count: 0 },
      checks: [
        {
          tool_id: "zizmor",
          label: "zizmor",
          required: false,
          status: "missing",
          command: "zizmor",
          detected_path: "",
          version: "",
          detail: "zizmor is not available.",
          install_commands: ["uv tool install zizmor"],
          verify_command: "zizmor --version",
          runbook_refs: ["docs/references/tooling_readiness_install_request_contract_v1.md"],
        },
      ],
    },
  ],
  install_guidance: [],
  artifact_roots: {
    install_requests: "Harness/artifacts/control/install_requests",
    repo_registry: "Harness/artifacts/control/repo_registry",
  },
};

const registryPayload = {
  version: "MoradinRepoRegistryV1",
  generated_at: "2026-05-03T00:00:00.000Z",
  allowlisted_root: "<LOCAL_PROJECTS_ROOT>",
  path_disclosure_mode: "masked",
  summary: {
    total_repos: 1,
    tracked_repos: 0,
    git_initialized_count: 1,
    moradin_sidecar_count: 0,
    reusable_artifact_count: 0,
  },
  repositories: [
    {
      repo_id: "manager",
      name: "moradin-harness-manager",
      scope: "manager",
      path: "<REPO_ROOT>",
      git_initialized: true,
      agents_present: true,
      moradin_sidecar_present: false,
      moradin_sidecar_path: "",
      package_managers: ["npm", "uv"],
      make_targets: ["repo-brief"],
      adapter_surfaces: {
        makefile_present: true,
        generated_tooling_present: true,
        repo_brief_target: true,
        verify_fast_target: true,
        review_ready_target: true,
      },
      artifact_reuse: {
        latest_status_report: "",
        latest_status_generated_at: "",
        project_status_slug: "",
      },
      brief: "Manager brief",
      rerun_advice: "Run make repo-brief after material changes.",
    },
  ],
  adapter_contract: {
    source_pattern: "repo-owned generated tooling adapters",
    preferred_commands: ["make repo-brief", "make verify-fast", "make review-ready"],
    artifact_root: "Harness/artifacts/control/repo_registry",
  },
};

describe("readiness page", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/moradin/readiness")) {
        return new Response(JSON.stringify(readinessPayload), { status: 200 });
      }
      if (url.includes("/api/moradin/repo-registry")) {
        return new Response(JSON.stringify(registryPayload), { status: 200 });
      }
      if (url.includes("/api/moradin/install-request")) {
        return new Response(
          JSON.stringify({
            version: "MoradinInstallRequestV1",
            request_id: "install_test",
            created_at: "2026-05-03T00:00:00.000Z",
            request_only: true,
            assistant_mode: "manual_handoff",
            operator_note: "Generated from Deploy Readiness.",
            status: "requested",
            selected_tools: [],
            commands: [],
            safety: "Moradin does not execute these commands.",
            artifact_paths: {
              json: "Harness/artifacts/control/install_requests/install_test/install_request.json",
              markdown: "Harness/artifacts/control/install_requests/install_test/install_request.md",
            },
          }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows missing tools and writes request-only install artifacts", async () => {
    render(
      <MemoryRouter>
        <ReadinessPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Readiness")).toBeInTheDocument();
    expect(screen.getAllByText("zizmor").length).toBeGreaterThan(0);
    expect(screen.getByText("uv tool install zizmor")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /create install request/i }));

    await waitFor(() => expect(screen.getByText("install_test")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/moradin/install-request",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
