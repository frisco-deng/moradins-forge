/* @vitest-environment node */

import {
  type ChildProcessWithoutNullStreams,
  spawn,
  spawnSync,
} from "node:child_process";
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(uiRoot, "..", "..");

let apiPort = 0;
let uiPort = 0;
let child: ChildProcessWithoutNullStreams | null = null;
let projectsRoot = "";
let controlRoot = "";
let discoveryDocsRoot = "";
let toolBinRoot = "";

async function findAvailablePort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("failed to resolve free port")));
        return;
      }
      const { port } = address;
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(port);
      });
    });
  });
}

async function allocatePortPair(): Promise<{ apiPort: number; uiPort: number }> {
  return {
    apiPort: await findAvailablePort(),
    uiPort: await findAvailablePort(),
  };
}

function apiUrl(pathname: string): string {
  return `http://127.0.0.1:${apiPort}${pathname}`;
}

async function waitForApiReady(timeoutMs = 20000): Promise<void> {
  await waitForApiReadyAtPort(apiPort, timeoutMs);
}

async function waitForAssistantRun(
  runId: string,
  timeoutMs = 20000,
): Promise<any> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const response = await fetch(
      apiUrl(`/api/assistant/run/${encodeURIComponent(runId)}`),
    );
    if (response.ok) {
      const payload = await response.json();
      if (payload.status === "pass" || payload.status === "fail") {
        return payload;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`assistant run ${runId} did not complete in time`);
}

async function waitForApiReadyAtPort(
  portValue: number,
  timeoutMs = 20000,
): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`http://127.0.0.1:${portValue}/api/status`);
      if (response.ok) {
        return;
      }
    } catch {
      // Retry until timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("control API did not become ready in time");
}

function isWslRuntimeForTests(): boolean {
  if (process.platform !== "linux") {
    return false;
  }
  if (process.env.WSL_DISTRO_NAME || process.env.WSL_INTEROP) {
    return true;
  }
  return os.release().toLowerCase().includes("microsoft");
}

function detectWslIpv4ForTests(): string {
  if (!isWslRuntimeForTests()) {
    return "";
  }
  const interfaces = os.networkInterfaces();
  for (const networkEntries of Object.values(interfaces)) {
    for (const entry of networkEntries ?? []) {
      const family =
        typeof entry.family === "string"
          ? entry.family
          : entry.family === 4
            ? "IPv4"
            : "";
      if (family !== "IPv4" || entry.internal) {
        continue;
      }
      if (entry.address === "127.0.0.1") {
        continue;
      }
      return entry.address;
    }
  }
  return "";
}

async function postJson(
  pathname: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<{ status: number; payload: any }> {
  const response = await fetch(apiUrl(pathname), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
  return {
    status: response.status,
    payload: await response.json(),
  };
}

async function startAndSynthesizeSession(
  inputMode: "prompt" | "onboarding" = "onboarding",
): Promise<any> {
  const start = await postJson("/api/discovery/session/start", {
    intake: {
      input_mode: inputMode,
      project_prompt:
        inputMode === "prompt"
          ? "Build an internal analytics tool with approval gates."
          : "",
      project_goal:
        inputMode === "onboarding"
          ? "Launch deterministic harness generation."
          : "",
      users: "platform operators",
      constraints: "deterministic gates",
      timeline: "30 days",
      integrations: "oidc, github",
      compliance: "soc2",
      deployment_target: "kubernetes",
      other_context: "legacy monorepo with strict approvals",
    },
  });
  expect(start.status).toBe(200);

  const firstGenerate = await postJson("/api/discovery/session/generate", {
    session_id: start.payload.session_id,
  });
  expect(firstGenerate.status).toBe(200);
  expect(firstGenerate.payload.status).toBe("questions_generated");

  const secondGenerate = await postJson("/api/discovery/session/generate", {
    session_id: start.payload.session_id,
  });
  expect(secondGenerate.status).toBe(200);
  expect(secondGenerate.payload.status).toBe("synthesized");

  return secondGenerate.payload;
}

async function writeExecutableScript(
  filePath: string,
  contents: string,
): Promise<void> {
  await fs.writeFile(filePath, `${contents}\n`, {
    encoding: "utf8",
    mode: 0o755,
  });
}

function buildChildEnv(
  overrides: Record<string, string> = {},
): NodeJS.ProcessEnv {
  return {
    ...process.env,
    PATH: toolBinRoot
      ? `${toolBinRoot}:${process.env.PATH ?? ""}`
      : process.env.PATH,
    CODEX_CLI_COMMAND: "mh-codex",
    CLAUDE_CODE_COMMAND: "mh-claude",
    ...overrides,
  };
}

beforeAll(async () => {
  projectsRoot = await fs.mkdtemp(
    path.join(os.tmpdir(), "mh-builder-projects-"),
  );
  controlRoot = await fs.mkdtemp(path.join(os.tmpdir(), "mh-builder-control-"));
  discoveryDocsRoot = await fs.mkdtemp(
    path.join(os.tmpdir(), "mh-builder-discovery-docs-"),
  );
  toolBinRoot = await fs.mkdtemp(path.join(os.tmpdir(), "mh-builder-bin-"));
  const ports = await allocatePortPair();
  apiPort = ports.apiPort;
  uiPort = ports.uiPort;

  await writeExecutableScript(
    path.join(toolBinRoot, "mh-codex"),
    [
      "#!/usr/bin/env bash",
      "set -euo pipefail",
      'prompt="$(cat)"',
      'if [[ "$prompt" == "emit-large-tail" ]]; then',
      "  python3 - <<'PY'",
      "import os",
      "import sys",
      "",
      "cwd = os.getcwd()",
      "sys.stdout.write('codex-cli\\n')",
      "sys.stdout.write('A' * 260000)",
      "sys.stdout.write(f'\\nstdout-tail:{cwd}/final/stdout.log\\n')",
      "sys.stderr.write('B' * 260000)",
      "sys.stderr.write(f'\\nstderr-tail:{cwd}/final/stderr.log\\n')",
      "PY",
      "  exit 0",
      "fi",
      "printf 'codex-cli\\n'",
      "printf 'cwd=%s\\n' \"$PWD\"",
      "printf '%s\\n' \"$prompt\"",
    ].join("\n"),
  );
  await writeExecutableScript(
    path.join(toolBinRoot, "mh-claude"),
    [
      "#!/usr/bin/env bash",
      "set -euo pipefail",
      'prompt="$(cat)"',
      "printf 'claude-cli\\n'",
      "printf 'cwd=%s\\n' \"$PWD\"",
      "printf '%s\\n' \"$prompt\"",
    ].join("\n"),
  );
  await writeExecutableScript(
    path.join(toolBinRoot, "ssh"),
    [
      "#!/usr/bin/env bash",
      "set -euo pipefail",
      'last="${@: -1}"',
      'if [[ -z "${last:-}" || "$last" == *@* ]]; then',
      "  exit 0",
      "fi",
      'exec /bin/bash -lc "$last"',
    ].join("\n"),
  );

  child = spawn(
    process.execPath,
    [path.join(uiRoot, "scripts", "control-api.mjs")],
    {
      cwd: uiRoot,
        env: buildChildEnv({
          TRACKER_API_PORT: String(apiPort),
          TRACKER_UI_PORT: String(uiPort),
          BUILDER_ALLOWLIST_ROOT: projectsRoot,
          BUILDER_CONTROL_ROOT: controlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: discoveryDocsRoot,
        DISCOVERY_LLM_BACKEND: "none",
      }),
      stdio: "pipe",
    },
  );

  await waitForApiReady(35_000);
}, 40_000);

afterAll(async () => {
  if (child) {
    child.kill("SIGTERM");
    child = null;
  }
  await fs.rm(projectsRoot, { recursive: true, force: true });
  await fs.rm(controlRoot, { recursive: true, force: true });
  await fs.rm(discoveryDocsRoot, { recursive: true, force: true });
  await fs.rm(toolBinRoot, { recursive: true, force: true });
});

describe("control-api backend discovery and generate", () => {
  it("creates a local repo in allowlisted root", async () => {
    const created = await postJson("/api/builder/create-local-repo", {
      repo_name: "mh-create-local-repo",
      initialize_git: true,
    });

    expect(created.status).toBe(200);
    expect(created.payload.status).toBe("created");
    expect(created.payload.repo_path).toBe(
      "<LOCAL_PROJECTS_ROOT>/mh-create-local-repo",
    );
    await expect(
      fs.stat(path.join(projectsRoot, "mh-create-local-repo", "README.md")),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(path.join(projectsRoot, "mh-create-local-repo", ".git")),
    ).resolves.toBeTruthy();
  });

  it("returns privacy-masked path fields by default", async () => {
    const statusResponse = await fetch(apiUrl("/api/builder/status"));
    expect(statusResponse.status).toBe(200);
    const statusPayload = await statusResponse.json();

    expect(statusPayload.version).toBe("BuilderStatusV1");
    expect(statusPayload.path_disclosure_mode).toBe("masked");
    expect(statusPayload.allowlisted_root).toBe("<LOCAL_PROJECTS_ROOT>");
    expect(
      statusPayload.known_repos.some((repo: { path: string }) =>
        repo.path.includes("<LOCAL_PROJECTS_ROOT>/"),
      ),
    ).toBe(true);
  });

  it("evaluates existing repo completeness for harness-core profile", async () => {
    const repoName = "mh-repo-completeness";
    const created = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      initialize_git: false,
    });
    expect(created.status).toBe(200);

    await fs.mkdir(path.join(projectsRoot, repoName, "docs", "11_ops"), {
      recursive: true,
    });
    await fs.writeFile(
      path.join(
        projectsRoot,
        repoName,
        "docs",
        "11_ops",
        "tooling_pipeline.md",
      ),
      "# tooling\n",
      "utf8",
    );

    const checked = await postJson("/api/builder/repo-completeness", {
      target_repo: repoName,
      profile: "harness_core",
    });
    expect(checked.status).toBe(200);
    expect(checked.payload.version).toBe("BuilderRepoCompletenessResponseV1");
    expect(checked.payload.profile).toBe("harness_core");
    expect(checked.payload.summary.total).toBeGreaterThan(4);
    expect(checked.payload.summary.missing_count).toBeGreaterThan(0);
    expect(
      checked.payload.groups.some(
        (group: { group_id: string }) => group.group_id === "tools",
      ),
    ).toBe(true);
  });

  it("returns builder provider availability metadata", async () => {
    const response = await fetch(apiUrl("/api/builder/providers"));
    expect(response.status).toBe(200);
    const payload = await response.json();

    expect(payload.version).toBe("BuilderProviderListV1");
    expect(Array.isArray(payload.providers)).toBe(true);
    expect(
      payload.providers.some(
        (provider: { provider_id: string }) => provider.provider_id === "none",
      ),
    ).toBe(true);
    expect(
      payload.providers.some(
        (provider: { provider_id: string }) =>
          provider.provider_id === "openai",
      ),
    ).toBe(true);
    expect(
      payload.providers.some(
        (provider: { provider_id: string }) =>
          provider.provider_id === "codex_cli",
      ),
    ).toBe(true);
    expect(
      payload.providers.some(
        (provider: { provider_id: string }) =>
          provider.provider_id === "claude_code",
      ),
    ).toBe(true);
  });

  it("returns remote ssh runtime diagnostics in status payload", async () => {
    const response = await fetch(apiUrl("/api/status"));
    expect(response.status).toBe(200);
    const payload = await response.json();

    expect(payload.api).toBe("TrackerControlStatusV1");
    expect(payload.ui_access).toBeTruthy();
    expect(payload.ui_access.execution_host_summary).toContain("Linux host");
    expect(payload.ui_access.remote_ssh_tunnel_example).toContain("ssh -L");
    expect(Array.isArray(payload.ui_access.preferred_urls)).toBe(true);
    expect(payload.assistant_runtimes).toBeTruthy();
    expect(payload.assistant_runtimes.codex_cli.availability_status).toBe(
      "available",
    );
    expect(payload.assistant_runtimes.claude_code.availability_status).toBe(
      "available",
    );
    expect(
      payload.assistant_runtimes.codex_cli.terminal_command_template,
    ).toContain("mh-codex");
    expect(payload.remote_ssh).toBeTruthy();
    expect(payload.remote_ssh.feature_flag_enabled).toBe(false);
    expect(payload.remote_ssh.mode).toBe("disabled");
    expect(Array.isArray(payload.remote_ssh.allowed_command_prefixes)).toBe(
      true,
    );
    expect(payload.remote_ssh.allowed_command_prefixes.length).toBeGreaterThan(
      0,
    );
    expect(payload.builder_feature_flags).toBeTruthy();
    expect(payload.builder_feature_flags.managed_by).toBe("environment");
    expect(payload.builder_feature_flags.allowlisted_root).toBe(
      "<LOCAL_PROJECTS_ROOT>",
    );
  });

  it("returns review queue endpoint payload", async () => {
    const response = await fetch(apiUrl("/api/review/queue"));
    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.version).toBe("ReviewQueueV1");
    expect(Array.isArray(payload.queues)).toBe(true);
    expect(typeof payload.pending_approvals).toBe("number");
  });

  it("enforces overwrite confirmation for create-local-repo", async () => {
    const repoName = "mh-create-overwrite";

    const firstCreate = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      initialize_git: false,
    });
    expect(firstCreate.status).toBe(200);
    await fs.writeFile(
      path.join(projectsRoot, repoName, "sentinel.txt"),
      "sentinel\n",
      "utf8",
    );

    const overwriteMissing = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
    });
    expect(overwriteMissing.status).toBe(409);
    expect(overwriteMissing.payload.error).toBe(
      "overwrite_confirmation_required",
    );

    const overwriteInvalid = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      overwrite: true,
      overwrite_confirmation: "overwrite:wrong-name",
    });
    expect(overwriteInvalid.status).toBe(400);
    expect(overwriteInvalid.payload.error).toBe(
      "invalid_overwrite_confirmation",
    );

    const overwriteValid = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      overwrite: true,
      overwrite_confirmation: `overwrite:${repoName}`,
      initialize_git: false,
    });
    expect(overwriteValid.status).toBe(200);
    expect(overwriteValid.payload.status).toBe("overwritten");

    await expect(
      fs.stat(path.join(projectsRoot, repoName, "README.md")),
    ).resolves.toBeTruthy();
    await expect(
      fs.access(path.join(projectsRoot, repoName, "sentinel.txt")),
    ).rejects.toThrow();
  });

  it("starts discovery in prompt mode and normalizes prompt-driven goal", async () => {
    const started = await postJson("/api/discovery/session/start", {
      intake: {
        input_mode: "prompt",
        project_prompt:
          "Create an internal compliance dashboard with role-based approvals.",
        project_goal: "",
        users: "security team",
        constraints: "auditability",
        timeline: "45 days",
        integrations: "oidc",
        compliance: "soc2",
        deployment_target: "kubernetes",
      },
    });

    expect(started.status).toBe(200);
    expect(started.payload.intake.input_mode).toBe("prompt");
    expect(started.payload.intake.project_goal.length).toBeGreaterThan(0);
    expect(started.payload.intake.project_prompt).toContain(
      "compliance dashboard",
    );
  });

  it("starts discovery in onboarding mode", async () => {
    const started = await postJson("/api/discovery/session/start", {
      intake: {
        input_mode: "onboarding",
        project_prompt: "",
        project_goal: "Deploy a redeployable harness seed.",
        users: "platform team",
        constraints: "deterministic checks",
        timeline: "2 sprints",
        integrations: "git, oidc",
        compliance: "internal",
        deployment_target: "kubernetes",
      },
    });

    expect(started.status).toBe(200);
    expect(started.payload.intake.input_mode).toBe("onboarding");
    expect(started.payload.intake.project_goal).toContain(
      "redeployable harness",
    );
  });

  it("builds and persists discovery prompt bundle artifacts", async () => {
    const session = await startAndSynthesizeSession("onboarding");
    const bundle = await postJson(
      "/api/discovery/session/build-prompt-bundle",
      {
        session_id: session.session_id,
        stage: "synthesis",
        selected_profile: "web_app",
      },
    );

    expect(bundle.status).toBe(200);
    expect(bundle.payload.version).toBe("DiscoveryPromptBundleV1");
    expect(bundle.payload.session_id).toBe(session.session_id);
    expect(bundle.payload.hash.length).toBeGreaterThan(20);
    expect(bundle.payload.workflow_type).toBe("new_project");
    expect(bundle.payload.prompt_template_id).toBe("new_project_synthesis");
    expect(bundle.payload.included_context_sections).toContain(
      "template_manifest",
    );
    expect(bundle.payload.artifact_references).toContain(
      `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_context_v1.json`,
    );
    expect(bundle.payload.context_pack_artifact_path).toBe(
      "dev_tracker/ui/public/generated/context_pack_v1.json",
    );

    const bundleJsonPath = path.join(
      controlRoot,
      "discovery_sessions",
      session.session_id,
      "prompt_bundle.json",
    );
    const bundleMdPath = path.join(
      controlRoot,
      "discovery_sessions",
      session.session_id,
      "prompt_bundle.md",
    );
    const promptContextPath = path.join(
      controlRoot,
      "discovery_sessions",
      session.session_id,
      "prompt_context_v1.json",
    );
    await expect(fs.stat(bundleJsonPath)).resolves.toBeTruthy();
    await expect(fs.stat(bundleMdPath)).resolves.toBeTruthy();
    await expect(fs.stat(promptContextPath)).resolves.toBeTruthy();
  });

  it("builds follow-on phase artifacts and carries extra context into the plan", async () => {
    const session = await startAndSynthesizeSession("onboarding");
    const followOnPlan = await postJson(
      "/api/discovery/session/build-follow-on-plan",
      {
        session_id: session.session_id,
        target_repo: "mh-follow-on-target",
        selected_profile: "web_app",
      },
    );

    expect(followOnPlan.status).toBe(200);
    expect(followOnPlan.payload.version).toBe(
      "DiscoveryFollowOnPlanResponseV1",
    );
    expect(followOnPlan.payload.target_repo).toBe("mh-follow-on-target");
    expect(followOnPlan.payload.alignment_state.version).toBe("AlignmentStateV1");
    expect(followOnPlan.payload.phase_plan.phases.length).toBeGreaterThanOrEqual(
      3,
    );
    expect(
      followOnPlan.payload.prompts.map((prompt: { prompt_id: string }) =>
        prompt.prompt_id,
      ),
    ).toEqual(
      expect.arrayContaining([
        "bootstrap_hydration",
        "phase_planning",
        "phase_1_execution",
        "run_all_phases",
      ]),
    );

    const sessionRoot = path.join(controlRoot, "discovery_sessions", session.session_id);
    const phasePlanJsonPath = path.join(sessionRoot, "phase_plan.json");
    const phasePlanMarkdownPath = path.join(sessionRoot, "phase_plan.md");
    const bootstrapPromptPath = path.join(sessionRoot, "bootstrap_prompt.md");
    const executionPromptsJsonPath = path.join(sessionRoot, "execution_prompts.json");
    const alignmentStateJsonPath = path.join(sessionRoot, "alignment_state.json");
    const alignmentStateMarkdownPath = path.join(sessionRoot, "alignment_state.md");

    await expect(fs.stat(phasePlanJsonPath)).resolves.toBeTruthy();
    await expect(fs.stat(phasePlanMarkdownPath)).resolves.toBeTruthy();
    await expect(fs.stat(bootstrapPromptPath)).resolves.toBeTruthy();
    await expect(fs.stat(executionPromptsJsonPath)).resolves.toBeTruthy();
    await expect(fs.stat(alignmentStateJsonPath)).resolves.toBeTruthy();
    await expect(fs.stat(alignmentStateMarkdownPath)).resolves.toBeTruthy();

    const phasePlanPayload = JSON.parse(await fs.readFile(phasePlanJsonPath, "utf8"));
    const bootstrapMarkdown = await fs.readFile(bootstrapPromptPath, "utf8");
    const executionPromptsPayload = JSON.parse(
      await fs.readFile(executionPromptsJsonPath, "utf8"),
    );
    const alignmentStatePayload = JSON.parse(
      await fs.readFile(alignmentStateJsonPath, "utf8"),
    );

    expect(phasePlanPayload.summary).toContain("mh-follow-on-target");
    expect(
      phasePlanPayload.phases[0].deliverables.some((item: string) =>
        item.includes("Capture extra operator context"),
      ),
    ).toBe(true);
    expect(bootstrapMarkdown).toContain("Fill remaining placeholders");
    expect(bootstrapMarkdown).toContain("legacy monorepo with strict approvals");
    expect(
      executionPromptsPayload.prompts.some(
        (prompt: { prompt_id: string }) => prompt.prompt_id === "run_all_phases",
      ),
    ).toBe(true);
    expect(alignmentStatePayload.summary.overall_status).toMatch(
      /critical|attention|ready/,
    );
    expect(alignmentStatePayload.next_recommended_action).toBeTruthy();
  });

  it("runs assistant actions and persists run artifacts", async () => {
    const repoName = "mh-assistant-target";
    const created = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      initialize_git: false,
    });
    expect(created.status).toBe(200);

    const response = await postJson("/api/assistant/run", {
      assistant: "codex_cli",
      source_mode: "builder",
      execution_scope: "local_repo",
      prompt: "Summarize builder state",
      target_repo: repoName,
    });

    expect(response.status).toBe(200);
    expect(response.payload.version).toBe("AssistantRunResponseV1");
    expect(response.payload.assistant).toBe("codex_cli");
    expect(["queued", "running", "pass"]).toContain(response.payload.status);
    expect(response.payload.stage).not.toBe("failed");
    const completed = await waitForAssistantRun(response.payload.run_id);
    expect(completed.status).toBe("pass");
    expect(completed.stdout).toContain("codex-cli");
    expect(completed.stdout).toContain(`cwd=<LOCAL_PROJECTS_ROOT>/${repoName}`);
    expect(completed.stdout).toContain("Summarize builder state");
    expect(completed.execution_scope).toBe("local_repo");
    expect(completed.execution_context.scope).toBe("local_repo");
    expect(completed.execution_context.target_label).toBe(repoName);
    expect(completed.execution_context.working_directory).toBe(
      `<LOCAL_PROJECTS_ROOT>/${repoName}`,
    );
    await expect(
      fs.stat(
        path.join(
          controlRoot,
          "assistant_runs",
          `${response.payload.run_id}.json`,
        ),
      ),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(
        path.join(
          controlRoot,
          "assistant_runs",
          `${response.payload.run_id}.md`,
        ),
      ),
    ).resolves.toBeTruthy();
    const recentRuns = await fetch(apiUrl("/api/assistant/runs?limit=4"));
    expect(recentRuns.status).toBe(200);
    const recentPayload = await recentRuns.json();
    expect(recentPayload.version).toBe("AssistantRunListResponseV1");
    expect(
      recentPayload.runs.some(
        (run: { run_id: string }) => run.run_id === response.payload.run_id,
      ),
    ).toBe(true);
  });

  it("redacts persisted assistant tails and preserves streamed tails after capture truncation", async () => {
    const repoName = "mh-assistant-tail-target";
    const created = await postJson("/api/builder/create-local-repo", {
      repo_name: repoName,
      initialize_git: false,
    });
    expect(created.status).toBe(200);

    const response = await postJson("/api/assistant/run", {
      assistant: "codex_cli",
      source_mode: "builder",
      execution_scope: "local_repo",
      prompt: "emit-large-tail",
      target_repo: repoName,
    });

    expect(response.status).toBe(200);
    const completed = await waitForAssistantRun(
      response.payload.run_id,
      30_000,
    );
    const safeStdoutTailPath = `stdout-tail:<LOCAL_PROJECTS_ROOT>/${repoName}/final/stdout.log`;
    const safeStderrTailPath = `stderr-tail:<LOCAL_PROJECTS_ROOT>/${repoName}/final/stderr.log`;
    const markdownPath = path.join(
      controlRoot,
      "assistant_runs",
      `${response.payload.run_id}.md`,
    );
    const jsonPath = path.join(
      controlRoot,
      "assistant_runs",
      `${response.payload.run_id}.json`,
    );
    const persisted = JSON.parse(await fs.readFile(jsonPath, "utf8"));
    const markdown = await fs.readFile(markdownPath, "utf8");

    expect(completed.status).toBe("pass");
    expect(completed.stdout.length).toBe(250_000);
    expect(completed.stderr.length).toBe(250_000);
    expect(completed.stdout).not.toContain("stdout-tail:");
    expect(completed.stderr).not.toContain("stderr-tail:");
    expect(completed.stdout_tail).toContain(safeStdoutTailPath);
    expect(completed.stderr_tail).toContain(safeStderrTailPath);
    expect(completed.stdout_tail).not.toContain(projectsRoot);
    expect(completed.stderr_tail).not.toContain(projectsRoot);
    expect(persisted.stdout_tail).toContain(safeStdoutTailPath);
    expect(persisted.stderr_tail).toContain(safeStderrTailPath);
    expect(persisted.stdout_tail).not.toContain(projectsRoot);
    expect(persisted.stderr_tail).not.toContain(projectsRoot);
    expect(markdown).toContain(safeStdoutTailPath);
    expect(markdown).toContain(safeStderrTailPath);
    expect(markdown).not.toContain(projectsRoot);
  });

  it("keeps remote ssh endpoints disabled by default", async () => {
    const tested = await postJson("/api/builder/remote/ssh/test", {
      target: {
        host: "example.com",
        user: "ops",
        port: 22,
        allowlisted_root: "/srv/work",
      },
    });
    expect(tested.status).toBe(403);
    expect(tested.payload.error).toBe("remote_ssh_disabled");
  });

  it("validates SSH remote target metadata when remote mode is enabled", async () => {
    const overrideProjectsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-projects-remote-validate-"),
    );
    const overrideControlRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-control-remote-validate-"),
    );
    const overrideDiscoveryDocsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-discovery-docs-remote-validate-"),
    );
    const overridePorts = await allocatePortPair();
    const overrideApiPort = overridePorts.apiPort;

    const overrideChild = spawn(
      process.execPath,
      [path.join(uiRoot, "scripts", "control-api.mjs")],
      {
        cwd: uiRoot,
        env: buildChildEnv({
          TRACKER_API_PORT: String(overrideApiPort),
          TRACKER_UI_PORT: String(overridePorts.uiPort),
          BUILDER_ALLOWLIST_ROOT: overrideProjectsRoot,
          BUILDER_CONTROL_ROOT: overrideControlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: overrideDiscoveryDocsRoot,
          DISCOVERY_LLM_BACKEND: "none",
          BUILDER_REMOTE_SSH_ENABLED: "true",
        }),
        stdio: "pipe",
      },
    );

    async function postJsonOverride(
      pathname: string,
      body: unknown,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    try {
      await waitForApiReadyAtPort(overrideApiPort);

      const missingPem = await postJsonOverride(
        "/api/builder/remote/ssh/test",
        {
          target: {
            host: "fake-host",
            user: "ops",
            port: 22,
            allowlisted_root: "/srv/work",
            auth_method: "pem_path",
          },
        },
      );
      expect(missingPem.status).toBe(400);
      expect(missingPem.payload.error).toBe("missing_remote_pem_path");

      const invalidKnownHosts = await postJsonOverride(
        "/api/builder/remote/ssh/test",
        {
          target: {
            host: "fake-host",
            user: "ops",
            port: 22,
            allowlisted_root: "/srv/work",
            known_hosts_mode: "relaxed",
          },
        },
      );
      expect(invalidKnownHosts.status).toBe(400);
      expect(invalidKnownHosts.payload.error).toBe("invalid_known_hosts_mode");
    } finally {
      overrideChild.kill("SIGTERM");
      await fs.rm(overrideProjectsRoot, { recursive: true, force: true });
      await fs.rm(overrideControlRoot, { recursive: true, force: true });
      await fs.rm(overrideDiscoveryDocsRoot, { recursive: true, force: true });
    }
  });

  it("keeps existing-project endpoints disabled by default", async () => {
    const scanned = await postJson("/api/builder/project-scan", {
      target_repo: "any-target",
    });
    expect(scanned.status).toBe(403);
    expect(scanned.payload.error).toBe("existing_project_mode_disabled");

    const deployed = await postJson("/api/builder/deploy-existing", {
      session_id: "disc_fake",
      target_repo: "any-target",
      mode: "sidecar",
    });
    expect(deployed.status).toBe(403);
    expect(deployed.payload.error).toBe("existing_project_mode_disabled");
  });

  it("supports remote existing-project scan/deploy/status via guarded SSH mode", async () => {
    const overrideProjectsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-projects-remote-mode-"),
    );
    const overrideControlRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-control-remote-mode-"),
    );
    const overrideDiscoveryDocsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-discovery-docs-remote-mode-"),
    );
    const remoteRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-remote-root-"),
    );
    const overridePorts = await allocatePortPair();
    const overrideApiPort = overridePorts.apiPort;
    const remoteRepoName = "remote-existing-project";
    const remoteRepoRoot = path.join(remoteRoot, remoteRepoName);

    await fs.mkdir(path.join(remoteRepoRoot, ".github", "workflows"), {
      recursive: true,
    });
    await fs.mkdir(path.join(remoteRepoRoot, "tests"), { recursive: true });
    await fs.writeFile(
      path.join(remoteRepoRoot, "README.md"),
      "# remote project\n",
      "utf8",
    );
    await fs.writeFile(
      path.join(remoteRepoRoot, ".github", "workflows", "ci.yml"),
      "name: ci\non: [push]\n",
      "utf8",
    );
    await fs.writeFile(
      path.join(remoteRepoRoot, "tests", "smoke.test.ts"),
      "ok\n",
      "utf8",
    );

    const overrideChild = spawn(
      process.execPath,
      [path.join(uiRoot, "scripts", "control-api.mjs")],
      {
        cwd: uiRoot,
        env: buildChildEnv({
          TRACKER_API_PORT: String(overrideApiPort),
          TRACKER_UI_PORT: String(overridePorts.uiPort),
          BUILDER_ALLOWLIST_ROOT: overrideProjectsRoot,
          BUILDER_CONTROL_ROOT: overrideControlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: overrideDiscoveryDocsRoot,
          DISCOVERY_LLM_BACKEND: "none",
          BUILDER_EXISTING_PROJECT_MODE: "true",
          BUILDER_REMOTE_SSH_ENABLED: "true",
        }),
        stdio: "pipe",
      },
    );

    const remoteTarget = {
      host: "fake-host",
      user: "ops",
      port: 22,
      allowlisted_root: remoteRoot,
      auth_method: "ssh_agent",
      known_hosts_mode: "accept_new",
      profile_label: "fake-remote",
    };

    async function postJsonOverride(
      pathname: string,
      body: unknown,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    async function getJsonOverride(
      pathname: string,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    try {
      await waitForApiReadyAtPort(overrideApiPort);

      const started = await postJsonOverride("/api/discovery/session/start", {
        intake: {
          input_mode: "onboarding",
          project_prompt: "",
          project_goal: "Integrate harness into remote repo",
          users: "platform engineers",
          constraints: "remote sidecar only",
          timeline: "14 days",
          integrations: "github",
          compliance: "soc2",
          deployment_target: "linux",
        },
      });
      expect(started.status).toBe(200);

      const generatedQuestions = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedQuestions.status).toBe(200);

      const generatedSynthesis = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedSynthesis.status).toBe(200);
      expect(generatedSynthesis.payload.status).toBe("synthesized");

      const approvalPath = path.join(
        overrideControlRoot,
        "discovery_sessions",
        started.payload.session_id,
        "approval_required.md",
      );
      const approvalMarkdown = (
        await fs.readFile(approvalPath, "utf8")
      ).replace(
        "- [ ] Approved for execution scope",
        "- [x] Approved for execution scope",
      );
      await fs.writeFile(approvalPath, approvalMarkdown, "utf8");

      const scan = await postJsonOverride("/api/builder/project-scan", {
        target_repo: remoteRepoName,
        target_mode: "remote_ssh",
        remote_target: remoteTarget,
        session_id: started.payload.session_id,
      });
      expect(scan.status).toBe(200);
      expect(scan.payload.target_mode).toBe("remote_ssh");
      expect(scan.payload.remote_target.host).toBe("fake-host");

      const deployed = await postJsonOverride("/api/builder/deploy-existing", {
        session_id: started.payload.session_id,
        target_repo: remoteRepoName,
        target_mode: "remote_ssh",
        remote_target: remoteTarget,
        mode: "sidecar",
      });
      expect(deployed.status).toBe(200);
      expect(deployed.payload.target_mode).toBe("remote_ssh");
      await expect(
        fs.stat(path.join(remoteRepoRoot, ".moradins-harness", "AGENTS.md")),
      ).resolves.toBeTruthy();

      const statusReport = await postJsonOverride(
        "/api/builder/project-status",
        {
          target_repo: remoteRepoName,
          target_mode: "remote_ssh",
          remote_target: remoteTarget,
          session_id: started.payload.session_id,
        },
      );
      expect(statusReport.status).toBe(200);
      expect(statusReport.payload.target_mode).toBe("remote_ssh");
      expect(statusReport.payload.alignment_state.version).toBe(
        "AlignmentStateV1",
      );
      expect(statusReport.payload.status_history).toBeTruthy();

      const statusHistory = await getJsonOverride(
        `/api/builder/project-status/history?target_repo=${encodeURIComponent(remoteRepoName)}&target_mode=remote_ssh&remote_target=${encodeURIComponent(JSON.stringify(remoteTarget))}`,
      );
      expect(statusHistory.status).toBe(200);
      expect(statusHistory.payload.target_mode).toBe("remote_ssh");
      expect(statusHistory.payload.total_entries).toBeGreaterThan(0);
    } finally {
      overrideChild.kill("SIGTERM");
      await fs.rm(overrideProjectsRoot, { recursive: true, force: true });
      await fs.rm(overrideControlRoot, { recursive: true, force: true });
      await fs.rm(overrideDiscoveryDocsRoot, { recursive: true, force: true });
      await fs.rm(remoteRoot, { recursive: true, force: true });
    }
  });

  it("supports existing-project scan/deploy/status when feature flag is enabled", async () => {
    const overrideProjectsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-projects-existing-mode-"),
    );
    const overrideControlRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-control-existing-mode-"),
    );
    const overrideDiscoveryDocsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-discovery-docs-existing-mode-"),
    );
    const overridePorts = await allocatePortPair();
    const overrideApiPort = overridePorts.apiPort;

    const overrideChild = spawn(
      process.execPath,
      [path.join(uiRoot, "scripts", "control-api.mjs")],
      {
        cwd: uiRoot,
        env: {
          ...process.env,
          TRACKER_API_PORT: String(overrideApiPort),
          TRACKER_UI_PORT: String(overridePorts.uiPort),
          BUILDER_ALLOWLIST_ROOT: overrideProjectsRoot,
          BUILDER_CONTROL_ROOT: overrideControlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: overrideDiscoveryDocsRoot,
          DISCOVERY_LLM_BACKEND: "none",
          BUILDER_EXISTING_PROJECT_MODE: "true",
        },
        stdio: "pipe",
      },
    );

    async function postJsonOverride(
      pathname: string,
      body: unknown,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    async function getJsonOverride(
      pathname: string,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    try {
      await waitForApiReadyAtPort(overrideApiPort);

      const created = await postJsonOverride("/api/builder/create-local-repo", {
        repo_name: "existing-project-seed",
        initialize_git: true,
      });
      expect(created.status).toBe(200);
      await fs.mkdir(
        path.join(
          overrideProjectsRoot,
          "existing-project-seed",
          ".github",
          "workflows",
        ),
        { recursive: true },
      );
      await fs.writeFile(
        path.join(
          overrideProjectsRoot,
          "existing-project-seed",
          ".github",
          "workflows",
          "ci.yml",
        ),
        "name: ci\non: [push]\n",
        "utf8",
      );
      await fs.mkdir(
        path.join(overrideProjectsRoot, "existing-project-seed", "tests"),
        { recursive: true },
      );
      await fs.writeFile(
        path.join(
          overrideProjectsRoot,
          "existing-project-seed",
          "tests",
          "smoke.test.ts",
        ),
        "ok\n",
        "utf8",
      );

      const started = await postJsonOverride("/api/discovery/session/start", {
        intake: {
          input_mode: "onboarding",
          project_prompt: "",
          project_goal: "Integrate harness into existing repo",
          users: "platform engineers",
          constraints: "do not overwrite project root",
          timeline: "30 days",
          integrations: "github, oidc",
          compliance: "soc2",
          deployment_target: "kubernetes",
        },
      });
      expect(started.status).toBe(200);

      const generatedQuestions = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedQuestions.status).toBe(200);
      expect(generatedQuestions.payload.status).toBe("questions_generated");

      const generatedSynthesis = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedSynthesis.status).toBe(200);
      expect(generatedSynthesis.payload.status).toBe("synthesized");

      const deployBeforeScan = await postJsonOverride(
        "/api/builder/deploy-existing",
        {
          session_id: started.payload.session_id,
          target_repo: "existing-project-seed",
          mode: "sidecar",
        },
      );
      expect(deployBeforeScan.status).toBe(409);
      expect(deployBeforeScan.payload.error).toBe("missing_project_scan");

      const approvalPath = path.join(
        overrideControlRoot,
        "discovery_sessions",
        started.payload.session_id,
        "approval_required.md",
      );
      const approvalMarkdown = (
        await fs.readFile(approvalPath, "utf8")
      ).replace(
        "- [ ] Approved for execution scope",
        "- [x] Approved for execution scope",
      );
      await fs.writeFile(approvalPath, approvalMarkdown, "utf8");

      const scan = await postJsonOverride("/api/builder/project-scan", {
        target_repo: "existing-project-seed",
        session_id: started.payload.session_id,
        scan_limits: {
          max_depth: 999,
          max_files: 999999,
        },
      });
      expect(scan.status).toBe(200);
      expect(scan.payload.version).toBe("ProjectBaselineScanV1");
      expect(scan.payload.artifact_paths).toBeTruthy();
      expect(scan.payload.detected.ci_surfaces.length).toBeGreaterThan(0);
      expect(scan.payload.scan_limits_effective.max_depth).toBe(16);
      expect(scan.payload.scan_limits_effective.max_files).toBe(50000);

      const deployed = await postJsonOverride("/api/builder/deploy-existing", {
        session_id: started.payload.session_id,
        target_repo: "existing-project-seed",
        mode: "sidecar",
      });
      expect(deployed.status).toBe(200);
      expect(deployed.payload.version).toBe("DeployExistingProjectResponseV1");
      expect(deployed.payload.mode).toBe("sidecar");
      await expect(
        fs.stat(
          path.join(
            overrideProjectsRoot,
            "existing-project-seed",
            ".moradins-harness",
            "AGENTS.md",
          ),
        ),
      ).resolves.toBeTruthy();

      const followOnPlan = await postJsonOverride(
        "/api/discovery/session/build-follow-on-plan",
        {
          session_id: started.payload.session_id,
          target_repo: "existing-project-seed",
          selected_profile: "internal_tooling",
        },
      );
      expect(followOnPlan.status).toBe(200);
      expect(followOnPlan.payload.version).toBe(
        "DiscoveryFollowOnPlanResponseV1",
      );
      expect(followOnPlan.payload.alignment_state.version).toBe(
        "AlignmentStateV1",
      );
      expect(
        followOnPlan.payload.prompts.map((prompt: { prompt_id: string }) =>
          prompt.prompt_id,
        ),
      ).toEqual(
        expect.arrayContaining([
          "bootstrap_hydration",
          "phase_planning",
          "phase_1_execution",
          "run_all_phases",
        ]),
      );
      await expect(
        fs.stat(
          path.join(
            overrideControlRoot,
            "discovery_sessions",
            started.payload.session_id,
            "alignment_state.json",
          ),
        ),
      ).resolves.toBeTruthy();
      await expect(
        fs.stat(
          path.join(
            overrideControlRoot,
            "discovery_sessions",
            started.payload.session_id,
            "phase_plan.json",
          ),
        ),
      ).resolves.toBeTruthy();
      await expect(
        fs.stat(
          path.join(
            overrideControlRoot,
            "discovery_sessions",
            started.payload.session_id,
            "execution_prompts.json",
          ),
        ),
      ).resolves.toBeTruthy();
      const bootstrapPromptMarkdown = await fs.readFile(
        path.join(
          overrideControlRoot,
          "discovery_sessions",
          started.payload.session_id,
          "bootstrap_prompt.md",
        ),
        "utf8",
      );
      const templateFillMapMarkdown = await fs.readFile(
        path.join(
          overrideControlRoot,
          "discovery_sessions",
          started.payload.session_id,
          "template_fill_map.md",
        ),
        "utf8",
      );
      const phasePlanPayload = JSON.parse(
        await fs.readFile(
          path.join(
            overrideControlRoot,
            "discovery_sessions",
            started.payload.session_id,
            "phase_plan.json",
          ),
          "utf8",
        ),
      );
      expect(bootstrapPromptMarkdown).toContain("languages=");
      expect(bootstrapPromptMarkdown).toContain("package_managers=");
      expect(bootstrapPromptMarkdown).toContain("ci_surfaces=");
      expect(bootstrapPromptMarkdown).toContain("deployment_surfaces=");
      expect(templateFillMapMarkdown).toContain("## Scan-Derived Context");
      expect(
        phasePlanPayload.phases.some((phase: { deliverables: string[] }) =>
          phase.deliverables.some(
            (item: string) =>
              item.toLowerCase().includes("validation surface") ||
              item.toLowerCase().includes("github"),
          ),
        ),
      ).toBe(true);

      const hydratedSession = await getJsonOverride(
        `/api/discovery/session/${started.payload.session_id}`,
      );
      expect(hydratedSession.status).toBe(200);
      expect(hydratedSession.payload.artifacts.phase_plan_markdown).toContain(
        "phase_plan.md",
      );
      expect(hydratedSession.payload.artifacts.alignment_state_markdown).toContain(
        "alignment_state.md",
      );
      expect(hydratedSession.payload.artifacts.execution_prompts_json).toContain(
        "execution_prompts.json",
      );

      const statusReport = await postJsonOverride(
        "/api/builder/project-status",
        {
          target_repo: "existing-project-seed",
          session_id: started.payload.session_id,
        },
      );
      expect(statusReport.status).toBe(200);
      expect(statusReport.payload.version).toBe("ProjectStatusReportV1");
      expect(statusReport.payload.alignment_state.version).toBe(
        "AlignmentStateV1",
      );
      expect(Array.isArray(statusReport.payload.actions)).toBe(true);
      expect(statusReport.payload.summary.action_total).toBeGreaterThan(0);
      expect(statusReport.payload.status_history).toBeTruthy();

      const statusHistory = await getJsonOverride(
        `/api/builder/project-status/history?target_repo=${encodeURIComponent("existing-project-seed")}&limit=5`,
      );
      expect(statusHistory.status).toBe(200);
      expect(statusHistory.payload.version).toBe(
        "ProjectStatusHistoryResponseV1",
      );
      expect(statusHistory.payload.total_entries).toBeGreaterThan(0);
      expect(statusHistory.payload.entries.length).toBeGreaterThan(0);
    } finally {
      overrideChild.kill("SIGTERM");
      await fs.rm(overrideProjectsRoot, { recursive: true, force: true });
      await fs.rm(overrideControlRoot, { recursive: true, force: true });
      await fs.rm(overrideDiscoveryDocsRoot, { recursive: true, force: true });
    }
  });

  it("blocks deploy on critical scan gaps unless explicit override is provided", async () => {
    const overrideProjectsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-projects-gaps-"),
    );
    const overrideControlRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-control-gaps-"),
    );
    const overrideDiscoveryDocsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-discovery-docs-gaps-"),
    );
    const overridePorts = await allocatePortPair();
    const overrideApiPort = overridePorts.apiPort;

    const overrideChild = spawn(
      process.execPath,
      [path.join(uiRoot, "scripts", "control-api.mjs")],
      {
        cwd: uiRoot,
        env: {
          ...process.env,
          TRACKER_API_PORT: String(overrideApiPort),
          TRACKER_UI_PORT: String(overridePorts.uiPort),
          BUILDER_ALLOWLIST_ROOT: overrideProjectsRoot,
          BUILDER_CONTROL_ROOT: overrideControlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: overrideDiscoveryDocsRoot,
          DISCOVERY_LLM_BACKEND: "none",
          BUILDER_EXISTING_PROJECT_MODE: "true",
        },
        stdio: "pipe",
      },
    );

    async function postJsonOverride(
      pathname: string,
      body: unknown,
    ): Promise<{ status: number; payload: any }> {
      const response = await fetch(
        `http://127.0.0.1:${overrideApiPort}${pathname}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      return {
        status: response.status,
        payload: await response.json(),
      };
    }

    try {
      await waitForApiReadyAtPort(overrideApiPort);

      const repoName = "existing-project-critical-gap";
      const created = await postJsonOverride("/api/builder/create-local-repo", {
        repo_name: repoName,
        initialize_git: true,
      });
      expect(created.status).toBe(200);

      const started = await postJsonOverride("/api/discovery/session/start", {
        intake: {
          input_mode: "onboarding",
          project_prompt: "",
          project_goal: "Integrate harness into gap repo",
          users: "platform engineers",
          constraints: "no root overwrite",
          timeline: "7 days",
          integrations: "",
          compliance: "",
          deployment_target: "linux",
        },
      });
      expect(started.status).toBe(200);

      const generatedQuestions = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedQuestions.status).toBe(200);
      const generatedSynthesis = await postJsonOverride(
        "/api/discovery/session/generate",
        {
          session_id: started.payload.session_id,
        },
      );
      expect(generatedSynthesis.status).toBe(200);
      expect(generatedSynthesis.payload.status).toBe("synthesized");

      const approvalPath = path.join(
        overrideControlRoot,
        "discovery_sessions",
        started.payload.session_id,
        "approval_required.md",
      );
      const approvalMarkdown = (
        await fs.readFile(approvalPath, "utf8")
      ).replace(
        "- [ ] Approved for execution scope",
        "- [x] Approved for execution scope",
      );
      await fs.writeFile(approvalPath, approvalMarkdown, "utf8");

      const scan = await postJsonOverride("/api/builder/project-scan", {
        target_repo: repoName,
        session_id: started.payload.session_id,
      });
      expect(scan.status).toBe(200);
      expect(scan.payload.summary.critical_gap_count).toBeGreaterThan(0);

      const blockedDeploy = await postJsonOverride(
        "/api/builder/deploy-existing",
        {
          session_id: started.payload.session_id,
          target_repo: repoName,
          mode: "sidecar",
        },
      );
      expect(blockedDeploy.status).toBe(409);
      expect(blockedDeploy.payload.error).toBe("critical_gaps_blocked");

      const overrideDeploy = await postJsonOverride(
        "/api/builder/deploy-existing",
        {
          session_id: started.payload.session_id,
          target_repo: repoName,
          mode: "sidecar",
          critical_gap_policy: "block_with_override",
          critical_gap_override_reason:
            "Proceeding for staged harness bootstrap before CI rollout.",
          critical_gap_override_confirmation:
            "override-critical-gaps:existing-project-critical-gap",
        },
      );
      expect(overrideDeploy.status).toBe(200);
      expect(overrideDeploy.payload.critical_gap_override_applied).toBe(true);
    } finally {
      overrideChild.kill("SIGTERM");
      await fs.rm(overrideProjectsRoot, { recursive: true, force: true });
      await fs.rm(overrideControlRoot, { recursive: true, force: true });
      await fs.rm(overrideDiscoveryDocsRoot, { recursive: true, force: true });
    }
  });

  it("blocks generate-from-discovery until approval is granted", async () => {
    const session = await startAndSynthesizeSession("onboarding");

    const generated = await postJson("/api/builder/generate-from-discovery", {
      session_id: session.session_id,
      profile: "web_app",
      destination_repo: "mh004-generate-unapproved",
    });

    expect(generated.status).toBe(409);
    expect(generated.payload.error).toBe("approval_required");
  });

  it("generates a full harness seed with validation metadata once approved", async () => {
    const session = await startAndSynthesizeSession("prompt");
    const approvalPath = path.join(
      controlRoot,
      "discovery_sessions",
      session.session_id,
      "approval_required.md",
    );

    let approvalMarkdown = await fs.readFile(approvalPath, "utf8");
    approvalMarkdown = approvalMarkdown.replace(
      "- [ ] Approved for execution scope",
      "- [x] Approved for execution scope",
    );
    await fs.writeFile(approvalPath, approvalMarkdown, "utf8");

    const generated = await postJson("/api/builder/generate-from-discovery", {
      session_id: session.session_id,
      profile: "internal_tooling",
      destination_repo: "mh004-generate-approved",
    });

    expect(generated.status).toBe(200);
    expect(generated.payload.version).toBe("GenerateProjectRepoResponseV1");
    expect(generated.payload.harness_seed_version).toBeTruthy();
    expect(Array.isArray(generated.payload.generated_files)).toBe(true);
    expect(generated.payload.generated_files.length).toBeGreaterThan(10);
    expect(generated.payload.validation.status).toBe("pass");

    const generatedRepo = path.join(projectsRoot, "mh004-generate-approved");
    const requiredSurface = [
      "AGENTS.md",
      "README.md",
      "Makefile",
      "pyproject.toml",
      "docs/00_overview/implementation_phases.md",
      "docs/11_ops/day0_onboarding_runbook.md",
      "docs/11_ops/day1_onboarding_runbook.md",
      "docs/03_architecture/container_topology.md",
      "docs/engineer_entry/index.md",
      "docs/references/moradin_forge_agent_integration_contract_v1.md",
      "Harness/moradin_payload/manifest.yaml",
      "skills/index.md",
      "scripts/moradin_forge.py",
      "scripts/moradin_forge.sh",
      "scripts/moradin_forge.ps1",
      "dev_tracker/ui/scripts/control-api.mjs",
      "dev_tracker/ui/tests/control-api-backend.test.ts",
      "tests/contracts/test_validators.py",
      "tests/scripts/test_moradin_forge.py",
      "tests/scripts/test_public_export.py",
    ];
    for (const relativePath of requiredSurface) {
      await expect(
        fs.stat(path.join(generatedRepo, relativePath)),
      ).resolves.toBeTruthy();
    }
  });

  it("isolates discovery synthesis docs under BUILDER_DISCOVERY_DOCS_ROOT", async () => {
    const session = await startAndSynthesizeSession("onboarding");

    await expect(
      fs.stat(
        path.join(
          discoveryDocsRoot,
          "product_specs",
          `discovery_${session.session_id}_project_spec.md`,
        ),
      ),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(
        path.join(
          discoveryDocsRoot,
          "design_docs",
          `discovery_${session.session_id}_architecture.md`,
        ),
      ),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(
        path.join(
          discoveryDocsRoot,
          "exec_plans",
          "implementation",
          "active",
          `plan_${session.session_id}_discovery_generated.md`,
        ),
      ),
    ).resolves.toBeTruthy();

    await expect(
      fs.stat(
        path.join(
          repoRoot,
          "docs",
          "product_specs",
          `discovery_${session.session_id}_project_spec.md`,
        ),
      ),
    ).rejects.toThrow();
    await expect(
      fs.stat(
        path.join(
          repoRoot,
          "docs",
          "design_docs",
          `discovery_${session.session_id}_architecture.md`,
        ),
      ),
    ).rejects.toThrow();
    await expect(
      fs.stat(
        path.join(
          repoRoot,
          "docs",
          "exec_plans",
          "implementation",
          "active",
          `plan_${session.session_id}_discovery_generated.md`,
        ),
      ),
    ).rejects.toThrow();
  });

  it("excludes volatile discovery drafts from seeded generated repos", async () => {
    const nonce = `${Date.now()}`;
    const volatileFiles = [
      path.join(
        repoRoot,
        "docs",
        "design_docs",
        `discovery_disc_${nonce}_architecture.md`,
      ),
      path.join(
        repoRoot,
        "docs",
        "product_specs",
        `discovery_disc_${nonce}_project_spec.md`,
      ),
      path.join(
        repoRoot,
        "docs",
        "exec_plans",
        "implementation",
        "active",
        `plan_disc_${nonce}_discovery_generated.md`,
      ),
    ];

    for (const filePath of volatileFiles) {
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, "# volatile\n", "utf8");
    }

    try {
      const session = await startAndSynthesizeSession("prompt");
      const approvalPath = path.join(
        controlRoot,
        "discovery_sessions",
        session.session_id,
        "approval_required.md",
      );
      const approvalMarkdown = (
        await fs.readFile(approvalPath, "utf8")
      ).replace(
        "- [ ] Approved for execution scope",
        "- [x] Approved for execution scope",
      );
      await fs.writeFile(approvalPath, approvalMarkdown, "utf8");

      const generated = await postJson("/api/builder/generate-from-discovery", {
        session_id: session.session_id,
        profile: "web_app",
        destination_repo: "mh004-volatile-filter",
      });
      expect(generated.status).toBe(200);

      const generatedRepo = path.join(projectsRoot, "mh004-volatile-filter");
      const excludedRelativePaths = [
        `docs/design_docs/discovery_disc_${nonce}_architecture.md`,
        `docs/product_specs/discovery_disc_${nonce}_project_spec.md`,
        `docs/exec_plans/implementation/active/plan_disc_${nonce}_discovery_generated.md`,
      ];
      for (const relativePath of excludedRelativePaths) {
        await expect(
          fs.stat(path.join(generatedRepo, relativePath)),
        ).rejects.toThrow();
      }
      expect(generated.payload.generated_files).not.toContain(
        excludedRelativePaths[0],
      );
      expect(generated.payload.generated_files).not.toContain(
        excludedRelativePaths[1],
      );
      expect(generated.payload.generated_files).not.toContain(
        excludedRelativePaths[2],
      );
    } finally {
      for (const filePath of volatileFiles) {
        await fs.rm(filePath, { force: true });
      }
    }
  });

  it("imports a harness directory path and records audit entry", async () => {
    const sourceRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-source-success-"),
    );
    await fs.mkdir(path.join(sourceRoot, "docs"), { recursive: true });
    await fs.writeFile(
      path.join(sourceRoot, "README.md"),
      "# imported\n",
      "utf8",
    );
    await fs.writeFile(
      path.join(sourceRoot, "docs", "notes.md"),
      "notes\n",
      "utf8",
    );
    await fs.mkdir(path.join(sourceRoot, ".git"), { recursive: true });

    const imported = await postJson("/api/builder/import-harness-path", {
      source_path: sourceRoot,
      destination_repo: "mh-import-path-success",
    });

    expect(imported.status).toBe(200);
    expect(imported.payload.status).toBe("imported");
    await expect(
      fs.stat(path.join(projectsRoot, "mh-import-path-success", "README.md")),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(
        path.join(projectsRoot, "mh-import-path-success", "docs", "notes.md"),
      ),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(path.join(projectsRoot, "mh-import-path-success", ".git")),
    ).rejects.toThrow();

    const audit = await fs.readFile(
      path.join(controlRoot, "builder_operation_audit.md"),
      "utf8",
    );
    expect(audit).toContain("| import-harness-path | imported |");
    await fs.rm(sourceRoot, { recursive: true, force: true });
  });

  it("imports a valid bundle and records audit entry", async () => {
    const archiveRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-bundle-success-"),
    );
    const archivePath = path.join(archiveRoot, "safe.zip");

    const createArchive = spawnSync(
      "python3",
      [
        "-c",
        [
          "import sys",
          "import zipfile",
          "",
          "archive_path = sys.argv[1]",
          "with zipfile.ZipFile(archive_path, 'w') as zf:",
          "    zf.writestr('README.md', '# bundle')",
          "    zf.writestr('docs/info.md', 'ok')",
        ].join("\n"),
        archivePath,
      ],
      { encoding: "utf8" },
    );
    if (createArchive.status !== 0) {
      throw new Error(
        createArchive.stderr ||
          createArchive.stdout ||
          "failed to create safe test archive",
      );
    }

    const archiveBuffer = await fs.readFile(archivePath);
    const imported = await postJson("/api/builder/import-harness-bundle", {
      destination_repo: "mh-import-bundle-success",
      filename: "safe.zip",
      bundle_base64: archiveBuffer.toString("base64"),
    });

    expect(imported.status).toBe(200);
    expect(imported.payload.status).toBe("imported");
    await expect(
      fs.stat(path.join(projectsRoot, "mh-import-bundle-success", "README.md")),
    ).resolves.toBeTruthy();
    await expect(
      fs.stat(
        path.join(projectsRoot, "mh-import-bundle-success", "docs", "info.md"),
      ),
    ).resolves.toBeTruthy();

    const audit = await fs.readFile(
      path.join(controlRoot, "builder_operation_audit.md"),
      "utf8",
    );
    expect(audit).toContain("| import-harness-bundle | imported |");
    await fs.rm(archiveRoot, { recursive: true, force: true });
  });

  it("blocks destination paths outside the allowlisted root", async () => {
    const sourceRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-source-outside-"),
    );
    await fs.writeFile(
      path.join(sourceRoot, "README.md"),
      "# source\n",
      "utf8",
    );

    const imported = await postJson("/api/builder/import-harness-path", {
      source_path: sourceRoot,
      destination_repo: path.join(
        os.tmpdir(),
        "mh-not-allowlisted-destination",
      ),
    });

    expect(imported.status).toBe(403);
    expect(imported.payload.error).toBe("outside_allowlist");
    await fs.rm(sourceRoot, { recursive: true, force: true });
  });

  it("blocks symlink escape attempts for destination paths", async () => {
    const sourceRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-source-symlink-"),
    );
    await fs.writeFile(
      path.join(sourceRoot, "README.md"),
      "# source\n",
      "utf8",
    );

    const outsideRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-outside-link-target-"),
    );
    const symlinkPath = path.join(projectsRoot, "link-out");
    await fs.symlink(outsideRoot, symlinkPath);

    const imported = await postJson("/api/builder/import-harness-path", {
      source_path: sourceRoot,
      destination_repo: path.join(projectsRoot, "link-out", "seed"),
    });

    expect(imported.status).toBe(403);
    expect(imported.payload.error).toBe("symlink_escape_blocked");

    await fs.rm(sourceRoot, { recursive: true, force: true });
    await fs.rm(outsideRoot, { recursive: true, force: true });
  });

  it("rejects unsafe archive entries during bundle import", async () => {
    const archiveRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-unsafe-archive-"),
    );
    const archivePath = path.join(archiveRoot, "unsafe.zip");

    const createArchive = spawnSync(
      "python3",
      [
        "-c",
        [
          "import sys",
          "import zipfile",
          "",
          "archive_path = sys.argv[1]",
          "with zipfile.ZipFile(archive_path, 'w') as zf:",
          "    zf.writestr('../escape.txt', 'bad')",
        ].join("\n"),
        archivePath,
      ],
      { encoding: "utf8" },
    );
    if (createArchive.status !== 0) {
      throw new Error(
        createArchive.stderr ||
          createArchive.stdout ||
          "failed to create unsafe test archive",
      );
    }

    const archiveBuffer = await fs.readFile(archivePath);
    const imported = await postJson("/api/builder/import-harness-bundle", {
      destination_repo: "mh-unsafe-bundle-test",
      filename: "unsafe.zip",
      bundle_base64: archiveBuffer.toString("base64"),
    });

    expect(imported.status).toBe(400);
    expect(imported.payload.error).toBe("unsafe_archive_path");
    await fs.rm(archiveRoot, { recursive: true, force: true });
  });

  it("rejects bundle filenames containing path separators", async () => {
    const imported = await postJson("/api/builder/import-harness-bundle", {
      destination_repo: "mh-invalid-filename-bundle",
      filename: "../../escape.zip",
      bundle_base64: Buffer.from("not-a-zip").toString("base64"),
    });

    expect(imported.status).toBe(400);
    expect(imported.payload.error).toBe("invalid_bundle_filename");
  });

  it("allows default trusted UI origins and rejects unknown origins", async () => {
    const trustedOrigins = [
      `http://127.0.0.1:${uiPort}`,
      `http://localhost:${uiPort}`,
      `http://[::1]:${uiPort}`,
    ];
    const wslIpv4 = detectWslIpv4ForTests();
    if (wslIpv4) {
      trustedOrigins.push(`http://${wslIpv4}:${uiPort}`);
    }

    for (const trustedOrigin of trustedOrigins) {
      const trusted = await fetch(apiUrl("/api/status"), {
        headers: { Origin: trustedOrigin },
      });
      expect(trusted.status).toBe(200);
      expect(trusted.headers.get("access-control-allow-origin")).toBe(
        trustedOrigin,
      );
    }

    const untrusted = await postJson(
      "/api/sync",
      {},
      {
        Origin: "http://malicious.example",
      },
    );
    expect(untrusted.status).toBe(403);
    expect(untrusted.payload.error).toBe("origin_not_allowed");
  });

  it("applies TRACKER_TRUSTED_ORIGINS override without merging default origins", async () => {
    const overrideProjectsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-projects-override-"),
    );
    const overrideControlRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-control-override-"),
    );
    const overrideDiscoveryDocsRoot = await fs.mkdtemp(
      path.join(os.tmpdir(), "mh-builder-discovery-docs-override-"),
    );
    const overridePorts = await allocatePortPair();
    const overrideApiPort = overridePorts.apiPort;
    const overrideUiPort = overridePorts.uiPort;
    const overrideTrustedOrigin = `http://localhost:${overrideUiPort}`;

    const overrideChild = spawn(
      process.execPath,
      [path.join(uiRoot, "scripts", "control-api.mjs")],
      {
        cwd: uiRoot,
        env: {
          ...process.env,
          TRACKER_API_PORT: String(overrideApiPort),
          TRACKER_UI_PORT: String(overrideUiPort),
          TRACKER_TRUSTED_ORIGINS: overrideTrustedOrigin,
          BUILDER_ALLOWLIST_ROOT: overrideProjectsRoot,
          BUILDER_CONTROL_ROOT: overrideControlRoot,
          BUILDER_DISCOVERY_DOCS_ROOT: overrideDiscoveryDocsRoot,
          DISCOVERY_LLM_BACKEND: "none",
        },
        stdio: "pipe",
      },
    );

    try {
      await waitForApiReadyAtPort(overrideApiPort);

      const allowed = await fetch(
        `http://127.0.0.1:${overrideApiPort}/api/status`,
        {
          headers: { Origin: overrideTrustedOrigin },
        },
      );
      expect(allowed.status).toBe(200);
      expect(allowed.headers.get("access-control-allow-origin")).toBe(
        overrideTrustedOrigin,
      );

      const defaultLoopback = await fetch(
        `http://127.0.0.1:${overrideApiPort}/api/status`,
        {
          headers: { Origin: `http://127.0.0.1:${overrideUiPort}` },
        },
      );
      expect(defaultLoopback.status).toBe(403);
      const payload = await defaultLoopback.json();
      expect(payload.error).toBe("origin_not_allowed");
    } finally {
      overrideChild.kill("SIGTERM");
      await fs.rm(overrideProjectsRoot, { recursive: true, force: true });
      await fs.rm(overrideControlRoot, { recursive: true, force: true });
      await fs.rm(overrideDiscoveryDocsRoot, { recursive: true, force: true });
    }
  }, 25_000);
});
