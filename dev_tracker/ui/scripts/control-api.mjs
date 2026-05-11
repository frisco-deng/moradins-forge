import { execFileSync, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(uiRoot, "..", "..");
const generatedRoot = path.join(uiRoot, "public", "generated");
const syncScriptPath = path.join(uiRoot, "scripts", "sync-docs.mjs");
const controlRoot = path.resolve(
  process.env.BUILDER_CONTROL_ROOT ??
    path.join(repoRoot, "Harness", "artifacts", "control"),
);
const discoveryDocsRoot = path.resolve(
  process.env.BUILDER_DISCOVERY_DOCS_ROOT ?? path.join(repoRoot, "docs"),
);
const discoveryRoot = path.join(controlRoot, "discovery_sessions");
const assistantRunsRoot = path.join(controlRoot, "assistant_runs");
const builderAuditPath = path.join(controlRoot, "builder_operation_audit.md");
const defaultAllowlistedRoot = path.join(repoRoot, ".builder_projects");
const allowlistedRoot = path.resolve(
  process.env.BUILDER_ALLOWLIST_ROOT ?? defaultAllowlistedRoot,
);
const harnessSourceRoot = String(
  process.env.BUILDER_HARNESS_SOURCE_ROOT ?? "",
).trim();
const externalTemplateRoot = String(
  process.env.BUILDER_EXTERNAL_TEMPLATE_ROOT ?? "",
).trim();
const pathDisclosureMode =
  String(process.env.BUILDER_PATH_DISCLOSURE_MODE ?? "masked")
    .trim()
    .toLowerCase() === "full"
    ? "full"
    : "masked";
const scanMaxDepthDefault = parseBoundedInteger(
  process.env.BUILDER_SCAN_MAX_DEPTH,
  6,
  { min: 1, max: 16 },
);
const scanMaxFilesDefault = parseBoundedInteger(
  process.env.BUILDER_SCAN_MAX_FILES,
  5000,
  { min: 100, max: 50000 },
);
const projectStatusHistoryMaxEntries = parseBoundedInteger(
  process.env.BUILDER_PROJECT_STATUS_HISTORY_MAX_ENTRIES,
  50,
  {
    min: 1,
    max: 500,
  },
);
const assistantRunTimeoutMs = parseBoundedInteger(
  process.env.ASSISTANT_RUN_TIMEOUT_MS,
  60_000,
  {
    min: 5_000,
    max: 600_000,
  },
);
const discoveryProviderDefault = String(
  process.env.DISCOVERY_LLM_BACKEND ?? "none",
)
  .trim()
  .toLowerCase();
const sshRemoteEnabled =
  String(process.env.BUILDER_REMOTE_SSH_ENABLED ?? "false")
    .trim()
    .toLowerCase() === "true";
const existingProjectModeEnabled =
  String(process.env.BUILDER_EXISTING_PROJECT_MODE ?? "false")
    .trim()
    .toLowerCase() === "true";
const sshAllowedCommands = String(
  process.env.BUILDER_REMOTE_SSH_ALLOWED_COMMANDS ?? "pwd,ls,whoami,uname -a",
)
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const DISCOVERY_PROMPT_SYSTEM_INSTRUCTIONS = [
  "You are the Moradins Harness discovery synthesizer.",
  "Follow deterministic contract-first planning.",
  "Return JSON only when asked for JSON.",
  "Prioritize explicit constraints, scope boundaries, and approval-gate language.",
  "Do not emit executable operations or shell commands.",
].join(" ");

const port = Number(process.env.TRACKER_API_PORT ?? 8787);
const uiPort = Number(process.env.TRACKER_UI_PORT ?? 5273);
const uiHost = resolveTrackerUiHost();
const trustedOriginsSource =
  process.env.TRACKER_TRUSTED_ORIGINS ??
  process.env.TRACKER_API_TRUSTED_ORIGINS;
const wslIpv4 = detectWslIpv4();
const trustedOrigins = buildTrustedOrigins(
  trustedOriginsSource,
  uiPort,
  wslIpv4,
);
const uiPreferredUrl = `http://localhost:${uiPort}/`;
const uiLoopbackUrl = `http://127.0.0.1:${uiPort}/`;
const uiWslUrl = wslIpv4 ? `http://${wslIpv4}:${uiPort}/` : "";
const HARNESS_SEED_VERSION = "mh004-seed-v1";
const CONTROL_ARTIFACT_RELATIVE_ROOT = "Harness/artifacts/control";
const DISCOVERY_SESSIONS_RELATIVE_ROOT =
  "Harness/artifacts/control/discovery_sessions";
const PROJECT_STATUS_HISTORY_RELATIVE_ROOT =
  "Harness/artifacts/control/project_status_history";
const ASSISTANT_RUNS_RELATIVE_ROOT = "Harness/artifacts/control/assistant_runs";
const INSTALL_REQUESTS_RELATIVE_ROOT =
  "Harness/artifacts/control/install_requests";
const REPO_REGISTRY_RELATIVE_ROOT = "Harness/artifacts/control/repo_registry";
const MORADIN_PAYLOAD_MANIFEST_RELATIVE_PATH =
  "Harness/moradin_payload/manifest.yaml";
const GENERATED_CONTEXT_PACK_RELATIVE_PATH =
  "dev_tracker/ui/public/generated/context_pack_v1.json";
const projectStatusHistoryRoot = path.join(
  controlRoot,
  "project_status_history",
);
const installRequestsRoot = path.join(controlRoot, "install_requests");
const repoRegistryRoot = path.join(controlRoot, "repo_registry");
const VOLATILE_DISCOVERY_FILE_PATTERNS = [
  /^docs\/design_docs\/discovery_.*_architecture\.md$/,
  /^docs\/product_specs\/discovery_.*_project_spec\.md$/,
  /^docs\/exec_plans\/implementation\/active\/plan_disc_.*_discovery_generated\.md$/,
];
const PROFILE_OVERLAYS = {
  web_app: {
    defaults: [
      "frontend + api + datastore baseline",
      "request/response latency and auth-ready routes",
    ],
  },
  data_pipeline: {
    defaults: [
      "batch/event ingestion + transform + scheduled orchestration",
      "backfill, replay, and lineage-first operations model",
    ],
  },
  agent_platform: {
    defaults: [
      "multi-agent orchestration, tool contracts, and memory boundary docs",
      "human-approval checkpoints for agent execution and escalation",
    ],
  },
  internal_tooling: {
    defaults: [
      "operator workflows, RBAC/ABAC guardrails, and audit visibility",
      "service reliability and incident ergonomics for internal users",
    ],
  },
};
const DISCOVERY_PROVIDER_SPECS = {
  none: {
    provider_id: "none",
    label: "Deterministic Local",
    capabilities: ["deterministic_fallback"],
    default_model: "deterministic-v1",
  },
  openai: {
    provider_id: "openai",
    label: "OpenAI",
    capabilities: ["llm_json", "remote_api"],
    default_model: "gpt-5-mini",
  },
  codex_cli: {
    provider_id: "codex_cli",
    label: "Codex CLI",
    capabilities: ["llm_json", "local_cli"],
    default_model: "codex-cli-default",
  },
  claude_code: {
    provider_id: "claude_code",
    label: "Claude Code CLI",
    capabilities: ["llm_json", "local_cli"],
    default_model: "claude-code-default",
  },
};
const REQUIRED_MORADIN_PAYLOAD_INCLUDES = [
  "AGENTS.md",
  "FORGE.md",
  "Harness/moradin_payload/manifest.yaml",
  "Harness/entrypoints",
  "dev_tracker/ui/src",
  "docs/references",
  "scripts/moradin_forge.py",
];

const runtimeState = {
  last_sync_at: "",
  last_sync_result: "never",
  last_sync_duration_ms: 0,
  sync_count: 0,
  syncing: false,
  last_error: "",
};

const builderState = {
  recent_operations: [],
};

let syncQueue = Promise.resolve();
const activeSyncChildren = new Set();
const activeAssistantChildren = new Set();
const activeAssistantRuns = new Map();
let shuttingDown = false;
let shutdownPromise = null;
const ASSISTANT_OUTPUT_CAPTURE_LIMIT = 250_000;
const ASSISTANT_OUTPUT_TAIL_LIMIT = 6_000;

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    void shutdown(0, signal);
  });
}

await ensureRuntimeDirs();
await queueSync("control-api startup");

const server = http.createServer(async (req, res) => {
  setCorsHeaders(req, res);

  if (req.method === "OPTIONS") {
    const origin = getRequestOrigin(req);
    if (origin && !isTrustedOrigin(origin)) {
      res.writeHead(403);
      res.end();
      return;
    }
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url ?? "/", `http://${req.headers.host}`);

  try {
    assertTrustedOrigin(req);

    if (req.method === "GET" && url.pathname === "/") {
      json(res, 200, {
        service: "MoradinForgeWorkbenchControlApi",
        purpose: "Local control API for sync/status/git/builder/discovery.",
        ui_url: uiPreferredUrl,
        ui_loopback_url: uiLoopbackUrl,
        ...(uiWslUrl ? { ui_wsl_url: uiWslUrl } : {}),
        api_endpoints: [
          "/api/status",
          "/api/git",
          "/api/sync",
          "/api/moradin/readiness",
          "/api/moradin/install-request",
          "/api/moradin/repo-registry",
          "/api/review/queue",
          "/api/builder/status",
          "/api/builder/providers",
          "/api/builder/create-local-repo",
          "/api/builder/repo-completeness",
          "/api/builder/project-scan",
          "/api/builder/deploy-existing",
          "/api/builder/project-status",
          "/api/builder/project-status/history",
          "/api/builder/generate-from-discovery",
          "/api/builder/import-harness-bundle",
          "/api/builder/import-harness-path",
          "/api/builder/remote/ssh/test",
          "/api/builder/remote/ssh/execute",
          "/api/discovery/session/start",
          "/api/discovery/session/answer",
          "/api/discovery/session/generate",
          "/api/discovery/session/build-prompt-bundle",
          "/api/discovery/session/build-follow-on-plan",
          "/api/discovery/session/:session_id",
          "/api/assistant/run",
        ],
      });
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/status") {
      const status = await buildStatusResponse();
      json(res, 200, status);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/git") {
      const git = await safeReadJson(
        path.join(generatedRoot, "git_state_v1.json"),
        { version: "GitStateV1" },
      );
      json(res, 200, git);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/review/queue") {
      const queue = await buildReviewQueueResponse();
      json(res, 200, queue);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/moradin/readiness") {
      const readiness = await buildMoradinReadiness();
      json(res, 200, readiness);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/moradin/install-request"
    ) {
      const payload = await readJsonBody(req);
      const request = await createMoradinInstallRequest(payload);
      json(res, 200, request);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/moradin/repo-registry") {
      const registry = await buildMoradinRepoRegistry();
      json(res, 200, registry);
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/sync") {
      await queueSync("manual api sync");
      const status = await buildStatusResponse();
      json(res, 200, status);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/builder/status") {
      const status = await buildBuilderStatus();
      json(res, 200, status);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/builder/providers") {
      const providers = await buildBuilderProviders();
      json(res, 200, providers);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/create-local-repo"
    ) {
      const payload = await readJsonBody(req);
      const result = await createLocalRepo(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/repo-completeness"
    ) {
      const payload = await readJsonBody(req);
      const result = await checkBuilderRepoCompleteness(payload);
      json(res, 200, result);
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/builder/project-scan") {
      const payload = await readJsonBody(req);
      const result = await scanExistingProject(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/deploy-existing"
    ) {
      const payload = await readJsonBody(req);
      const result = await deployExistingProject(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/project-status"
    ) {
      const payload = await readJsonBody(req);
      const result = await buildProjectStatusReport(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "GET" &&
      url.pathname === "/api/builder/project-status/history"
    ) {
      let remoteTarget = null;
      const remoteTargetRaw = String(
        url.searchParams.get("remote_target") ?? "",
      ).trim();
      if (remoteTargetRaw) {
        try {
          remoteTarget = JSON.parse(remoteTargetRaw);
        } catch {
          throw new ApiError(
            400,
            "invalid_remote_target",
            "remote_target query value must be valid JSON.",
          );
        }
      }
      const result = await buildProjectStatusHistoryResponse({
        target_repo: String(url.searchParams.get("target_repo") ?? ""),
        limit: url.searchParams.get("limit"),
        target_mode: String(url.searchParams.get("target_mode") ?? ""),
        remote_target: remoteTarget,
      });
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/generate-from-discovery"
    ) {
      const payload = await readJsonBody(req);
      const result = await generateProjectRepoFromDiscovery(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/import-harness-path"
    ) {
      const payload = await readJsonBody(req);
      const result = await importHarnessPath(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/import-harness-bundle"
    ) {
      const payload = await readJsonBody(req, 80 * 1024 * 1024);
      const result = await importHarnessBundle(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/remote/ssh/test"
    ) {
      const payload = await readJsonBody(req);
      const result = await testRemoteSsh(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/builder/remote/ssh/execute"
    ) {
      const payload = await readJsonBody(req);
      const result = await executeRemoteSsh(payload);
      json(res, 200, result);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/discovery/session/start"
    ) {
      const payload = await readJsonBody(req);
      const session = await startDiscoverySession(payload);
      json(res, 200, session);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/discovery/session/answer"
    ) {
      const payload = await readJsonBody(req);
      const session = await answerDiscoverySession(payload);
      json(res, 200, session);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/discovery/session/generate"
    ) {
      const payload = await readJsonBody(req);
      const session = await generateDiscoverySession(payload);
      json(res, 200, session);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/discovery/session/build-prompt-bundle"
    ) {
      const payload = await readJsonBody(req);
      const bundle = await buildPromptBundleForSession(payload);
      json(res, 200, bundle);
      return;
    }

    if (
      req.method === "POST" &&
      url.pathname === "/api/discovery/session/build-follow-on-plan"
    ) {
      const payload = await readJsonBody(req);
      const result = await buildFollowOnPlanForSession(payload);
      json(res, 200, result);
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/assistant/run") {
      const payload = await readJsonBody(req);
      const result = await startAssistantRun(payload);
      json(res, 200, result);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/assistant/runs") {
      const limit = parseBoundedInteger(url.searchParams.get("limit"), 8, {
        min: 1,
        max: 50,
      });
      json(res, 200, await buildAssistantRunListResponse(limit));
      return;
    }

    if (
      req.method === "GET" &&
      url.pathname.startsWith("/api/assistant/run/")
    ) {
      const runId = decodeURIComponent(
        url.pathname.replace("/api/assistant/run/", ""),
      ).trim();
      if (!runId) {
        throw new ApiError(
          400,
          "invalid_run_id",
          "run_id is required in path.",
        );
      }
      const run = await loadAssistantRunRecord(runId);
      if (!run) {
        throw new ApiError(
          404,
          "assistant_run_not_found",
          "Assistant run was not found.",
        );
      }
      json(res, 200, run);
      return;
    }

    if (
      req.method === "GET" &&
      url.pathname.startsWith("/api/discovery/session/")
    ) {
      const sessionId = decodeURIComponent(
        url.pathname.replace("/api/discovery/session/", ""),
      ).trim();
      if (!sessionId) {
        throw new ApiError(
          400,
          "invalid_session_id",
          "session_id is required in path.",
        );
      }
      const session = await loadDiscoverySession(sessionId);
      json(res, 200, session);
      return;
    }

    json(res, 404, {
      error: "not_found",
      path: url.pathname,
    });
  } catch (error) {
    if (error instanceof ApiError) {
      json(res, error.statusCode, {
        error: error.code,
        message: error.message,
        detail: error.detail,
      });
      return;
    }

    json(res, 500, {
      error: "internal_error",
      message: String(error),
    });
  }
});

await startServer();

function queueSync(reason) {
  syncQueue = syncQueue.then(() => runSync(reason));
  return syncQueue;
}

function runSync(reason) {
  return new Promise((resolve, reject) => {
    if (shuttingDown) {
      resolve();
      return;
    }
    if (runtimeState.syncing) {
      resolve();
      return;
    }

    runtimeState.syncing = true;
    const started = Date.now();
    process.stdout.write(`[control-api] sync start (${reason})\n`);

    const child = spawn(process.execPath, [syncScriptPath], {
      stdio: "inherit",
      env: process.env,
    });
    activeSyncChildren.add(child);

    child.on("exit", (code) => {
      activeSyncChildren.delete(child);
      runtimeState.syncing = false;
      runtimeState.last_sync_at = new Date().toISOString();
      runtimeState.last_sync_duration_ms = Date.now() - started;
      runtimeState.sync_count += 1;

      if (code === 0) {
        runtimeState.last_sync_result = "success";
        runtimeState.last_error = "";
        resolve();
      } else {
        runtimeState.last_sync_result = "failed";
        runtimeState.last_error = `sync-docs exited with code ${code}`;
        reject(new Error(runtimeState.last_error));
      }
    });

    child.on("error", (error) => {
      activeSyncChildren.delete(child);
      runtimeState.syncing = false;
      runtimeState.last_sync_at = new Date().toISOString();
      runtimeState.last_sync_duration_ms = Date.now() - started;
      runtimeState.sync_count += 1;
      runtimeState.last_sync_result = "failed";
      runtimeState.last_error = String(error);
      reject(error);
    });
  });
}

function startServer() {
  return new Promise((resolve, reject) => {
    const handleError = (error) => {
      reject(error);
    };

    server.once("error", handleError);
    server.listen(port, "127.0.0.1", () => {
      server.off("error", handleError);
      const uiTargets = [
        uiPreferredUrl,
        uiLoopbackUrl,
        ...(uiWslUrl ? [uiWslUrl] : []),
      ].join(", ");
      process.stdout.write(
        `[control-api] listening on http://127.0.0.1:${port} (UI bind ${uiHost}; browser targets ${uiTargets}; remote tunnel ssh -L ${uiPort}:127.0.0.1:${uiPort} <linux-host>)\n`,
      );
      if (!isWslRuntime() && !isLoopbackBindHost(uiHost)) {
        process.stdout.write(
          `[control-api] warning: non-loopback UI bind '${uiHost}' is outside current-scope release support. Keep remote hosts loopback-only and use SSH local port forwarding.\n`,
        );
      }
      resolve();
    });
  }).catch(async (error) => {
    process.stderr.write(`${formatListenError(error)}\n`);
    await shutdown(1, "listen_error");
  });
}

function formatListenError(error) {
  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    error.code === "EADDRINUSE"
  ) {
    return `[control-api] port ${port} is already in use on 127.0.0.1:${port}. If this is an existing Moradins Harness instance, rerun ./harness_devops.sh --restart-existing or stop it first.`;
  }
  return `[control-api] failed to start on 127.0.0.1:${port}: ${String(error)}`;
}

function shutdown(code, reason) {
  if (shutdownPromise) {
    return shutdownPromise;
  }

  shuttingDown = true;
  process.stdout.write(`[control-api] shutting down (${reason})\n`);

  shutdownPromise = (async () => {
    for (const child of activeSyncChildren) {
      try {
        child.kill("SIGTERM");
      } catch {
        // Ignore dead children during shutdown.
      }
    }

    for (const child of activeAssistantChildren) {
      try {
        child.kill("SIGTERM");
      } catch {
        // Ignore dead children during shutdown.
      }
    }

    await new Promise((resolve) => {
      try {
        server.close(() => resolve());
      } catch {
        resolve();
      }
    });

    process.exit(code);
  })();

  return shutdownPromise;
}

async function buildStatusResponse() {
  const runtime = await safeReadJson(
    path.join(generatedRoot, "runtime_status.json"),
    {},
  );
  const snapshot = await safeReadJson(
    path.join(generatedRoot, "tracker_snapshot_v1.json"),
    {
      version: "TrackerSnapshotV5",
      generated_at: "",
      summary: {},
    },
  );

  return {
    api: "TrackerControlStatusV1",
    runtime_state: runtimeState,
    runtime_snapshot: runtime,
    tracker_snapshot: {
      version: snapshot.version,
      generated_at: snapshot.generated_at,
      summary: snapshot.summary,
    },
    ui_access: buildUiAccessStatus(),
    assistant_runtimes: {
      codex_cli: buildAssistantRuntimeStatus("codex_cli"),
      claude_code: buildAssistantRuntimeStatus("claude_code"),
    },
    remote_ssh: {
      feature_flag_enabled: sshRemoteEnabled,
      ssh_binary_available: commandExists("ssh"),
      allowed_command_prefixes: [...sshAllowedCommands],
      mode: sshRemoteEnabled ? "guarded" : "disabled",
    },
    builder_feature_flags: {
      managed_by: "environment",
      existing_project_mode_enabled: existingProjectModeEnabled,
      allowlisted_root: disclosePath(allowlistedRoot),
      path_disclosure_mode: pathDisclosureMode,
      scan_limits_defaults: {
        max_depth: scanMaxDepthDefault,
        max_files: scanMaxFilesDefault,
      },
      project_status_history_retention: projectStatusHistoryMaxEntries,
    },
  };
}

async function buildReviewQueueResponse() {
  const snapshot = await safeReadJson(
    path.join(generatedRoot, "tracker_snapshot_v1.json"),
    null,
  );
  if (snapshot?.review_queue?.version === "ReviewQueueV1") {
    return snapshot.review_queue;
  }

  const docs = Array.isArray(snapshot?.docs) ? snapshot.docs : [];
  const queueSpecs = [
    {
      queue_id: "updates",
      label: "Updates",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/updates/active/") &&
        !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "upgrades",
      label: "Upgrades",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/upgrades/active/") &&
        !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "tooling",
      label: "Tooling",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/tooling/active/") &&
        !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "suggestions",
      label: "Suggestions",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/implementation/active/sug_") &&
        !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "governance",
      label: "Governance",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/implementation/active/") &&
        !relativePath.endsWith("/index.md") &&
        !path.basename(relativePath).startsWith("sug_"),
    },
  ];

  const queues = queueSpecs.map((spec) => {
    const rows = docs
      .filter((doc) => spec.include(String(doc.relative_path ?? "")))
      .map((doc) => {
        const status = String(doc.status ?? "");
        const normalized = status.trim().toLowerCase();
        const actionable = !new Set([
          "implemented",
          "closed",
          "archived",
          "completed",
          "rejected",
          "cancelled",
          "superseded",
          "done",
        ]).has(normalized);
        return {
          doc_id: String(doc.id ?? ""),
          relative_path: String(doc.relative_path ?? ""),
          title: String(doc.title ?? ""),
          status,
          owner: String(doc.owner ?? ""),
          actionable,
        };
      });
    return {
      queue_id: spec.queue_id,
      label: spec.label,
      active_docs: rows.length,
      actionable_docs: rows.filter((row) => row.actionable).length,
      implemented_docs: rows.filter((row) => !row.actionable).length,
      rows,
    };
  });

  const queueById = Object.fromEntries(
    queues.map((queue) => [queue.queue_id, queue]),
  );
  const pendingApprovals = Number(
    snapshot?.changelog?.awaiting_human_review_count ?? 0,
  );
  return {
    version: "ReviewQueueV1",
    generated_at: new Date().toISOString(),
    pending_approvals: pendingApprovals,
    pending_total: queues.reduce(
      (sum, queue) => sum + queue.actionable_docs,
      0,
    ),
    queues,
    zero_state: {
      updates: (queueById.updates?.actionable_docs ?? 0) === 0,
      upgrades: (queueById.upgrades?.actionable_docs ?? 0) === 0,
      tooling: (queueById.tooling?.actionable_docs ?? 0) === 0,
      suggestions: (queueById.suggestions?.actionable_docs ?? 0) === 0,
    },
    reconciliation: {
      status: "warn",
      issues: [
        "Review queue served from fallback. Run sync-docs to generate TrackerSnapshotV5 queue metadata.",
      ],
    },
  };
}

async function buildMoradinReadiness() {
  const groups = [];
  for (const groupSpec of buildMoradinToolingSpecs()) {
    const checks = groupSpec.checks.map((checkSpec) =>
      buildMoradinToolCheck(checkSpec),
    );
    groups.push({
      group_id: groupSpec.group_id,
      label: groupSpec.label,
      required: checks.some((check) => check.required),
      summary: {
        total: checks.length,
        present_count: checks.filter((check) => check.status === "present")
          .length,
        missing_count: checks.filter((check) => check.status === "missing")
          .length,
        manual_count: checks.filter((check) => check.status === "manual")
          .length,
      },
      checks,
    });
  }

  const allChecks = groups.flatMap((group) => group.checks);
  const requiredMissing = allChecks.filter(
    (check) => check.required && check.status === "missing",
  );
  const optionalMissing = allChecks.filter(
    (check) => !check.required && check.status === "missing",
  );
  const installGuidance = [...requiredMissing, ...optionalMissing].map(
    (check) => ({
      tool_id: check.tool_id,
      label: check.label,
      required: check.required,
      install_commands: check.install_commands,
      verify_command: check.verify_command,
      runbook_refs: check.runbook_refs,
      note:
        "Request-only. Moradin records these commands for a human operator and never runs host installs from the UI.",
    }),
  );

  const payloadManifest = await loadMoradinPayloadManifest();

  return {
    version: "MoradinToolingReadinessV1",
    generated_at: new Date().toISOString(),
    request_only: true,
    payload_manifest: {
      manifest_path: MORADIN_PAYLOAD_MANIFEST_RELATIVE_PATH,
      payload_id: payloadManifest.payload_id,
      payload_version: payloadManifest.payload_version,
      include_count: payloadManifest.include_paths.length,
      exclude_count: payloadManifest.exclude_paths.length,
      sidecar_default_dir: payloadManifest.sidecar_default_dir,
    },
    summary: {
      total: allChecks.length,
      present_count: allChecks.filter((check) => check.status === "present")
        .length,
      missing_count: allChecks.filter((check) => check.status === "missing")
        .length,
      manual_count: allChecks.filter((check) => check.status === "manual")
        .length,
      required_missing_count: requiredMissing.length,
      optional_missing_count: optionalMissing.length,
      overall_status:
        requiredMissing.length > 0
          ? "action_required"
          : optionalMissing.length > 0
            ? "optional_attention"
            : "ready",
    },
    groups,
    install_guidance: installGuidance,
    artifact_roots: {
      install_requests: INSTALL_REQUESTS_RELATIVE_ROOT,
      repo_registry: REPO_REGISTRY_RELATIVE_ROOT,
    },
  };
}

async function createMoradinInstallRequest(payload) {
  const readiness = await buildMoradinReadiness();
  const allChecks = readiness.groups.flatMap((group) => group.checks);
  const byId = new Map(allChecks.map((check) => [check.tool_id, check]));
  const requestedIdsRaw = Array.isArray(payload?.tool_ids)
    ? payload.tool_ids
    : [];
  const requestedIds = requestedIdsRaw
    .map((value) => String(value ?? "").trim())
    .filter((value, index, values) => value && values.indexOf(value) === index);
  const selectedChecks =
    requestedIds.length > 0
      ? requestedIds.map((toolId) => byId.get(toolId)).filter(Boolean)
      : allChecks.filter((check) => check.status === "missing");

  if (requestedIds.some((toolId) => !byId.has(toolId))) {
    const unknownToolIds = requestedIds.filter((toolId) => !byId.has(toolId));
    throw new ApiError(
      400,
      "unknown_tool_id",
      `Unknown tooling request id: ${unknownToolIds.join(", ")}`,
      { known_tool_ids: [...byId.keys()] },
    );
  }

  const requestId = buildInstallRequestId();
  const requestRoot = path.join(installRequestsRoot, requestId);
  await fs.mkdir(requestRoot, { recursive: true });

  const operatorNote = String(payload?.operator_note ?? "").trim();
  const assistantModeRaw = String(payload?.assistant_mode ?? "manual_handoff")
    .trim()
    .toLowerCase();
  const assistantMode = [
    "codex_cli",
    "codex_app_manual_handoff",
    "claude_code",
    "manual_handoff",
  ].includes(assistantModeRaw)
    ? assistantModeRaw
    : "manual_handoff";
  const commandRows = selectedChecks.flatMap((check) =>
    check.install_commands.map((command) => ({
      tool_id: check.tool_id,
      label: check.label,
      command,
      verify_command: check.verify_command,
      required: check.required,
    })),
  );
  const jsonPath = path.join(requestRoot, "install_request.json");
  const markdownPath = path.join(requestRoot, "install_request.md");
  const createdAt = new Date().toISOString();
  const request = {
    version: "MoradinInstallRequestV1",
    request_id: requestId,
    created_at: createdAt,
    request_only: true,
    assistant_mode: assistantMode,
    operator_note: operatorNote,
    status: commandRows.length > 0 ? "requested" : "no_missing_tools",
    selected_tools: selectedChecks.map((check) => ({
      tool_id: check.tool_id,
      label: check.label,
      status: check.status,
      required: check.required,
      install_commands: check.install_commands,
      verify_command: check.verify_command,
      runbook_refs: check.runbook_refs,
    })),
    commands: commandRows,
    safety:
      "Moradin does not execute these commands. A human operator must review and run any install command from a shell they control.",
    artifact_paths: {
      json: `${INSTALL_REQUESTS_RELATIVE_ROOT}/${requestId}/install_request.json`,
      markdown: `${INSTALL_REQUESTS_RELATIVE_ROOT}/${requestId}/install_request.md`,
    },
  };

  const markdown = renderInstallRequestMarkdown(request);
  await fs.writeFile(jsonPath, `${JSON.stringify(request, null, 2)}\n`, "utf8");
  await fs.writeFile(markdownPath, `${markdown}\n`, "utf8");
  return request;
}

async function buildMoradinRepoRegistry() {
  await fs.mkdir(allowlistedRoot, { recursive: true });
  await fs.mkdir(repoRegistryRoot, { recursive: true });

  const repos = [];
  repos.push(
    await buildMoradinRepoRegistryRecord({
      repoName: "moradin-harness-manager",
      repoPath: repoRoot,
      scope: "manager",
    }),
  );

  const entries = await fs.readdir(allowlistedRoot, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const repoPath = path.join(allowlistedRoot, entry.name);
    repos.push(
      await buildMoradinRepoRegistryRecord({
        repoName: entry.name,
        repoPath,
        scope: "tracked",
      }),
    );
  }

  repos.sort((left, right) => {
    if (left.scope !== right.scope) {
      return left.scope === "manager" ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });

  const registry = {
    version: "MoradinRepoRegistryV1",
    generated_at: new Date().toISOString(),
    allowlisted_root: disclosePath(allowlistedRoot),
    path_disclosure_mode: pathDisclosureMode,
    summary: {
      total_repos: repos.length,
      tracked_repos: repos.filter((repo) => repo.scope === "tracked").length,
      git_initialized_count: repos.filter((repo) => repo.git_initialized)
        .length,
      moradin_sidecar_count: repos.filter((repo) => repo.moradin_sidecar_present)
        .length,
      reusable_artifact_count: repos.filter(
        (repo) => repo.artifact_reuse?.latest_status_report,
      ).length,
    },
    repositories: repos,
    adapter_contract: {
      source_pattern: "repo-owned generated tooling adapters",
      preferred_commands: [
        "make repo-brief",
        "make verify-fast",
        "make review-ready",
      ],
      artifact_root: REPO_REGISTRY_RELATIVE_ROOT,
    },
  };

  const jsonPath = path.join(repoRegistryRoot, "repositories.json");
  const markdownPath = path.join(repoRegistryRoot, "repositories.md");
  await fs.writeFile(
    jsonPath,
    `${JSON.stringify(registry, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(
    markdownPath,
    `${renderRepoRegistryMarkdown(registry)}\n`,
    "utf8",
  );

  return registry;
}

async function buildBuilderStatus() {
  await fs.mkdir(allowlistedRoot, { recursive: true });
  const entries = await fs.readdir(allowlistedRoot, { withFileTypes: true });
  const repos = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }

    const repoPath = path.join(allowlistedRoot, entry.name);
    const gitPath = path.join(repoPath, ".git");
    const hasGit = await pathExists(gitPath);
    repos.push({
      name: entry.name,
      path: repoPath,
      git_initialized: hasGit,
    });
  }

  repos.sort((a, b) => a.name.localeCompare(b.name));

  return {
    version: "BuilderStatusV1",
    existing_project_mode_enabled: existingProjectModeEnabled,
    allowlisted_root: disclosePath(allowlistedRoot),
    path_disclosure_mode: pathDisclosureMode,
    scan_limits_defaults: {
      max_depth: scanMaxDepthDefault,
      max_files: scanMaxFilesDefault,
    },
    project_status_history_retention: projectStatusHistoryMaxEntries,
    known_repos: repos.map((repo) => ({
      ...repo,
      path: disclosePath(repo.path),
    })),
    recent_operations: builderState.recent_operations.map((row) => ({
      ...row,
      destination_path: disclosePath(row.destination_path),
      detail: discloseText(row.detail),
      target_repo: row.target_repo ? discloseText(row.target_repo) : "",
      sidecar_path: row.sidecar_path ? disclosePath(row.sidecar_path) : "",
    })),
  };
}

async function buildBuilderProviders() {
  const providerIds = ["none", "openai", "codex_cli", "claude_code"];
  const providers = [];

  for (const providerId of providerIds) {
    const spec = DISCOVERY_PROVIDER_SPECS[providerId];
    const availability = await detectProviderAvailability(providerId);
    providers.push({
      provider_id: spec.provider_id,
      label: spec.label,
      capabilities: [...spec.capabilities],
      availability_status: availability.available ? "available" : "unavailable",
      detail: availability.detail,
      default_model: spec.default_model,
    });
  }

  return {
    version: "BuilderProviderListV1",
    providers,
  };
}

function buildMoradinToolingSpecs() {
  const readinessRunbook =
    "docs/references/tooling_readiness_install_request_contract_v1.md";
  return [
    {
      group_id: "host_baseline",
      label: "Host Baseline",
      checks: [
        {
          tool_id: "git",
          label: "Git",
          command: "git",
          required: true,
          version_args: ["--version"],
          install_commands: ["sudo apt-get update && sudo apt-get install -y git"],
          verify_command: "git --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "uv",
          label: "uv",
          command: "uv",
          required: true,
          version_args: ["--version"],
          install_commands: ["curl -LsSf https://astral.sh/uv/install.sh | sh"],
          verify_command: "uv --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "node",
          label: "Node.js",
          command: "node",
          required: true,
          version_args: ["--version"],
          install_commands: [
            "sudo apt-get update && sudo apt-get install -y nodejs npm",
          ],
          verify_command: "node --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "npm",
          label: "npm",
          command: "npm",
          required: true,
          version_args: ["--version"],
          install_commands: [
            "sudo apt-get update && sudo apt-get install -y nodejs npm",
          ],
          verify_command: "npm --version",
          runbook_refs: [readinessRunbook],
        },
      ],
    },
    {
      group_id: "assistant_handoffs",
      label: "Assistant Handoffs",
      checks: [
        {
          tool_id: "codex_cli",
          label: "Codex CLI",
          command: String(process.env.CODEX_CLI_COMMAND ?? "codex").trim() || "codex",
          required: false,
          version_args: ["--version"],
          install_commands: ["npm install -g @openai/codex"],
          verify_command: `${String(process.env.CODEX_CLI_COMMAND ?? "codex").trim() || "codex"} --version`,
          runbook_refs: [readinessRunbook, "docs/references/assistant_handoff_contract_v1.md"],
        },
        {
          tool_id: "codex_app_manual_handoff",
          label: "Codex App Manual Handoff",
          manual: true,
          required: false,
          install_commands: [],
          verify_command:
            "Use Moradin prompt artifacts with the Codex app manual paste flow.",
          runbook_refs: ["docs/references/assistant_handoff_contract_v1.md"],
        },
        {
          tool_id: "claude_code",
          label: "Claude Code CLI",
          command:
            String(process.env.CLAUDE_CODE_COMMAND ?? "claude").trim() ||
            "claude",
          required: false,
          version_args: ["--version"],
          install_commands: ["npm install -g @anthropic-ai/claude-code"],
          verify_command: `${String(process.env.CLAUDE_CODE_COMMAND ?? "claude").trim() || "claude"} --version`,
          runbook_refs: [readinessRunbook, "docs/references/assistant_handoff_contract_v1.md"],
        },
      ],
    },
    {
      group_id: "moradin_helpers",
      label: "Moradin Shell And Docker Bridge",
      checks: [
        {
          tool_id: "tpldeck",
          label: "tpldeck shell helper",
          command: "tpldeck",
          required: false,
          version_args: ["--help"],
          install_commands: [],
          verify_command: "command -v tpldeck",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "uvbootstrap",
          label: "uvbootstrap shell helper",
          command: "uvbootstrap",
          required: false,
          version_args: ["--help"],
          install_commands: [],
          verify_command: "command -v uvbootstrap",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "codex_run",
          label: "codex-run Docker bridge",
          command: "codex-run",
          required: false,
          version_args: ["--help"],
          install_commands: [],
          verify_command: "command -v codex-run",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "codex_docker",
          label: "codex-docker Docker bridge",
          command: "codex-docker",
          required: false,
          version_args: ["--help"],
          install_commands: [],
          verify_command: "command -v codex-docker",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "codex_exec",
          label: "codex-exec Docker bridge",
          command: "codex-exec",
          required: false,
          version_args: ["--help"],
          install_commands: [],
          verify_command: "command -v codex-exec",
          runbook_refs: [readinessRunbook],
        },
      ],
    },
    {
      group_id: "optional_scanners",
      label: "Optional Scanners",
      checks: [
        {
          tool_id: "gitleaks",
          label: "gitleaks",
          command: "gitleaks",
          required: false,
          version_args: ["version"],
          install_commands: ["sudo apt-get update && sudo apt-get install -y gitleaks"],
          verify_command: "gitleaks version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "trivy",
          label: "Trivy",
          command: "trivy",
          required: false,
          version_args: ["--version"],
          install_commands: ["sudo apt-get update && sudo apt-get install -y trivy"],
          verify_command: "trivy --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "actionlint",
          label: "actionlint",
          command: "actionlint",
          required: false,
          version_args: ["--version"],
          install_commands: ["sudo apt-get update && sudo apt-get install -y actionlint"],
          verify_command: "actionlint --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "zizmor",
          label: "zizmor",
          command: "zizmor",
          required: false,
          version_args: ["--version"],
          install_commands: ["uv tool install zizmor"],
          verify_command: "zizmor --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "conftest",
          label: "Conftest",
          command: "conftest",
          required: false,
          version_args: ["--version"],
          install_commands: ["sudo apt-get update && sudo apt-get install -y conftest"],
          verify_command: "conftest --version",
          runbook_refs: [readinessRunbook],
        },
        {
          tool_id: "yamllint",
          label: "yamllint",
          command: "yamllint",
          required: false,
          version_args: ["--version"],
          install_commands: ["uv tool install yamllint"],
          verify_command: "yamllint --version",
          runbook_refs: [readinessRunbook],
        },
      ],
    },
  ];
}

function buildMoradinToolCheck(spec) {
  if (spec.manual) {
    return {
      tool_id: spec.tool_id,
      label: spec.label,
      required: Boolean(spec.required),
      status: "manual",
      command: "",
      detected_path: "",
      version: "",
      detail:
        "Manual handoff mode uses Moradin prompt artifacts and does not require a local CLI binary.",
      install_commands: [...(spec.install_commands ?? [])],
      verify_command: spec.verify_command ?? "",
      runbook_refs: [...(spec.runbook_refs ?? [])],
    };
  }

  const command = String(spec.command ?? "").trim();
  const available = Boolean(command) && commandExists(command);
  const detectedPath = available ? commandPath(command) : "";
  const version = available
    ? commandVersion(command, spec.version_args ?? ["--version"])
    : "";
  return {
    tool_id: spec.tool_id,
    label: spec.label,
    required: Boolean(spec.required),
    status: available ? "present" : "missing",
    command,
    detected_path: discloseText(detectedPath),
    version,
    detail: available
      ? `${spec.label} is available.`
      : `${spec.label} is not available on the Linux host running Moradin.`,
    install_commands: [...(spec.install_commands ?? [])],
    verify_command: spec.verify_command ?? (command ? `${command} --version` : ""),
    runbook_refs: [...(spec.runbook_refs ?? [])],
  };
}

function commandPath(command) {
  try {
    return execFileSync("which", [command], {
      encoding: "utf8",
      env: process.env,
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 2_000,
    })
      .trim()
      .split(/\r?\n/)[0];
  } catch {
    return "";
  }
}

function commandVersion(command, args) {
  try {
    const output = execFileSync(command, args, {
      encoding: "utf8",
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 3_000,
    });
    return String(output ?? "")
      .trim()
      .split(/\r?\n/)[0]
      .slice(0, 240);
  } catch {
    return "";
  }
}

function buildInstallRequestId() {
  const timestamp = new Date()
    .toISOString()
    .replaceAll("-", "")
    .replaceAll(":", "")
    .replaceAll(".", "")
    .replace("T", "_")
    .slice(0, 20);
  const nonce = crypto.randomBytes(3).toString("hex");
  return `install_${timestamp}_${nonce}`;
}

function renderInstallRequestMarkdown(request) {
  const lines = [
    "# Moradin Install Request",
    "",
    `- request_id: ${request.request_id}`,
    `- created_at: ${request.created_at}`,
    `- assistant_mode: ${request.assistant_mode}`,
    `- request_only: ${request.request_only}`,
    `- status: ${request.status}`,
    "",
    "Moradin did not run any install command. Review these commands before running them from a human-controlled shell.",
  ];
  if (request.operator_note) {
    lines.push("", "## Operator Note", "", request.operator_note);
  }
  lines.push("", "## Requested Tools", "");
  if (request.selected_tools.length === 0) {
    lines.push("- No missing tools were selected.");
  } else {
    for (const tool of request.selected_tools) {
      lines.push(
        `- ${tool.label} (${tool.tool_id}): ${tool.status}; required=${tool.required}`,
      );
    }
  }
  lines.push("", "## Human-Run Commands", "");
  if (request.commands.length === 0) {
    lines.push("- No shell install commands are required for this request.");
  } else {
    for (const row of request.commands) {
      lines.push(`### ${row.label}`, "", "```bash", row.command, "```", "");
      if (row.verify_command) {
        lines.push("Verify:", "", "```bash", row.verify_command, "```", "");
      }
    }
  }
  return lines.join("\n").trimEnd();
}

async function buildMoradinRepoRegistryRecord({ repoName, repoPath, scope }) {
  const gitInitialized = await pathExists(path.join(repoPath, ".git"));
  const agentsPresent = await pathExists(path.join(repoPath, "AGENTS.md"));
  const sidecarPath = path.join(repoPath, ".moradins-harness");
  const sidecarPresent = await pathExists(sidecarPath);
  const makeTargets = await detectMakeTargets(repoPath);
  const packageManagers = await detectRepoPackageManagers(repoPath);
  const latestStatus = await findLatestProjectStatusArtifact(repoPath, repoName);
  const adapterSurfaces = {
    makefile_present: await pathExists(path.join(repoPath, "Makefile")),
    generated_tooling_present: await pathExists(path.join(repoPath, "tooling")),
    repo_brief_target: makeTargets.includes("repo-brief"),
    verify_fast_target: makeTargets.includes("verify-fast"),
    review_ready_target: makeTargets.includes("review-ready"),
  };

  return {
    repo_id:
      scope === "manager"
        ? "manager"
        : buildProjectStatusHistorySlug(normalizePath(repoPath)),
    name: repoName,
    scope,
    path: disclosePath(repoPath),
    git_initialized: gitInitialized,
    agents_present: agentsPresent,
    moradin_sidecar_present: sidecarPresent,
    moradin_sidecar_path: sidecarPresent ? disclosePath(sidecarPath) : "",
    package_managers: packageManagers,
    make_targets: makeTargets.slice(0, 40),
    adapter_surfaces: adapterSurfaces,
    artifact_reuse: {
      latest_status_report: latestStatus ? latestStatus.relative_path : "",
      latest_status_generated_at: latestStatus?.generated_at ?? "",
      project_status_slug: latestStatus?.target_slug ?? "",
    },
    brief: buildRepoRegistryBrief({
      repoName,
      scope,
      gitInitialized,
      agentsPresent,
      sidecarPresent,
      adapterSurfaces,
      packageManagers,
      latestStatus,
    }),
    rerun_advice: buildRepoRegistryRerunAdvice({
      agentsPresent,
      sidecarPresent,
      adapterSurfaces,
      latestStatus,
    }),
  };
}

async function detectMakeTargets(repoPath) {
  const makefilePath = path.join(repoPath, "Makefile");
  try {
    const content = await fs.readFile(makefilePath, "utf8");
    const targets = new Set();
    for (const match of content.matchAll(/^([A-Za-z0-9_.-]+):(?:\s|$)/gm)) {
      const target = String(match[1] ?? "").trim();
      if (target && target !== ".PHONY") {
        targets.add(target);
      }
    }
    return [...targets].sort((a, b) => a.localeCompare(b));
  } catch {
    return [];
  }
}

async function detectRepoPackageManagers(repoPath) {
  const checks = [
    ["npm", "package-lock.json"],
    ["npm", "package.json"],
    ["pnpm", "pnpm-lock.yaml"],
    ["yarn", "yarn.lock"],
    ["uv", "uv.lock"],
    ["pip", "requirements.txt"],
    ["poetry", "poetry.lock"],
    ["cargo", "Cargo.lock"],
    ["go", "go.mod"],
  ];
  const found = new Set();
  for (const [manager, marker] of checks) {
    if (await pathExists(path.join(repoPath, marker))) {
      found.add(manager);
    }
  }
  return [...found].sort((a, b) => a.localeCompare(b));
}

async function findLatestProjectStatusArtifact(repoPath, repoName) {
  const candidates = [
    buildProjectStatusHistorySlug(normalizePath(repoPath)),
    buildProjectStatusHistorySlug(repoName),
  ];
  for (const targetSlug of candidates) {
    const latestPath = path.join(projectStatusHistoryRoot, targetSlug, "latest.json");
    const report = await safeReadJson(latestPath, null);
    if (report?.version === "ProjectStatusReportV1") {
      return {
        target_slug: targetSlug,
        generated_at: String(report.generated_at ?? ""),
        relative_path: `${PROJECT_STATUS_HISTORY_RELATIVE_ROOT}/${targetSlug}/latest.json`,
      };
    }
  }
  return null;
}

function buildRepoRegistryBrief({
  repoName,
  scope,
  gitInitialized,
  agentsPresent,
  sidecarPresent,
  adapterSurfaces,
  packageManagers,
  latestStatus,
}) {
  const signals = [
    gitInitialized ? "git initialized" : "git missing",
    agentsPresent ? "AGENTS.md present" : "AGENTS.md missing",
    sidecarPresent ? "Moradin sidecar present" : "no Moradin sidecar",
    adapterSurfaces.repo_brief_target
      ? "repo brief target present"
      : "repo brief target missing",
    latestStatus ? "status artifact reusable" : "no reusable status artifact",
  ];
  const managers = packageManagers.length ? packageManagers.join(", ") : "none";
  return `${repoName} (${scope}) has ${signals.join("; ")}. Package manager signals: ${managers}.`;
}

function buildRepoRegistryRerunAdvice({
  agentsPresent,
  sidecarPresent,
  adapterSurfaces,
  latestStatus,
}) {
  if (!agentsPresent || !sidecarPresent) {
    return "Use Deploy -> Readiness, then Deploy -> Builder to adopt the repo with a bounded Moradin sidecar.";
  }
  if (!adapterSurfaces.repo_brief_target || !adapterSurfaces.verify_fast_target) {
    return "Refresh repo adapters, then run make repo-brief and make verify-fast from the target repo.";
  }
  if (!latestStatus) {
    return "Run Deploy -> Verify or make repo-brief to create a reusable status artifact before the next assistant handoff.";
  }
  return "Reuse the latest registry and status artifacts before rerunning scans; rerun make repo-brief after material changes.";
}

function renderRepoRegistryMarkdown(registry) {
  const lines = [
    "# Moradin Repo Registry",
    "",
    `- generated_at: ${registry.generated_at}`,
    `- allowlisted_root: ${registry.allowlisted_root}`,
    `- total_repos: ${registry.summary.total_repos}`,
    `- moradin_sidecar_count: ${registry.summary.moradin_sidecar_count}`,
    "",
    "| repo | scope | git | agents | sidecar | reusable status | advice |",
    "| --- | --- | --- | --- | --- | --- | --- |",
  ];
  for (const repo of registry.repositories) {
    lines.push(
      `| ${repo.name} | ${repo.scope} | ${repo.git_initialized ? "yes" : "no"} | ${repo.agents_present ? "yes" : "no"} | ${repo.moradin_sidecar_present ? "yes" : "no"} | ${repo.artifact_reuse.latest_status_report ? "yes" : "no"} | ${repo.rerun_advice.replaceAll("|", "\\|")} |`,
    );
  }
  return lines.join("\n");
}

async function createLocalRepo(payload) {
  const repoName = String(payload?.repo_name ?? "").trim();
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{1,63}$/.test(repoName)) {
    throw new ApiError(
      400,
      "invalid_repo_name",
      "repo_name must start with an alphanumeric character and use only letters, numbers, dot, underscore, or dash.",
    );
  }

  const destinationPath = await resolveDestinationPath(repoName);
  const overwrite = Boolean(payload?.overwrite);
  const initializeGit = payload?.initialize_git !== false;

  const prep = await prepareDestination({
    destinationPath,
    overwrite,
    confirmation: payload?.overwrite_confirmation,
  });
  if (!prep.canProceed) {
    await recordBuilderAudit({
      action: "create-local-repo",
      status: "rejected",
      destinationPath,
      detail: "overwrite confirmation required",
    });
    throw new ApiError(
      409,
      "overwrite_confirmation_required",
      "Destination exists and is not empty.",
      prep.conflict,
    );
  }

  await fs.mkdir(destinationPath, { recursive: true });
  const readmePath = path.join(destinationPath, "README.md");
  if (!(await pathExists(readmePath))) {
    const readme = `# ${repoName}\n\nBootstrapped by moradins-harness Builder.\n`;
    await fs.writeFile(readmePath, readme, "utf8");
  }

  if (
    initializeGit &&
    !(await pathExists(path.join(destinationPath, ".git")))
  ) {
    execFileSync("git", ["init"], { cwd: destinationPath, stdio: "ignore" });
  }

  await recordBuilderAudit({
    action: "create-local-repo",
    status: prep.overwrote ? "overwritten" : "created",
    destinationPath,
    detail: initializeGit ? "git initialized" : "git initialization skipped",
  });

  return {
    version: "CreateLocalRepoResponseV1",
    status: prep.overwrote ? "overwritten" : "created",
    repo_path: disclosePath(destinationPath),
    message: prep.overwrote
      ? "Repository path overwritten and initialized."
      : "Repository path created and initialized.",
  };
}

async function checkBuilderRepoCompleteness(payload) {
  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }

  const profileRaw = String(payload?.profile ?? "harness_core")
    .trim()
    .toLowerCase();
  if (profileRaw !== "harness_core" && profileRaw !== "minimal") {
    throw new ApiError(
      400,
      "invalid_profile",
      "profile must be one of: harness_core, minimal.",
    );
  }
  const profile = profileRaw;

  const destinationPath = await resolveDestinationPath(targetRepo);
  const groups = await buildRepoCompletenessGroups(destinationPath, profile);

  const checks = groups.flatMap((group) => group.checks);
  const passCount = checks.filter((check) => check.status === "pass").length;
  const missingCount = checks.length - passCount;

  await recordBuilderAudit({
    action: "repo-completeness",
    status: missingCount > 0 ? "incomplete" : "complete",
    destinationPath,
    detail: `profile=${profile}; pass=${passCount}; missing=${missingCount}`,
  });

  return {
    version: "BuilderRepoCompletenessResponseV1",
    target_repo: targetRepo,
    profile,
    checked_at: new Date().toISOString(),
    summary: {
      total: checks.length,
      pass_count: passCount,
      missing_count: missingCount,
    },
    groups,
  };
}

async function scanExistingProject(payload) {
  assertExistingProjectModeEnabled();

  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }

  const targetMode = normalizeTargetMode(
    payload?.target_mode,
    payload?.remote_target,
  );
  const remoteTarget =
    targetMode === "remote_ssh"
      ? normalizeRemoteTarget(payload?.remote_target ?? {})
      : null;
  let destinationPath = "";
  let scan = null;

  if (targetMode === "remote_ssh") {
    assertSshRemoteEnabled();
    scan = await runRemoteProjectBaselineScan({
      targetRepo,
      remoteTarget,
      scanLimits: normalizeScanLimits(payload?.scan_limits),
    });
  } else {
    destinationPath = await resolveDestinationPath(targetRepo);
    const destinationStats = await fs.lstat(destinationPath).catch(() => null);
    if (!destinationStats) {
      throw new ApiError(
        404,
        "target_repo_missing",
        "target_repo path does not exist.",
      );
    }
    if (!destinationStats.isDirectory()) {
      throw new ApiError(
        400,
        "target_repo_not_directory",
        "target_repo must resolve to an existing directory.",
      );
    }
    scan = await runProjectBaselineScan({
      targetRepo,
      destinationPath,
      scanLimits: normalizeScanLimits(payload?.scan_limits),
    });
  }

  const sessionId = String(payload?.session_id ?? "").trim();
  let artifactPaths = null;
  if (sessionId) {
    const session = await loadDiscoverySession(sessionId);
    artifactPaths = await writeProjectScanArtifacts(session.session_id, scan);
    session.project_scan_summary = {
      target_repo: targetRepo,
      scanned_at: scan.scanned_at,
      languages: [...scan.detected.languages],
      package_managers: [...scan.detected.package_managers],
      ci_surfaces: [...scan.detected.ci_surfaces],
      deployment_surfaces: [...scan.detected.deployment_surfaces],
      critical_gaps: [...scan.critical_gaps],
      target_mode: targetMode,
      remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
      scan_limits_effective: scan.scan_limits_effective ?? null,
      scan_truncated: Boolean(scan.scan_truncated),
      scan_truncation_reason: String(scan.scan_truncation_reason ?? ""),
    };
    session.project_scan_artifact_paths = {
      json: artifactPaths.json,
      markdown: artifactPaths.markdown,
    };
    session.updated_at = new Date().toISOString();
    await saveDiscoverySession(session);
    await writeDiscoveryPromptBundleArtifacts({
      session,
      stage: session.status === "synthesized" ? "synthesis" : "questions",
      selectedProfile: session.synthesis?.recommended_profile ?? "",
    });
  }

  await recordBuilderAudit({
    action: "project-scan",
    status: "scanned",
    destinationPath:
      targetMode === "remote_ssh"
        ? buildRemoteDestinationDescriptor(
            remoteTarget,
            buildRemoteRepoPath(remoteTarget, targetRepo),
          )
        : destinationPath,
    targetRepo,
    detail:
      `languages=${scan.detected.languages.length}; ci=${scan.detected.ci_surfaces.length}; gaps=${scan.critical_gaps.length}; ` +
      `depth=${scan.scan_limits_effective?.max_depth ?? scanMaxDepthDefault}; files=${scan.scan_limits_effective?.max_files ?? scanMaxFilesDefault}; ` +
      `truncated=${scan.scan_truncated ? "yes" : "no"}; mode=${targetMode}`,
  });

  return {
    ...scan,
    artifact_paths: artifactPaths,
    session_id: sessionId || "",
    target_mode: targetMode,
    remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
  };
}

async function deployExistingProject(payload) {
  assertExistingProjectModeEnabled();

  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }
  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }

  const mode = String(payload?.mode ?? "sidecar")
    .trim()
    .toLowerCase();
  if (mode !== "sidecar") {
    throw new ApiError(400, "invalid_deploy_mode", "mode must be sidecar.");
  }
  const sidecarDir = normalizeSidecarDir(
    payload?.sidecar_dir ?? ".moradins-harness",
  );
  const criticalGapPolicyRaw = String(
    payload?.critical_gap_policy ?? "block_with_override",
  )
    .trim()
    .toLowerCase();
  if (
    !["block_with_override", "warn_only", "hard_block"].includes(
      criticalGapPolicyRaw,
    )
  ) {
    throw new ApiError(
      400,
      "invalid_critical_gap_policy",
      "critical_gap_policy must be one of: block_with_override, warn_only, hard_block.",
    );
  }
  const criticalGapPolicy = criticalGapPolicyRaw;

  const session = await loadDiscoverySession(sessionId);
  if (!session?.synthesis) {
    throw new ApiError(
      409,
      "missing_synthesis",
      "Discovery session does not have synthesis output yet.",
    );
  }
  const scanSummary = isRecord(session.project_scan_summary)
    ? session.project_scan_summary
    : null;
  if (!scanSummary) {
    throw new ApiError(
      409,
      "missing_project_scan",
      "Discovery session does not include project scan context. Run project scan before deploy-existing.",
    );
  }
  const scanCriticalGaps = Array.isArray(scanSummary.critical_gaps)
    ? scanSummary.critical_gaps
        .map((value) => String(value ?? "").trim())
        .filter((value) => value.length > 0)
    : [];
  const criticalGapOverrideReason = String(
    payload?.critical_gap_override_reason ?? "",
  ).trim();
  const criticalGapOverrideConfirmation = String(
    payload?.critical_gap_override_confirmation ?? "",
  ).trim();
  const expectedCriticalGapOverride =
    buildCriticalGapOverrideConfirmation(targetRepo);
  const criticalGapOverrideApplied =
    scanCriticalGaps.length > 0 &&
    criticalGapPolicy === "block_with_override" &&
    criticalGapOverrideReason.length >= 12 &&
    criticalGapOverrideConfirmation === expectedCriticalGapOverride;
  const approvalGranted = await isDiscoveryApprovalGranted(sessionId);
  if (!approvalGranted) {
    throw new ApiError(
      409,
      "approval_required",
      "Discovery session is not approved. Mark approval artifact before deploying into existing project.",
      {
        approval_artifact_path: session.approval?.approval_artifact_path ?? "",
      },
    );
  }

  const targetMode = normalizeTargetMode(
    payload?.target_mode,
    payload?.remote_target,
  );
  const remoteTarget =
    targetMode === "remote_ssh"
      ? normalizeRemoteTarget(payload?.remote_target ?? {})
      : null;
  let destinationPath = "";
  let destinationDisplayPath = "";
  let sidecarPath = "";
  let sidecarDisplayPath = "";

  if (targetMode === "remote_ssh") {
    assertSshRemoteEnabled();
    const remoteRepoPath = buildRemoteRepoPath(remoteTarget, targetRepo);
    destinationDisplayPath = discloseText(remoteRepoPath);
    sidecarPath = path.posix.join(remoteRepoPath, sidecarDir);
    sidecarDisplayPath = discloseText(sidecarPath);
    await assertRemoteRepoDirectory(remoteTarget, remoteRepoPath);
  } else {
    destinationPath = await resolveDestinationPath(targetRepo);
    const destinationStats = await fs.lstat(destinationPath).catch(() => null);
    if (!destinationStats || !destinationStats.isDirectory()) {
      throw new ApiError(
        404,
        "target_repo_missing",
        "target_repo must resolve to an existing directory.",
      );
    }
    destinationDisplayPath = disclosePath(destinationPath);
    sidecarPath = path.join(destinationPath, sidecarDir);
    sidecarDisplayPath = disclosePath(sidecarPath);
  }

  if (scanCriticalGaps.length > 0 && criticalGapPolicy === "hard_block") {
    await recordBuilderAudit({
      action: "deploy-existing-sidecar",
      status: "rejected",
      destinationPath: sidecarPath,
      targetRepo,
      detail: `critical gaps hard block active; gaps=${scanCriticalGaps.length}`,
    });
    throw new ApiError(
      409,
      "critical_gaps_hard_blocked",
      "Deploy is blocked because critical project scan gaps are present and policy is hard_block.",
      {
        critical_gap_count: scanCriticalGaps.length,
        critical_gaps: scanCriticalGaps,
        critical_gap_policy: criticalGapPolicy,
      },
    );
  }

  if (
    scanCriticalGaps.length > 0 &&
    criticalGapPolicy === "block_with_override" &&
    !criticalGapOverrideApplied
  ) {
    await recordBuilderAudit({
      action: "deploy-existing-sidecar",
      status: "rejected",
      destinationPath: sidecarPath,
      targetRepo,
      detail: `critical gaps override required; gaps=${scanCriticalGaps.length}`,
    });
    throw new ApiError(
      409,
      "critical_gaps_blocked",
      "Deploy is blocked because critical project scan gaps are present. Provide override reason and confirmation token to continue.",
      {
        critical_gap_count: scanCriticalGaps.length,
        critical_gaps: scanCriticalGaps,
        critical_gap_policy: criticalGapPolicy,
        expected_override_confirmation: expectedCriticalGapOverride,
      },
    );
  }

  const overwriteSidecar = Boolean(payload?.overwrite_sidecar);
  const prep =
    targetMode === "remote_ssh"
      ? await prepareRemoteDestination({
          target: remoteTarget,
          remotePath: sidecarPath,
          overwrite: overwriteSidecar,
          confirmation: overwriteSidecar
            ? payload?.overwrite_confirmation
            : undefined,
        })
      : await prepareDestination({
          destinationPath: sidecarPath,
          overwrite: overwriteSidecar,
          confirmation: overwriteSidecar
            ? payload?.overwrite_confirmation
            : undefined,
        });
  if (!prep.canProceed) {
    await recordBuilderAudit({
      action: "deploy-existing-sidecar",
      status: "rejected",
      destinationPath: sidecarPath,
      targetRepo,
      sidecarPath,
      detail: "overwrite confirmation required",
    });
    throw new ApiError(
      409,
      "overwrite_confirmation_required",
      "Sidecar destination exists and is not empty.",
      prep.conflict,
    );
  }

  const generatedFiles = [];
  const profile =
    String(session.synthesis?.recommended_profile ?? "").trim() ||
    recommendProfile(session.intake);
  const tempRoot = await fs.mkdtemp(
    path.join(os.tmpdir(), "moradins-sidecar-"),
  );
  const buildRoot = path.join(tempRoot, sidecarDir);
  let validation = null;

  try {
    validation = await buildHarnessSidecarAtPath({
      destinationPath: buildRoot,
      profile,
      session,
      sessionId,
      generatedFiles,
    });
    if (targetMode === "remote_ssh") {
      await streamDirectoryToRemote({
        sourceDir: buildRoot,
        target: remoteTarget,
        remotePath: sidecarPath,
      });
    } else {
      await fs.mkdir(sidecarPath, { recursive: true });
      await copyDirectoryContentsSafe(buildRoot, sidecarPath, {
        skipGit: false,
      });
    }
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
  const templateFillMapArtifacts = await writeTemplateFillMapArtifacts({
    sessionId,
    workflowType: "existing_project",
    targetRepo,
    targetMode,
    profile,
    generatedFiles,
    scanSummary: session.project_scan_summary,
  });

  session.artifacts = {
    ...session.artifacts,
    deployed_sidecar_path: sidecarDisplayPath,
    template_fill_map_json: templateFillMapArtifacts.json,
    template_fill_map_markdown: templateFillMapArtifacts.markdown,
  };
  session.updated_at = new Date().toISOString();
  await saveDiscoverySession(session);

  await recordBuilderAudit({
    action: "deploy-existing-sidecar",
    status: prep.overwrote ? "overwritten" : "created",
    destinationPath: sidecarPath,
    targetRepo,
    sidecarPath,
    detail:
      `session=${sessionId}; profile=${profile}; validation=${validation.status}; ` +
      `critical_gap_policy=${criticalGapPolicy}; critical_gap_count=${scanCriticalGaps.length}; ` +
      `critical_gap_override=${criticalGapOverrideApplied ? "applied" : "none"}; mode=${targetMode}`,
  });

  const statusParams = new URLSearchParams({
    target: targetRepo,
    session: sessionId,
  });
  if (targetMode === "remote_ssh") {
    statusParams.set("target_mode", targetMode);
    statusParams.set("remote_target", JSON.stringify(remoteTarget));
  }

  return {
    version: "DeployExistingProjectResponseV1",
    status: prep.overwrote ? "overwritten" : "created",
    mode: "sidecar",
    session_id: sessionId,
    target_repo: targetRepo,
    target_mode: targetMode,
    remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
    destination_path: destinationDisplayPath,
    sidecar_path: sidecarDisplayPath,
    profile,
    harness_seed_version: HARNESS_SEED_VERSION,
    generated_files: generatedFiles.sort((a, b) => a.localeCompare(b)),
    template_fill_map_artifact_paths: templateFillMapArtifacts,
    validation,
    critical_gap_policy: criticalGapPolicy,
    critical_gap_count: scanCriticalGaps.length,
    critical_gap_override_applied: criticalGapOverrideApplied,
    status_route: `/project-status?${statusParams.toString()}`,
  };
}

async function buildProjectStatusReport(payload) {
  assertExistingProjectModeEnabled();

  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }
  const sessionId = String(payload?.session_id ?? "").trim();
  const targetMode = normalizeTargetMode(
    payload?.target_mode,
    payload?.remote_target,
  );
  const remoteTarget =
    targetMode === "remote_ssh"
      ? normalizeRemoteTarget(payload?.remote_target ?? {})
      : null;
  let destinationPath = "";
  let destinationDisplayPath = "";
  let targetKey = "";
  let scan = null;
  let groups = [];

  if (targetMode === "remote_ssh") {
    assertSshRemoteEnabled();
    const remoteRepoPath = buildRemoteRepoPath(remoteTarget, targetRepo);
    destinationDisplayPath = discloseText(remoteRepoPath);
    targetKey = buildRemoteDestinationDescriptor(remoteTarget, remoteRepoPath);
    scan = await runRemoteProjectBaselineScan({
      targetRepo,
      remoteTarget,
      scanLimits: normalizeScanLimits(null),
    });

    const remoteSidecarPath = path.posix.join(
      remoteRepoPath,
      ".moradins-harness",
    );
    const sidecarStatus = (
      await runRemoteShellText(
        remoteTarget,
        [
          `if [ -d ${sanitizeRemoteShellValue(remoteSidecarPath)} ]; then`,
          "printf 'present';",
          "else",
          "printf 'missing';",
          "fi",
        ].join(" "),
        { timeout: 12_000, maxBuffer: 1024 * 1024 },
      )
    )
      .trim()
      .toLowerCase();

    groups = [
      {
        group_id: "governance",
        label: "Harness Governance Readiness",
        checks: [
          {
            check_id: "remote-sidecar-default-path",
            label: "Default sidecar directory exists on remote target",
            status: sidecarStatus === "present" ? "pass" : "missing",
            detail:
              sidecarStatus === "present"
                ? `Detected ${discloseText(remoteSidecarPath)} on remote target.`
                : `Expected ${discloseText(remoteSidecarPath)} on remote target.`,
            path: discloseText(remoteSidecarPath),
          },
        ],
      },
    ];
  } else {
    destinationPath = await resolveDestinationPath(targetRepo);
    const destinationStats = await fs.lstat(destinationPath).catch(() => null);
    if (!destinationStats || !destinationStats.isDirectory()) {
      throw new ApiError(
        404,
        "target_repo_missing",
        "target_repo must resolve to an existing directory.",
      );
    }
    destinationDisplayPath = disclosePath(destinationPath);
    targetKey = destinationPath;
    [scan, groups] = await Promise.all([
      runProjectBaselineScan({
        targetRepo,
        destinationPath,
        scanLimits: normalizeScanLimits(null),
      }),
      buildRepoCompletenessGroups(destinationPath, "harness_core"),
    ]);
  }
  const reviewQueue = await buildReviewQueueResponse();
  let alignmentState = null;
  if (sessionId) {
    const session = await loadDiscoverySession(sessionId);
    const phasePlan = await loadDiscoveryPhasePlanArtifact(session);
    alignmentState = await buildAlignmentState({
      session,
      targetRepo,
      workflowType: session.project_scan_summary?.target_repo
        ? "existing_project"
        : "new_project",
      selectedProfile:
        String(session.synthesis?.recommended_profile ?? "").trim() ||
        recommendProfile(session.intake),
      phasePlan,
      targetMode,
      targetPath: destinationDisplayPath,
      reviewQueue,
      repoCompletenessGroups: groups,
    });
    await writeAlignmentStateArtifacts({ session, alignmentState });
  }

  const missingChecks = groups.flatMap((group) =>
    group.checks
      .filter((check) => check.status === "missing")
      .map((check) => ({
        group_id: group.group_id,
        group_label: group.label,
        check,
      })),
  );

  const actions = alignmentState ? buildProjectStatusActionsFromAlignment(alignmentState) : [];
  if (!alignmentState) {
    if (reviewQueue.pending_approvals > 0) {
      actions.push({
        action_id: "queue-pending-approvals",
        severity: "critical",
        title: "Resolve pending approvals",
        description: `${reviewQueue.pending_approvals} approval item(s) remain open before execution can continue.`,
        route: "/reviews/queue",
        depends_on: [],
        source: "review_queue.pending_approvals",
      });
    }

    for (const queueId of ["updates", "upgrades", "tooling", "suggestions"]) {
      const queue = reviewQueue.queues.find((row) => row.queue_id === queueId);
      if (!queue || queue.actionable_docs <= 0) {
        continue;
      }
      const severityByQueue = {
        updates: "high",
        upgrades: "high",
        tooling: "medium",
        suggestions: "low",
      };
      actions.push({
        action_id: `queue-${queueId}`,
        severity: severityByQueue[queueId],
        title: `Review actionable ${queue.label.toLowerCase()} items`,
        description: `${queue.actionable_docs} actionable item(s) detected in ${queue.label}.`,
        route: "/exchange",
        depends_on:
          reviewQueue.pending_approvals > 0 ? ["queue-pending-approvals"] : [],
        source: `review_queue.${queueId}.actionable_docs`,
      });
    }

    for (const row of missingChecks) {
      const severity =
        row.group_id === "foundations" || row.group_id === "governance"
          ? "high"
          : "medium";
      actions.push({
        action_id: `repo-gap-${row.check.check_id}`,
        severity,
        title: `Fill missing ${row.group_label} surface`,
        description: row.check.label,
        route: "/deploy/status",
        depends_on: [],
        source: `repo_completeness.${row.group_id}.${row.check.check_id}`,
      });
    }

    for (const [index, gap] of scan.critical_gaps.entries()) {
      actions.push({
        action_id: `scan-gap-${index + 1}`,
        severity: "high",
        title: "Resolve baseline project gap",
        description: gap,
        route: "/deploy/builder",
        depends_on: [],
        source: "project_scan.critical_gaps",
      });
    }
  }

  const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
  actions.sort((a, b) => {
    if (severityRank[a.severity] !== severityRank[b.severity]) {
      return severityRank[a.severity] - severityRank[b.severity];
    }
    if (a.depends_on.length !== b.depends_on.length) {
      return a.depends_on.length - b.depends_on.length;
    }
    return a.title.localeCompare(b.title);
  });

  const counts = alignmentState
    ? {
        critical: alignmentState.summary.critical_count,
        high: alignmentState.summary.high_count,
        medium: alignmentState.summary.medium_count,
        low: alignmentState.summary.low_count,
      }
    : {
        critical: actions.filter((row) => row.severity === "critical").length,
        high: actions.filter((row) => row.severity === "high").length,
        medium: actions.filter((row) => row.severity === "medium").length,
        low: actions.filter((row) => row.severity === "low").length,
      };
  const overallStatus = alignmentState
    ? alignmentState.summary.overall_status
    : counts.critical > 0
      ? "critical"
      : counts.high > 0 || counts.medium > 0
        ? "attention"
        : "ready";
  const domainHealth = [
    {
      domain_id: "codebase",
      label: "Codebase Signals",
      status: scan.detected.languages.length > 0 ? "healthy" : "attention",
      summary:
        scan.detected.languages.length > 0
          ? `${scan.detected.languages.length} language signal(s) detected.`
          : "No language signals detected in scanned project files.",
    },
    {
      domain_id: "delivery",
      label: "Delivery Pipeline",
      status: scan.detected.ci_surfaces.length > 0 ? "healthy" : "risk",
      summary:
        scan.detected.ci_surfaces.length > 0
          ? `CI surfaces: ${scan.detected.ci_surfaces.join(", ")}`
          : "No CI pipeline configuration detected.",
    },
    {
      domain_id: "quality",
      label: "Quality and Tests",
      status: scan.detected.test_surfaces.length > 0 ? "healthy" : "attention",
      summary:
        scan.detected.test_surfaces.length > 0
          ? `Test signals: ${scan.detected.test_surfaces.slice(0, 5).join(", ")}`
          : "No test surface hint detected.",
    },
    {
      domain_id: "governance",
      label: "Harness Governance Readiness",
      status:
        alignmentState?.summary.overall_status === "critical"
          ? "risk"
          : alignmentState?.summary.overall_status === "attention" ||
              missingChecks.length > 0
            ? "attention"
            : "healthy",
      summary:
        alignmentState?.next_recommended_action?.next_action ??
        (missingChecks.length === 0
          ? "Harness baseline checks pass for this target."
          : `${missingChecks.length} harness baseline check(s) are missing.`),
    },
  ];
  const generatedAt = new Date().toISOString();
  const baseReport = {
    version: "ProjectStatusReportV1",
    generated_at: generatedAt,
    target_repo: targetRepo,
    session_id: sessionId,
    target_mode: targetMode,
    remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
    target_path: destinationDisplayPath,
    summary: {
      overall_status: overallStatus,
      critical_count: counts.critical,
      high_count: counts.high,
      medium_count: counts.medium,
      low_count: counts.low,
      action_total: actions.length,
    },
    critical_focus: alignmentState
      ? buildAlignmentCriticalFocus(alignmentState)
      : actions
          .filter(
            (row) => row.severity === "critical" || row.severity === "high",
          )
          .slice(0, 5)
          .map((row) => row.title),
    domain_health: domainHealth,
    actions,
    project_scan: scan,
    alignment_state: alignmentState,
  };
  const historyPersisted = await persistProjectStatusHistory({
    targetRepo,
    targetKey,
    report: baseReport,
  });

  await recordBuilderAudit({
    action: "project-status",
    status: "generated",
    destinationPath: targetMode === "remote_ssh" ? targetKey : destinationPath,
    targetRepo,
    detail:
      `overall=${overallStatus}; critical=${counts.critical}; actions=${actions.length}; ` +
      `history_entries=${historyPersisted.retained_entries}; mode=${targetMode}`,
  });

  return {
    ...baseReport,
    status_history: historyPersisted,
  };
}

async function buildProjectStatusHistoryResponse(payload) {
  assertExistingProjectModeEnabled();

  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }
  const limit = parseBoundedInteger(payload?.limit, 20, { min: 1, max: 200 });
  const targetMode = normalizeTargetMode(
    payload?.target_mode,
    payload?.remote_target,
  );
  const remoteTarget =
    targetMode === "remote_ssh"
      ? normalizeRemoteTarget(payload?.remote_target ?? {})
      : null;
  const targetKey =
    targetMode === "remote_ssh"
      ? buildRemoteDestinationDescriptor(
          remoteTarget,
          buildRemoteRepoPath(remoteTarget, targetRepo),
        )
      : await resolveDestinationPath(targetRepo);
  const targetSlug = buildProjectStatusHistorySlug(targetKey);
  const targetHistoryRoot = path.join(projectStatusHistoryRoot, targetSlug);
  const exists = await pathExists(targetHistoryRoot);
  if (!exists) {
    return {
      version: "ProjectStatusHistoryResponseV1",
      generated_at: new Date().toISOString(),
      target_repo: targetRepo,
      target_mode: targetMode,
      remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
      target_slug: targetSlug,
      retention_max_entries: projectStatusHistoryMaxEntries,
      total_entries: 0,
      entries: [],
    };
  }

  const fileNames = (await fs.readdir(targetHistoryRoot))
    .filter((entry) => /^status_.*\.json$/i.test(entry))
    .sort((a, b) => b.localeCompare(a));

  const entries = [];
  const selected = fileNames.slice(0, limit);
  for (const fileName of selected) {
    const absolutePath = path.join(targetHistoryRoot, fileName);
    try {
      const raw = await fs.readFile(absolutePath, "utf8");
      const parsed = JSON.parse(raw);
      if (!isRecord(parsed) || !isRecord(parsed.summary)) {
        continue;
      }
      const overallStatus = normalizeProjectStatusOverall(
        parsed.summary.overall_status,
      );
      entries.push({
        history_id: fileName.replace(/\.json$/i, ""),
        generated_at: String(parsed.generated_at ?? ""),
        overall_status: overallStatus,
        critical_count: Number(parsed.summary.critical_count ?? 0),
        high_count: Number(parsed.summary.high_count ?? 0),
        medium_count: Number(parsed.summary.medium_count ?? 0),
        low_count: Number(parsed.summary.low_count ?? 0),
        action_total: Number(parsed.summary.action_total ?? 0),
        storage_path: disclosePath(absolutePath),
        trend: {
          critical_delta: 0,
          high_delta: 0,
        },
      });
    } catch {
      // Ignore malformed history entries and keep endpoint resilient.
    }
  }

  for (let index = 0; index < entries.length; index += 1) {
    const current = entries[index];
    const previous = entries[index + 1];
    if (!previous) {
      continue;
    }
    current.trend = {
      critical_delta: current.critical_count - previous.critical_count,
      high_delta: current.high_count - previous.high_count,
    };
  }

  return {
    version: "ProjectStatusHistoryResponseV1",
    generated_at: new Date().toISOString(),
    target_repo: targetRepo,
    target_mode: targetMode,
    remote_target: remoteTarget ? summarizeRemoteTarget(remoteTarget) : null,
    target_slug: targetSlug,
    retention_max_entries: projectStatusHistoryMaxEntries,
    total_entries: fileNames.length,
    entries,
  };
}

function buildProjectBaselineScanFromFiles({
  targetRepo,
  targetPath,
  effectiveScanLimits,
  files,
  fileScan,
}) {
  const fileSet = new Set(files);

  const languages = new Set();
  const packageManagers = new Set();
  const lockfiles = new Set();
  const ciSurfaces = new Set();
  const testSurfaces = new Set();
  const deploymentSurfaces = new Set();
  const infraSurfaces = new Set();
  const governanceSurfaces = new Set();

  const languagePatterns = [
    [/\.tsx?$/i, "typescript"],
    [/\.jsx?$/i, "javascript"],
    [/\.py$/i, "python"],
    [/\.go$/i, "go"],
    [/\.rs$/i, "rust"],
    [/\.java$/i, "java"],
    [/\.kt$/i, "kotlin"],
    [/\.rb$/i, "ruby"],
    [/\.php$/i, "php"],
  ];
  for (const relativePath of files) {
    for (const [pattern, label] of languagePatterns) {
      if (pattern.test(relativePath)) {
        languages.add(label);
      }
    }
    if (
      /(^|\/)(test|tests|__tests__)(\/|$)/i.test(relativePath) ||
      /\.test\./i.test(relativePath) ||
      /\.spec\./i.test(relativePath)
    ) {
      testSurfaces.add(relativePath);
    }
  }

  const knownLockfiles = [
    ["package-lock.json", "npm"],
    ["pnpm-lock.yaml", "pnpm"],
    ["yarn.lock", "yarn"],
    ["bun.lockb", "bun"],
    ["poetry.lock", "poetry"],
    ["uv.lock", "uv"],
    ["Pipfile.lock", "pipenv"],
    ["go.sum", "go-mod"],
    ["Cargo.lock", "cargo"],
  ];
  for (const [filename, manager] of knownLockfiles) {
    if (fileSet.has(filename)) {
      lockfiles.add(filename);
      packageManagers.add(manager);
    }
  }
  if (fileSet.has("package.json")) {
    packageManagers.add("node");
  }
  if (fileSet.has("pyproject.toml") || fileSet.has("requirements.txt")) {
    packageManagers.add("python");
  }
  if (fileSet.has("go.mod")) {
    packageManagers.add("go");
  }
  if (fileSet.has("Cargo.toml")) {
    packageManagers.add("rust");
  }

  for (const relativePath of files) {
    if (
      relativePath.startsWith(".github/workflows/") &&
      /\.(ya?ml)$/i.test(relativePath)
    ) {
      ciSurfaces.add("github_actions");
    }
    if (relativePath === ".gitlab-ci.yml") {
      ciSurfaces.add("gitlab_ci");
    }
    if (relativePath === "Jenkinsfile") {
      ciSurfaces.add("jenkins");
    }
    if (relativePath === "azure-pipelines.yml") {
      ciSurfaces.add("azure_pipelines");
    }
    if (relativePath === ".circleci/config.yml") {
      ciSurfaces.add("circleci");
    }

    if (
      relativePath === "Dockerfile" ||
      relativePath.startsWith("docker/") ||
      relativePath.includes("docker-compose") ||
      relativePath.startsWith("k8s/") ||
      relativePath.startsWith("helm/") ||
      relativePath.endsWith("chart.yaml")
    ) {
      deploymentSurfaces.add(relativePath);
    }

    if (
      relativePath.endsWith(".tf") ||
      relativePath === "Pulumi.yaml" ||
      relativePath.startsWith("terraform/") ||
      relativePath.startsWith("ansible/") ||
      relativePath.startsWith(".infra/")
    ) {
      infraSurfaces.add(relativePath);
    }
  }

  const governanceCandidates = [
    "README.md",
    "AGENTS.md",
    "docs/00_overview/engineer_entrypoint.md",
    "docs/11_ops/tooling_pipeline.md",
    "docs/15_checklists/agent_cycle_gate.md",
  ];
  for (const candidate of governanceCandidates) {
    if (fileSet.has(candidate)) {
      governanceSurfaces.add(candidate);
    }
  }

  const criticalGaps = [];
  if (ciSurfaces.size === 0) {
    criticalGaps.push(
      "No CI pipeline definition detected. Add a CI surface before execution-heavy integration work.",
    );
  }
  if (testSurfaces.size === 0) {
    criticalGaps.push(
      "No test surface detected. Add baseline tests before enabling aggressive implementation loops.",
    );
  }
  if (!fileSet.has("README.md")) {
    criticalGaps.push(
      "Missing README.md. Add baseline project orientation for maintainers and reviewers.",
    );
  }
  if (governanceSurfaces.size === 0) {
    criticalGaps.push(
      "No governance docs detected. Add policy/ops/checklist references for safe harness integration.",
    );
  }

  return {
    version: "ProjectBaselineScanV1",
    scanned_at: new Date().toISOString(),
    target_repo: targetRepo,
    target_path: targetPath,
    file_count: files.length,
    scan_limits_effective: effectiveScanLimits,
    scan_truncated: fileScan.scan_truncated,
    scan_truncation_reason: fileScan.scan_truncation_reason,
    detected: {
      languages: [...languages].sort((a, b) => a.localeCompare(b)),
      package_managers: [...packageManagers].sort((a, b) => a.localeCompare(b)),
      lockfiles: [...lockfiles].sort((a, b) => a.localeCompare(b)),
      ci_surfaces: [...ciSurfaces].sort((a, b) => a.localeCompare(b)),
      test_surfaces: [...testSurfaces]
        .slice(0, 20)
        .sort((a, b) => a.localeCompare(b)),
      deployment_surfaces: [...deploymentSurfaces]
        .slice(0, 20)
        .sort((a, b) => a.localeCompare(b)),
      infra_surfaces: [...infraSurfaces]
        .slice(0, 20)
        .sort((a, b) => a.localeCompare(b)),
      governance_surfaces: [...governanceSurfaces].sort((a, b) =>
        a.localeCompare(b),
      ),
    },
    critical_gaps: criticalGaps,
    summary: {
      language_count: languages.size,
      package_manager_count: packageManagers.size,
      ci_surface_count: ciSurfaces.size,
      test_surface_count: testSurfaces.size,
      critical_gap_count: criticalGaps.length,
    },
  };
}

async function runProjectBaselineScan({
  targetRepo,
  destinationPath,
  scanLimits,
}) {
  const effectiveScanLimits = normalizeScanLimits(scanLimits);
  const fileScan = await listProjectFiles(destinationPath, {
    maxDepth: effectiveScanLimits.max_depth,
    maxFiles: effectiveScanLimits.max_files,
  });
  return buildProjectBaselineScanFromFiles({
    targetRepo,
    targetPath: disclosePath(destinationPath),
    effectiveScanLimits,
    files: fileScan.files,
    fileScan,
  });
}

function resolveArtifactAbsolutePath(artifactPath) {
  const value = String(artifactPath ?? "").trim();
  if (!value) {
    return "";
  }
  if (path.isAbsolute(value)) {
    return value;
  }
  if (value.startsWith(`${CONTROL_ARTIFACT_RELATIVE_ROOT}/`)) {
    return path.join(
      controlRoot,
      value.slice(`${CONTROL_ARTIFACT_RELATIVE_ROOT}/`.length),
    );
  }
  return path.join(repoRoot, value);
}

async function buildAlignmentSourceBreakdown(session) {
  const breakdown = {
    seed_template: 0,
    profile_overlay: 0,
    user_filled: 0,
    scan_derived: 0,
    manual_required: 0,
  };
  const templateFillMapPath = resolveArtifactAbsolutePath(
    session?.artifacts?.template_fill_map_json,
  );
  if (!templateFillMapPath) {
    return breakdown;
  }
  const payload = await safeReadJson(templateFillMapPath, null);
  if (!isRecord(payload) || !Array.isArray(payload.rows)) {
    return breakdown;
  }

  for (const row of payload.rows) {
    const sourceKind = String(row?.source_kind ?? "").trim();
    if (
      sourceKind === "seed_template" ||
      sourceKind === "profile_overlay" ||
      sourceKind === "user_filled" ||
      sourceKind === "scan_derived"
    ) {
      breakdown[sourceKind] += 1;
    }
  }
  return breakdown;
}

async function loadDiscoveryPhasePlanArtifact(session) {
  const phasePlanPath = resolveArtifactAbsolutePath(
    session?.artifacts?.phase_plan_json,
  );
  if (!phasePlanPath) {
    return null;
  }
  const payload = await safeReadJson(phasePlanPath, null);
  return isRecord(payload) ? payload : null;
}

function buildAlignmentSummary(items) {
  const openItems = items.filter((item) => item.status !== "satisfied");
  const summary = {
    satisfied_count: items.filter((item) => item.status === "satisfied").length,
    manual_required_count: items.filter(
      (item) => item.status === "manual_required",
    ).length,
    missing_count: items.filter((item) => item.status === "missing").length,
    deferred_count: items.filter((item) => item.status === "deferred").length,
    critical_count: openItems.filter((item) => item.severity === "critical")
      .length,
    high_count: openItems.filter((item) => item.severity === "high").length,
    medium_count: openItems.filter((item) => item.severity === "medium").length,
    low_count: openItems.filter((item) => item.severity === "low").length,
    overall_status: "ready",
  };
  summary.overall_status =
    summary.critical_count > 0
      ? "critical"
      : summary.high_count > 0 ||
          summary.medium_count > 0 ||
          summary.manual_required_count > 0 ||
          summary.missing_count > 0
        ? "attention"
        : "ready";
  return summary;
}

function buildAlignmentNextRecommendedAction(items) {
  const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
  const statusRank = { manual_required: 0, missing: 1, deferred: 2, satisfied: 3 };
  const candidates = items
    .filter((item) => item.status !== "satisfied")
    .sort((left, right) => {
      if (severityRank[left.severity] !== severityRank[right.severity]) {
        return severityRank[left.severity] - severityRank[right.severity];
      }
      if (statusRank[left.status] !== statusRank[right.status]) {
        return statusRank[left.status] - statusRank[right.status];
      }
      return left.label.localeCompare(right.label);
    });
  const nextItem = candidates[0];
  if (!nextItem) {
    return null;
  }
  return {
    item_id: nextItem.item_id,
    label: nextItem.label,
    route: nextItem.recommended_route,
    next_action: nextItem.next_action,
  };
}

function buildProjectStatusActionsFromAlignment(alignmentState) {
  return alignmentState.items
    .filter((item) => item.status !== "satisfied")
    .map((item) => ({
      action_id: `alignment-${item.item_id}`,
      severity: item.severity,
      title: item.label,
      description: item.next_action,
      route: item.recommended_route,
      depends_on: [],
      source: `alignment_state.${item.item_id}`,
    }));
}

function buildAlignmentCriticalFocus(alignmentState) {
  return alignmentState.items
    .filter(
      (item) =>
        item.status !== "satisfied" &&
        (item.severity === "critical" || item.severity === "high"),
    )
    .slice(0, 5)
    .map((item) => item.label);
}

async function buildAlignmentState({
  session,
  targetRepo,
  workflowType,
  selectedProfile,
  phasePlan,
  targetMode = "local",
  targetPath = "",
  reviewQueue = null,
  repoCompletenessGroups = [],
}) {
  const items = [];
  const lockedProjectGoal =
    String(session?.synthesis?.product_spec?.intent ?? "").trim() ||
    String(session?.intake?.project_goal ?? "").trim() ||
    String(session?.intake?.project_prompt ?? "").trim() ||
    targetRepo;
  const approvalApproved = Boolean(session?.approval?.approved);
  const projectScanSummary = isRecord(session?.project_scan_summary)
    ? session.project_scan_summary
    : null;
  const scanCriticalGaps = normalizeStringArray(
    projectScanSummary?.critical_gaps,
  );
  const alignmentPhasePlan = phasePlan ?? {
    next_recommended_phase_id: "phase_1",
  };
  const sourceBreakdown = await buildAlignmentSourceBreakdown(session);

  items.push({
    item_id: "project_goal_locked",
    label: "Lock project goal and scope boundary",
    status: lockedProjectGoal ? "satisfied" : "missing",
    severity: "critical",
    source_type: "user_filled",
    owner: "operator",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(session?.artifacts?.product_spec ?? "").trim(),
      String(session?.artifacts?.synthesis_markdown ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Confirm the approved project goal and keep the execution boundary explicit before implementation continues.",
  });
  items.push({
    item_id: "approval_gate",
    label: "Resolve discovery approval gate",
    status: approvalApproved ? "satisfied" : "manual_required",
    severity: "critical",
    source_type: "manual_required",
    owner: "operator",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(session?.approval?.approval_artifact_path ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Mark the approval artifact before generation, deploy continuation, or assistant-backed alignment review.",
  });
  items.push({
    item_id: "project_scan_context",
    label: "Review scan-derived repo context",
    status: projectScanSummary
      ? scanCriticalGaps.length > 0
        ? "manual_required"
        : "satisfied"
      : "missing",
    severity: scanCriticalGaps.length > 0 ? "high" : "medium",
    source_type: "scan_derived",
    owner: "operator",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(session?.project_scan_artifact_paths?.markdown ?? "").trim(),
      String(session?.project_scan_artifact_paths?.json ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Use the scan summary to keep language, CI, deployment, and governance surfaces aligned before phase work begins.",
  });

  scanCriticalGaps.forEach((gap, index) => {
    items.push({
      item_id: `critical_gap_${String(index + 1).padStart(2, "0")}`,
      label: `Resolve critical scan gap ${index + 1}`,
      status: "manual_required",
      severity: "high",
      source_type: "manual_required",
      owner: "operator",
      recommended_route: "/deploy/builder",
      evidence_paths: [
        String(session?.project_scan_artifact_paths?.markdown ?? "").trim(),
      ].filter(Boolean),
      next_action: gap,
    });
  });

  items.push({
    item_id: "template_fill_provenance",
    label: "Confirm template-fill provenance",
    status: session?.artifacts?.template_fill_map_markdown
      ? "satisfied"
      : "missing",
    severity: "high",
    source_type: "seed_template",
    owner: "harness",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(session?.artifacts?.template_fill_map_json ?? "").trim(),
      String(session?.artifacts?.template_fill_map_markdown ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Review what came from the seed template, profile overlay, user-filled discovery, and scan-derived context before moving forward.",
  });

  items.push({
    item_id:
      workflowType === "existing_project"
        ? "sidecar_deployed"
        : "seed_repo_generated",
    label:
      workflowType === "existing_project"
        ? "Confirm guarded sidecar deployment"
        : "Confirm generated harness seed output",
    status:
      workflowType === "existing_project"
        ? session?.artifacts?.deployed_sidecar_path
          ? "satisfied"
          : "missing"
        : session?.artifacts?.generated_repo_path
          ? "satisfied"
          : "missing",
    severity: "high",
    source_type: "seed_template",
    owner: "harness",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(
        workflowType === "existing_project"
          ? session?.artifacts?.deployed_sidecar_path ?? ""
          : session?.artifacts?.generated_repo_path ?? "",
      ).trim(),
      String(session?.artifacts?.generated_project_spec ?? "").trim(),
    ].filter(Boolean),
    next_action:
      workflowType === "existing_project"
        ? "Verify the harness is deployed only inside `.moradins-harness` and not across the target repo."
        : "Inspect the generated seed repo and confirm it reflects the approved goal and scan-derived context.",
  });

  items.push({
    item_id: "phase_plan_ready",
    label: "Generate the follow-on phase plan",
    status: session?.artifacts?.phase_plan_json ? "satisfied" : "missing",
    severity: "medium",
    source_type: "user_filled",
    owner: "harness",
    recommended_route: "/deploy/builder",
    evidence_paths: [
      String(session?.artifacts?.phase_plan_json ?? "").trim(),
      String(session?.artifacts?.phase_plan_markdown ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Write the typed phase plan so next execution work stays bounded, legible, and reviewable.",
  });
  items.push({
    item_id: "execution_prompts_ready",
    label: "Generate execution prompts and operator handoff",
    status: session?.artifacts?.execution_prompts_json
      ? "satisfied"
      : "missing",
    severity: "medium",
    source_type: "user_filled",
    owner: "assistant",
    recommended_route: "/deploy/status",
    evidence_paths: [
      String(session?.artifacts?.execution_prompts_json ?? "").trim(),
      String(session?.artifacts?.execution_prompts_markdown ?? "").trim(),
      String(session?.artifacts?.bootstrap_prompt_markdown ?? "").trim(),
    ].filter(Boolean),
    next_action:
      "Use the generated prompts and alignment artifact as the reviewed handoff for the next operator or assistant step.",
  });

  for (const group of repoCompletenessGroups) {
    for (const check of group?.checks ?? []) {
      if (check.status !== "missing") {
        continue;
      }
      items.push({
        item_id: `repo_gap_${group.group_id}_${check.check_id}`,
        label: `Fill missing ${group.label} surface`,
        status: "manual_required",
        severity:
          group.group_id === "foundations" || group.group_id === "governance"
            ? "high"
            : "medium",
        source_type: "manual_required",
        owner: "operator",
        recommended_route: "/deploy/status",
        evidence_paths: [
          String(check.path ?? "").trim(),
          targetPath,
        ].filter(Boolean),
        next_action: check.label,
      });
    }
  }

  if (reviewQueue?.pending_approvals > 0) {
    items.push({
      item_id: "review_queue_pending_approvals",
      label: "Resolve pending human approvals",
      status: "manual_required",
      severity: "critical",
      source_type: "manual_required",
      owner: "operator",
      recommended_route: "/reviews/queue",
      evidence_paths: [],
      next_action: `${reviewQueue.pending_approvals} approval item(s) remain open before execution should continue.`,
    });
  }

  const summary = buildAlignmentSummary(items);
  const nextRecommendedAction = buildAlignmentNextRecommendedAction(items);

  return {
    version: "AlignmentStateV1",
    generated_at: new Date().toISOString(),
    session_id: session.session_id,
    target_repo: targetRepo,
    workflow_type: workflowType,
    selected_profile: selectedProfile || "unselected",
    target_mode: targetMode,
    target_path: targetPath || undefined,
    locked_project_goal: lockedProjectGoal,
    approval_state: approvalApproved ? "approved" : "pending",
    next_recommended_phase_id:
      alignmentPhasePlan.next_recommended_phase_id ?? "phase_1",
    source_breakdown: sourceBreakdown,
    summary,
    next_recommended_action: nextRecommendedAction,
    items,
  };
}

function formatAlignmentStateMarkdown(alignmentState) {
  const sourceBreakdownLines = Object.entries(
    alignmentState.source_breakdown ?? {},
  ).map(([key, value]) => `- ${key}: ${value}`);
  return [
    "# Alignment State",
    "",
    `- session_id: \`${alignmentState.session_id}\``,
    `- target_repo: \`${alignmentState.target_repo}\``,
    `- workflow_type: \`${alignmentState.workflow_type}\``,
    `- selected_profile: \`${alignmentState.selected_profile || "unselected"}\``,
    `- approval_state: \`${alignmentState.approval_state}\``,
    `- next_recommended_phase_id: \`${alignmentState.next_recommended_phase_id}\``,
    ...(alignmentState.target_mode
      ? [`- target_mode: \`${alignmentState.target_mode}\``]
      : []),
    ...(alignmentState.target_path
      ? [`- target_path: \`${alignmentState.target_path}\``]
      : []),
    "",
    "## Locked Goal",
    "",
    alignmentState.locked_project_goal,
    "",
    "## Summary",
    "",
    `- overall_status: \`${alignmentState.summary.overall_status}\``,
    `- satisfied_count: ${alignmentState.summary.satisfied_count}`,
    `- manual_required_count: ${alignmentState.summary.manual_required_count}`,
    `- missing_count: ${alignmentState.summary.missing_count}`,
    `- deferred_count: ${alignmentState.summary.deferred_count}`,
    "",
    "## Source Breakdown",
    "",
    ...(sourceBreakdownLines.length > 0 ? sourceBreakdownLines : ["- none"]),
    "",
    "## Next Recommended Action",
    "",
    ...(alignmentState.next_recommended_action
      ? [
          `- item_id: \`${alignmentState.next_recommended_action.item_id}\``,
          `- label: ${alignmentState.next_recommended_action.label}`,
          `- route: \`${alignmentState.next_recommended_action.route}\``,
          `- next_action: ${alignmentState.next_recommended_action.next_action}`,
        ]
      : ["- none"]),
    "",
    "## Items",
    "",
    ...alignmentState.items.flatMap((item) => [
      `### ${item.label}`,
      "",
      `- item_id: \`${item.item_id}\``,
      `- status: \`${item.status}\``,
      `- severity: \`${item.severity}\``,
      `- source_type: \`${item.source_type}\``,
      `- owner: \`${item.owner}\``,
      `- recommended_route: \`${item.recommended_route}\``,
      `- next_action: ${item.next_action}`,
      "",
      "#### Evidence Paths",
      "",
      ...(item.evidence_paths.length > 0
        ? item.evidence_paths.map((evidencePath) => `- ${evidencePath}`)
        : ["- none"]),
      "",
    ]),
  ].join("\n");
}

async function writeAlignmentStateArtifacts({ session, alignmentState }) {
  const sessionRoot = `Harness/artifacts/control/discovery_sessions/${session.session_id}`;
  const artifactPaths = {
    alignment_state_json: `${sessionRoot}/alignment_state.json`,
    alignment_state_markdown: `${sessionRoot}/alignment_state.md`,
  };
  await writeDiscoveryFile(
    session.session_id,
    "alignment_state.json",
    JSON.stringify(alignmentState, null, 2),
  );
  await writeDiscoveryFile(
    session.session_id,
    "alignment_state.md",
    formatAlignmentStateMarkdown(alignmentState),
  );
  session.artifacts = {
    ...session.artifacts,
    alignment_state_json: artifactPaths.alignment_state_json,
    alignment_state_markdown: artifactPaths.alignment_state_markdown,
  };
  await saveDiscoverySession(session);
  return artifactPaths;
}

function normalizeTargetMode(rawTargetMode, remoteTarget) {
  if (remoteTarget) {
    return "remote_ssh";
  }
  return String(rawTargetMode ?? "local")
    .trim()
    .toLowerCase() === "remote_ssh"
    ? "remote_ssh"
    : "local";
}

function normalizeRemoteRepoName(targetRepo) {
  const normalized = normalizePath(
    String(targetRepo ?? "")
      .trim()
      .replace(/^\.?\/*/, ""),
  );
  if (!normalized || normalized.startsWith("/") || normalized.includes("..")) {
    throw new ApiError(
      400,
      "invalid_remote_target_repo",
      "target_repo must be a relative path under the remote allowlisted root.",
    );
  }
  return normalized;
}

function buildRemoteRepoPath(target, targetRepo) {
  const normalizedRepo = normalizeRemoteRepoName(targetRepo);
  return path.posix.join(target.allowlisted_root, normalizedRepo);
}

async function runRemoteShellText(
  target,
  remoteCommand,
  { input, timeout = 20_000, maxBuffer = 5 * 1024 * 1024 } = {},
) {
  if (!commandExists("ssh")) {
    throw new ApiError(
      500,
      "ssh_binary_missing",
      "ssh command is not available on this host.",
    );
  }
  const args = buildSshArgs(target, remoteCommand);
  try {
    const output = execFileSync("ssh", args, {
      encoding: "utf8",
      env: process.env,
      input,
      stdio: ["pipe", "pipe", "pipe"],
      timeout,
      maxBuffer,
    });
    return String(output ?? "");
  } catch (error) {
    const detail = String(
      error?.stderr ?? error?.stdout ?? error?.message ?? "",
    ).trim();
    throw new ApiError(
      400,
      "remote_ssh_command_failed",
      detail || "remote ssh command failed",
    );
  }
}

async function assertRemoteRepoDirectory(target, remoteRepoPath) {
  await runRemoteShellText(
    target,
    `cd ${sanitizeRemoteShellValue(remoteRepoPath)} && pwd`,
    {
      timeout: 12_000,
      maxBuffer: 1024 * 1024,
    },
  );
}

async function prepareRemoteDestination({
  target,
  remotePath,
  overwrite,
  confirmation,
}) {
  const probeOutput = (
    await runRemoteShellText(
      target,
      [
        `if [ ! -e ${sanitizeRemoteShellValue(remotePath)} ]; then`,
        "printf 'missing';",
        `elif [ -d ${sanitizeRemoteShellValue(remotePath)} ] && [ -z "$(find ${sanitizeRemoteShellValue(remotePath)} -mindepth 1 -maxdepth 1 -print -quit)" ]; then`,
        "printf 'empty';",
        `elif [ -d ${sanitizeRemoteShellValue(remotePath)} ]; then`,
        "printf 'present';",
        "else",
        "printf 'file';",
        "fi",
      ].join(" "),
      { timeout: 12_000, maxBuffer: 1024 * 1024 },
    )
  )
    .trim()
    .toLowerCase();

  if (probeOutput === "missing" || probeOutput === "empty") {
    await runRemoteShellText(
      target,
      `mkdir -p ${sanitizeRemoteShellValue(remotePath)}`,
      {
        timeout: 12_000,
        maxBuffer: 1024 * 1024,
      },
    );
    return { canProceed: true, overwrote: false, conflict: null };
  }

  const expectedConfirmation = buildOverwriteConfirmation(remotePath);
  if (!overwrite) {
    return {
      canProceed: false,
      overwrote: false,
      conflict: {
        destination_path: discloseText(remotePath),
        expected_confirmation: expectedConfirmation,
      },
    };
  }

  if (String(confirmation ?? "").trim() !== expectedConfirmation) {
    throw new ApiError(
      400,
      "invalid_overwrite_confirmation",
      "overwrite_confirmation is required and did not match expected value.",
      {
        expected_confirmation: expectedConfirmation,
        destination_path: discloseText(remotePath),
      },
    );
  }

  await runRemoteShellText(
    target,
    `rm -rf -- ${sanitizeRemoteShellValue(remotePath)} && mkdir -p ${sanitizeRemoteShellValue(remotePath)}`,
    {
      timeout: 20_000,
      maxBuffer: 1024 * 1024,
    },
  );
  return { canProceed: true, overwrote: true, conflict: null };
}

async function streamDirectoryToRemote({ sourceDir, target, remotePath }) {
  if (!commandExists("tar")) {
    throw new ApiError(
      500,
      "tar_binary_missing",
      "tar command is not available on this host.",
    );
  }
  if (!commandExists("ssh")) {
    throw new ApiError(
      500,
      "ssh_binary_missing",
      "ssh command is not available on this host.",
    );
  }

  await runRemoteShellText(
    target,
    `mkdir -p ${sanitizeRemoteShellValue(remotePath)}`,
    {
      timeout: 12_000,
      maxBuffer: 1024 * 1024,
    },
  );

  await new Promise((resolve, reject) => {
    const tarChild = spawn("tar", ["-C", sourceDir, "-cf", "-", "."], {
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const sshChild = spawn(
      "ssh",
      buildSshArgs(
        target,
        `tar -xf - -C ${sanitizeRemoteShellValue(remotePath)}`,
      ),
      {
        env: process.env,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );

    let tarStderr = "";
    let sshStdout = "";
    let sshStderr = "";
    let tarExited = false;
    let sshExited = false;
    let tarCode = 0;
    let sshCode = 0;
    let finished = false;

    function finalize() {
      if (finished || !tarExited || !sshExited) {
        return;
      }
      finished = true;
      if (tarCode !== 0) {
        reject(
          new ApiError(
            500,
            "remote_tar_stream_failed",
            tarStderr.trim() ||
              "failed to archive local sidecar for remote deploy",
          ),
        );
        return;
      }
      if (sshCode !== 0) {
        reject(
          new ApiError(
            400,
            "remote_ssh_command_failed",
            sshStderr.trim() ||
              sshStdout.trim() ||
              "remote sidecar upload failed",
          ),
        );
        return;
      }
      resolve();
    }

    tarChild.stdout.pipe(sshChild.stdin);
    tarChild.stdout.on("error", () => {
      sshChild.stdin.destroy();
    });
    tarChild.stderr.on("data", (chunk) => {
      tarStderr += chunk.toString();
    });
    sshChild.stdout.on("data", (chunk) => {
      sshStdout += chunk.toString();
    });
    sshChild.stderr.on("data", (chunk) => {
      sshStderr += chunk.toString();
    });

    tarChild.on("error", (error) => {
      if (finished) {
        return;
      }
      finished = true;
      reject(
        new ApiError(
          500,
          "remote_tar_spawn_failed",
          String(error?.message ?? error),
        ),
      );
    });
    sshChild.on("error", (error) => {
      if (finished) {
        return;
      }
      finished = true;
      reject(
        new ApiError(
          500,
          "remote_ssh_spawn_failed",
          String(error?.message ?? error),
        ),
      );
    });
    tarChild.on("close", (code) => {
      tarCode = Number(code ?? 1);
      tarExited = true;
      finalize();
    });
    sshChild.on("close", (code) => {
      sshCode = Number(code ?? 1);
      sshExited = true;
      finalize();
    });
  });
}

async function runRemoteProjectBaselineScan({
  targetRepo,
  remoteTarget,
  scanLimits,
}) {
  const effectiveScanLimits = normalizeScanLimits(scanLimits);
  const remoteRepoPath = buildRemoteRepoPath(remoteTarget, targetRepo);
  await assertRemoteRepoDirectory(remoteTarget, remoteRepoPath);
  const maxDepth = effectiveScanLimits.max_depth + 1;
  const maxFiles = effectiveScanLimits.max_files;
  const remoteCommand =
    `cd ${sanitizeRemoteShellValue(remoteRepoPath)} && ` +
    `find . -maxdepth ${maxDepth} \\( -path './.git' -o -path './node_modules' -o -path './dist' -o -path './build' -o -path './.venv' -o -path './.cache' \\) -prune -o -type f -print | ` +
    "sed 's#^\\./##' | " +
    "sort | " +
    `head -n ${maxFiles}`;
  const stdout = (await runRemoteShellText(remoteTarget, remoteCommand)).trim();
  const files = stdout
    .split(/\r?\n/)
    .map((value) => normalizePath(value.trim()))
    .filter(Boolean);
  return buildProjectBaselineScanFromFiles({
    targetRepo,
    targetPath: discloseText(remoteRepoPath),
    effectiveScanLimits,
    files,
    fileScan: {
      files,
      scan_truncated: files.length >= maxFiles,
      scan_truncation_reason:
        files.length >= maxFiles
          ? `Reached remote max_files limit (${maxFiles}).`
          : "",
    },
  });
}

async function writeProjectScanArtifacts(sessionId, scan) {
  const jsonRelativePath = `${DISCOVERY_SESSIONS_RELATIVE_ROOT}/${sessionId}/project_scan.json`;
  const markdownRelativePath = `${DISCOVERY_SESSIONS_RELATIVE_ROOT}/${sessionId}/project_scan.md`;
  await writeDiscoveryFile(
    sessionId,
    "project_scan.json",
    JSON.stringify(scan, null, 2),
  );

  const markdown = [
    "# Project Baseline Scan",
    "",
    `- scanned_at: \`${scan.scanned_at}\``,
    `- target_repo: \`${scan.target_repo}\``,
    `- file_count: \`${scan.file_count}\``,
    `- max_depth: \`${scan.scan_limits_effective?.max_depth ?? scanMaxDepthDefault}\``,
    `- max_files: \`${scan.scan_limits_effective?.max_files ?? scanMaxFilesDefault}\``,
    `- scan_truncated: \`${scan.scan_truncated ? "true" : "false"}\``,
    ...(scan.scan_truncation_reason
      ? [`- scan_truncation_reason: ${scan.scan_truncation_reason}`]
      : []),
    "",
    "## Summary",
    "",
    `- language_count: ${scan.summary.language_count}`,
    `- package_manager_count: ${scan.summary.package_manager_count}`,
    `- ci_surface_count: ${scan.summary.ci_surface_count}`,
    `- test_surface_count: ${scan.summary.test_surface_count}`,
    `- critical_gap_count: ${scan.summary.critical_gap_count}`,
    "",
    "## Critical Gaps",
    "",
    ...(scan.critical_gaps.length > 0
      ? scan.critical_gaps.map((row) => `- ${row}`)
      : ["- none"]),
    "",
    "## Detected Languages",
    "",
    ...(scan.detected.languages.length > 0
      ? scan.detected.languages.map((row) => `- ${row}`)
      : ["- none"]),
    "",
    "## CI Surfaces",
    "",
    ...(scan.detected.ci_surfaces.length > 0
      ? scan.detected.ci_surfaces.map((row) => `- ${row}`)
      : ["- none"]),
    "",
  ].join("\n");
  await writeDiscoveryFile(sessionId, "project_scan.md", markdown);

  return {
    json: jsonRelativePath,
    markdown: markdownRelativePath,
  };
}

async function listProjectFiles(rootPath, { maxDepth, maxFiles }) {
  const skipDirs = new Set([
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    ".cache",
  ]);
  const discovered = [];
  const truncationReasons = new Set();

  async function walk(currentPath, depth, prefix) {
    if (depth > maxDepth) {
      truncationReasons.add(`Reached max_depth limit (${maxDepth}).`);
      return;
    }
    if (discovered.length >= maxFiles) {
      truncationReasons.add(`Reached max_files limit (${maxFiles}).`);
      return;
    }
    const entries = await fs.readdir(currentPath, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      if (discovered.length >= maxFiles) {
        truncationReasons.add(`Reached max_files limit (${maxFiles}).`);
        return;
      }
      const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
      const absolutePath = path.join(currentPath, entry.name);
      if (entry.isSymbolicLink()) {
        continue;
      }
      if (entry.isDirectory()) {
        if (skipDirs.has(entry.name)) {
          continue;
        }
        await walk(absolutePath, depth + 1, relativePath);
        continue;
      }
      if (entry.isFile()) {
        discovered.push(normalizePath(relativePath));
      }
    }
  }

  await walk(rootPath, 0, "");
  return {
    files: discovered,
    scan_truncated: truncationReasons.size > 0,
    scan_truncation_reason: [...truncationReasons].join(" "),
  };
}

function parseBoundedInteger(rawValue, fallback, { min, max }) {
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric) || !Number.isInteger(numeric)) {
    return fallback;
  }
  if (numeric < min) {
    return min;
  }
  if (numeric > max) {
    return max;
  }
  return numeric;
}

function normalizeProjectStatusOverall(rawValue) {
  const normalized = String(rawValue ?? "")
    .trim()
    .toLowerCase();
  if (normalized === "critical" || normalized === "ready") {
    return normalized;
  }
  return "attention";
}

function normalizeScanLimits(rawLimits) {
  const source = isRecord(rawLimits) ? rawLimits : {};
  return {
    max_depth: parseBoundedInteger(source.max_depth, scanMaxDepthDefault, {
      min: 1,
      max: 16,
    }),
    max_files: parseBoundedInteger(source.max_files, scanMaxFilesDefault, {
      min: 100,
      max: 50000,
    }),
  };
}

function buildCriticalGapOverrideConfirmation(targetRepo) {
  const normalized = String(targetRepo ?? "")
    .trim()
    .replaceAll("\\", "/")
    .replace(/\/+$/g, "");
  const parts = normalized.split("/").filter(Boolean);
  const targetName = parts[parts.length - 1] ?? "target";
  return `override-critical-gaps:${targetName}`;
}

function summarizeRemoteTarget(target) {
  return {
    target_id: String(target?.target_id ?? "").trim(),
    connection_mode: "ssh",
    host: String(target?.host ?? "").trim(),
    user: String(target?.user ?? "").trim(),
    port: Number(target?.port ?? 22),
    profile_label: String(target?.profile_label ?? "").trim(),
    auth_method: String(target?.auth_method ?? "ssh_agent").trim(),
    known_hosts_mode: String(target?.known_hosts_mode ?? "strict").trim(),
    allowlisted_root: discloseText(
      String(target?.allowlisted_root ?? "").trim(),
    ),
    pem_path: target?.pem_path ? discloseText(String(target.pem_path)) : "",
  };
}

function buildRemoteDestinationDescriptor(target, remotePath) {
  return `ssh://${target.user}@${target.host}:${target.port}${remotePath}`;
}

function buildProjectStatusHistorySlug(targetKey) {
  const normalized = normalizePath(String(targetKey ?? "").trim()).replace(
    /\/+/g,
    "/",
  );
  const base =
    path
      .basename(normalized.replace(/\/+$/g, ""))
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "target";
  const hash = crypto
    .createHash("sha256")
    .update(normalized)
    .digest("hex")
    .slice(0, 8);
  return `${base}-${hash}`;
}

function formatTimestampForFilename(isoTimestamp) {
  return String(isoTimestamp ?? "")
    .trim()
    .replaceAll(":", "-")
    .replaceAll(".", "-");
}

async function persistProjectStatusHistory({ targetRepo, targetKey, report }) {
  const targetSlug = buildProjectStatusHistorySlug(targetKey);
  const targetHistoryRoot = path.join(projectStatusHistoryRoot, targetSlug);
  await fs.mkdir(targetHistoryRoot, { recursive: true });

  const stamp = formatTimestampForFilename(report.generated_at);
  const entryPath = path.join(targetHistoryRoot, `status_${stamp}.json`);
  const latestPath = path.join(targetHistoryRoot, "latest.json");
  const serialized = `${JSON.stringify(report, null, 2)}\n`;
  await fs.writeFile(entryPath, serialized, "utf8");
  await fs.writeFile(latestPath, serialized, "utf8");

  const statusFiles = (await fs.readdir(targetHistoryRoot))
    .filter((entry) => /^status_.*\.json$/i.test(entry))
    .sort((a, b) => b.localeCompare(a));
  for (const stale of statusFiles.slice(projectStatusHistoryMaxEntries)) {
    await fs.rm(path.join(targetHistoryRoot, stale), { force: true });
  }

  return {
    target_slug: targetSlug,
    entry_path: disclosePath(entryPath),
    latest_path: disclosePath(latestPath),
    retained_entries: Math.min(
      statusFiles.length,
      projectStatusHistoryMaxEntries,
    ),
    retention_max_entries: projectStatusHistoryMaxEntries,
    target_repo: targetRepo,
  };
}

function normalizeSidecarDir(rawValue) {
  const value = String(rawValue ?? "").trim();
  if (!value) {
    throw new ApiError(400, "invalid_sidecar_dir", "sidecar_dir is required.");
  }
  if (value.includes("/") || value.includes("\\") || value.includes("..")) {
    throw new ApiError(
      400,
      "invalid_sidecar_dir",
      "sidecar_dir must be a single directory name without traversal.",
    );
  }
  return value;
}

async function buildRepoCompletenessGroups(destinationPath, profile) {
  const minimalGroups = [
    {
      group_id: "goal",
      label: "Goal Coverage",
      checks: [
        {
          check_id: "goal-project-spec",
          label: "Project goal artifact exists",
          type: "glob_markdown",
          path: "docs/product_specs",
          pattern:
            /(project_spec|project_builder_ui|generated_profile_overlay)\.md$/i,
        },
      ],
    },
    {
      group_id: "integrations",
      label: "Integration Coverage",
      checks: [
        {
          check_id: "integration-tooling-runbook",
          label: "Tooling pipeline guide exists",
          type: "file",
          path: "docs/11_ops/tooling_pipeline.md",
        },
        {
          check_id: "integration-configuration-guide",
          label: "Configuration guide exists",
          type: "file",
          path: "docs/11_ops/configuration.md",
        },
      ],
    },
    {
      group_id: "tools",
      label: "Tooling Surface",
      checks: [
        {
          check_id: "tools-branch-hygiene",
          label: "Branch hygiene script exists",
          type: "file",
          path: "scripts/check_branch_hygiene.py",
        },
        {
          check_id: "tools-control-api",
          label: "Control API script exists",
          type: "file",
          path: "dev_tracker/ui/scripts/control-api.mjs",
        },
        {
          check_id: "tools-skills-index",
          label: "Skills index exists",
          type: "file",
          path: "skills/index.md",
        },
      ],
    },
  ];

  const harnessCoreGroups = [
    {
      group_id: "foundations",
      label: "Harness Foundations",
      checks: [
        {
          check_id: "foundation-agents",
          label: "AGENTS policy exists",
          type: "file",
          path: "AGENTS.md",
        },
        {
          check_id: "foundation-readme",
          label: "README exists",
          type: "file",
          path: "README.md",
        },
        {
          check_id: "foundation-overview",
          label: "Overview docs directory exists",
          type: "directory",
          path: "docs/00_overview",
        },
        {
          check_id: "foundation-architecture",
          label: "Architecture docs directory exists",
          type: "directory",
          path: "docs/03_architecture",
        },
      ],
    },
    {
      group_id: "governance",
      label: "Governance and Execution",
      checks: [
        {
          check_id: "governance-checklists",
          label: "Checklist docs directory exists",
          type: "directory",
          path: "docs/15_checklists",
        },
        {
          check_id: "governance-exec-plans",
          label: "Execution plans index exists",
          type: "file",
          path: "docs/exec_plans/index.md",
        },
        {
          check_id: "governance-changelog",
          label: "Control changelog exists",
          type: "file",
          path: "Harness/artifacts/control/changelog.md",
        },
      ],
    },
  ];

  const groupSpecs =
    profile === "harness_core"
      ? [...minimalGroups, ...harnessCoreGroups]
      : minimalGroups;
  const groups = [];

  for (const groupSpec of groupSpecs) {
    const checks = [];
    for (const checkSpec of groupSpec.checks) {
      checks.push(
        await evaluateRepoCompletenessCheck(destinationPath, checkSpec),
      );
    }
    groups.push({
      group_id: groupSpec.group_id,
      label: groupSpec.label,
      checks,
    });
  }

  return groups;
}

async function evaluateRepoCompletenessCheck(destinationPath, spec) {
  if (spec.type === "glob_markdown") {
    const exists = await matchMarkdownPattern(
      destinationPath,
      spec.path,
      spec.pattern,
    );
    return {
      check_id: spec.check_id,
      label: spec.label,
      status: exists ? "pass" : "missing",
      detail: exists
        ? `Found matching markdown under ${spec.path}.`
        : `No matching markdown found under ${spec.path}.`,
      path: spec.path,
    };
  }

  const absolutePath = path.join(destinationPath, spec.path);
  const exists = await pathExists(absolutePath);

  if (!exists) {
    return {
      check_id: spec.check_id,
      label: spec.label,
      status: "missing",
      detail: "Required path not found.",
      path: spec.path,
    };
  }

  if (spec.type === "directory") {
    const stats = await fs.lstat(absolutePath);
    return {
      check_id: spec.check_id,
      label: spec.label,
      status: stats.isDirectory() ? "pass" : "missing",
      detail: stats.isDirectory()
        ? "Directory exists."
        : "Path exists but is not a directory.",
      path: spec.path,
    };
  }

  const stats = await fs.lstat(absolutePath);
  return {
    check_id: spec.check_id,
    label: spec.label,
    status: stats.isFile() ? "pass" : "missing",
    detail: stats.isFile() ? "File exists." : "Path exists but is not a file.",
    path: spec.path,
  };
}

async function matchMarkdownPattern(destinationPath, relativeDirPath, pattern) {
  const absoluteDir = path.join(destinationPath, relativeDirPath);
  if (!(await pathExists(absoluteDir))) {
    return false;
  }

  const stats = await fs.lstat(absoluteDir);
  if (!stats.isDirectory()) {
    return false;
  }

  const entries = await fs.readdir(absoluteDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) {
      continue;
    }
    if (pattern.test(entry.name)) {
      return true;
    }
  }

  return false;
}

async function generateProjectRepoFromDiscovery(payload) {
  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }

  const profile = String(payload?.profile ?? "").trim();
  const allowedProfiles = new Set([
    "web_app",
    "data_pipeline",
    "agent_platform",
    "internal_tooling",
  ]);
  if (!allowedProfiles.has(profile)) {
    throw new ApiError(
      400,
      "invalid_profile",
      "profile must be one of: web_app, data_pipeline, agent_platform, internal_tooling.",
    );
  }

  const session = await loadDiscoverySession(sessionId);
  if (!session?.synthesis) {
    throw new ApiError(
      409,
      "missing_synthesis",
      "Discovery session does not have synthesis output yet.",
    );
  }

  const approvalGranted = await isDiscoveryApprovalGranted(sessionId);
  if (!approvalGranted) {
    throw new ApiError(
      409,
      "approval_required",
      "Discovery session is not approved. Mark approval artifact before generating project repo.",
      {
        approval_artifact_path: session.approval?.approval_artifact_path ?? "",
      },
    );
  }

  const destinationPath = await resolveDestinationPath(
    String(payload?.destination_repo ?? "").trim(),
  );
  const overwrite = Boolean(payload?.overwrite);
  const prep = await prepareDestination({
    destinationPath,
    overwrite,
    confirmation: payload?.overwrite_confirmation,
  });
  if (!prep.canProceed) {
    await recordBuilderAudit({
      action: "generate-from-discovery",
      status: "rejected",
      destinationPath,
      detail: "overwrite confirmation required",
    });
    throw new ApiError(
      409,
      "overwrite_confirmation_required",
      "Destination exists and is not empty.",
      prep.conflict,
    );
  }

  await fs.mkdir(destinationPath, { recursive: true });
  const generatedFiles = [];

  await seedHarnessRepo(destinationPath, generatedFiles);
  await applyProfileOverlay(
    destinationPath,
    profile,
    sessionId,
    generatedFiles,
  );
  await writeGeneratedDiscoveryArtifacts({
    destinationPath,
    profile,
    session,
    sessionId,
    generatedFiles,
  });
  const templateFillMapArtifacts = await writeTemplateFillMapArtifacts({
    sessionId,
    workflowType: "new_project",
    targetRepo: String(payload?.destination_repo ?? "").trim(),
    targetMode: "local",
    profile,
    generatedFiles,
    scanSummary: session.project_scan_summary,
  });

  const validation = await validateGeneratedHarnessSeed(destinationPath);
  const generatedProjectSpecPath = disclosePath(
    path.join(
      destinationPath,
      "docs",
      "product_specs",
      `discovery_${sessionId}_project_spec.md`,
    ),
  );

  session.artifacts = {
    ...session.artifacts,
    generated_repo_path: disclosePath(destinationPath),
    generated_project_spec: generatedProjectSpecPath,
    template_fill_map_json: templateFillMapArtifacts.json,
    template_fill_map_markdown: templateFillMapArtifacts.markdown,
  };
  await saveDiscoverySession(session);

  await recordBuilderAudit({
    action: "generate-from-discovery",
    status: prep.overwrote ? "overwritten" : "created",
    destinationPath,
    detail: `session=${sessionId}; profile=${profile}; validation=${validation.status}`,
  });

  return {
    version: "GenerateProjectRepoResponseV1",
    status: prep.overwrote ? "overwritten" : "created",
    destination_path: disclosePath(destinationPath),
    profile,
    session_id: sessionId,
    harness_seed_version: HARNESS_SEED_VERSION,
    generated_files: generatedFiles.sort((a, b) => a.localeCompare(b)),
    template_fill_map_artifact_paths: templateFillMapArtifacts,
    validation,
  };
}

async function importHarnessPath(payload) {
  const sourceRaw = String(payload?.source_path ?? "").trim();
  if (!sourceRaw) {
    throw new ApiError(400, "invalid_source_path", "source_path is required.");
  }

  const sourcePath = path.resolve(sourceRaw);
  if (!(await pathExists(sourcePath))) {
    throw new ApiError(
      404,
      "source_path_missing",
      `source_path does not exist: ${disclosePath(sourcePath)}`,
    );
  }

  const sourceStats = await fs.lstat(sourcePath);
  if (sourceStats.isSymbolicLink()) {
    throw new ApiError(
      400,
      "source_symlink_blocked",
      "source_path cannot be a symlink.",
    );
  }

  const destinationPath = await resolveDestinationPath(
    String(payload?.destination_repo ?? "").trim(),
  );
  const overwrite = Boolean(payload?.overwrite);
  const prep = await prepareDestination({
    destinationPath,
    overwrite,
    confirmation: payload?.overwrite_confirmation,
  });
  if (!prep.canProceed) {
    await recordBuilderAudit({
      action: "import-harness-path",
      status: "rejected",
      destinationPath,
      detail: "overwrite confirmation required",
    });
    throw new ApiError(
      409,
      "overwrite_confirmation_required",
      "Destination exists and is not empty.",
      prep.conflict,
    );
  }

  await fs.mkdir(destinationPath, { recursive: true });

  if (sourceStats.isDirectory()) {
    await copyDirectoryContentsSafe(sourcePath, destinationPath, {
      skipGit: true,
    });
  } else if (sourceStats.isFile()) {
    const targetPath = path.join(destinationPath, path.basename(sourcePath));
    await fs.copyFile(sourcePath, targetPath);
  } else {
    throw new ApiError(
      400,
      "unsupported_source_type",
      "source_path must be a file or directory.",
    );
  }

  await recordBuilderAudit({
    action: "import-harness-path",
    status: prep.overwrote ? "overwritten" : "imported",
    destinationPath,
    detail: "source imported from local path",
  });

  return {
    version: "ImportHarnessResponseV1",
    status: prep.overwrote ? "overwritten" : "imported",
    destination_path: disclosePath(destinationPath),
    source: disclosePath(sourcePath),
    mode: "path",
  };
}

async function importHarnessBundle(payload) {
  const destinationPath = await resolveDestinationPath(
    String(payload?.destination_repo ?? "").trim(),
  );
  const overwrite = Boolean(payload?.overwrite);
  const prep = await prepareDestination({
    destinationPath,
    overwrite,
    confirmation: payload?.overwrite_confirmation,
  });
  if (!prep.canProceed) {
    await recordBuilderAudit({
      action: "import-harness-bundle",
      status: "rejected",
      destinationPath,
      detail: "overwrite confirmation required",
    });
    throw new ApiError(
      409,
      "overwrite_confirmation_required",
      "Destination exists and is not empty.",
      prep.conflict,
    );
  }

  const bundleInfo = await materializeBundle(payload);
  const extractRoot = await extractBundleSafely(bundleInfo);

  await fs.mkdir(destinationPath, { recursive: true });
  await copyDirectoryContentsSafe(extractRoot, destinationPath, {
    skipGit: true,
  });

  await recordBuilderAudit({
    action: "import-harness-bundle",
    status: prep.overwrote ? "overwritten" : "imported",
    destinationPath,
    detail: `bundle=${bundleInfo.displayName}`,
  });

  return {
    version: "ImportHarnessResponseV1",
    status: prep.overwrote ? "overwritten" : "imported",
    destination_path: disclosePath(destinationPath),
    source: bundleInfo.displayName,
    mode: "bundle",
  };
}

function assertSshRemoteEnabled() {
  if (!sshRemoteEnabled) {
    throw new ApiError(
      403,
      "remote_ssh_disabled",
      "SSH remote mode is disabled. Set BUILDER_REMOTE_SSH_ENABLED=true to enable guarded endpoints.",
    );
  }
}

function assertExistingProjectModeEnabled() {
  if (!existingProjectModeEnabled) {
    throw new ApiError(
      403,
      "existing_project_mode_disabled",
      "Existing project integration mode is disabled. Set BUILDER_EXISTING_PROJECT_MODE=true to enable guided sidecar deploy flows.",
    );
  }
}

function normalizeRemoteTarget(rawTarget) {
  const host = String(rawTarget?.host ?? "").trim();
  const user = String(rawTarget?.user ?? "").trim();
  const allowlistedRootRemote = String(
    rawTarget?.allowlisted_root ?? "",
  ).trim();
  const connectionMode = String(rawTarget?.connection_mode ?? "ssh")
    .trim()
    .toLowerCase();
  const port = Number(rawTarget?.port ?? 22);
  const targetIdRaw = String(rawTarget?.target_id ?? "").trim();
  const profileLabel = String(rawTarget?.profile_label ?? "").trim();
  const authMethodRaw = String(rawTarget?.auth_method ?? "ssh_agent")
    .trim()
    .toLowerCase();
  const pemPathRaw = String(rawTarget?.pem_path ?? "").trim();
  const knownHostsModeRaw = String(rawTarget?.known_hosts_mode ?? "strict")
    .trim()
    .toLowerCase();

  if (connectionMode !== "ssh") {
    throw new ApiError(
      400,
      "invalid_connection_mode",
      "connection_mode must be ssh.",
    );
  }
  if (!host || !/^[a-zA-Z0-9._-]+$/.test(host)) {
    throw new ApiError(
      400,
      "invalid_remote_host",
      "target.host is required and must be hostname-safe.",
    );
  }
  if (!user || !/^[a-zA-Z0-9._-]+$/.test(user)) {
    throw new ApiError(
      400,
      "invalid_remote_user",
      "target.user is required and must be username-safe.",
    );
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new ApiError(
      400,
      "invalid_remote_port",
      "target.port must be an integer between 1 and 65535.",
    );
  }
  if (
    !allowlistedRootRemote ||
    !allowlistedRootRemote.startsWith("/") ||
    allowlistedRootRemote.includes("..")
  ) {
    throw new ApiError(
      400,
      "invalid_remote_allowlist_root",
      "target.allowlisted_root must be an absolute remote path without traversal sequences.",
    );
  }
  if (authMethodRaw !== "ssh_agent" && authMethodRaw !== "pem_path") {
    throw new ApiError(
      400,
      "invalid_remote_auth_method",
      "target.auth_method must be ssh_agent or pem_path.",
    );
  }
  if (knownHostsModeRaw !== "strict" && knownHostsModeRaw !== "accept_new") {
    throw new ApiError(
      400,
      "invalid_known_hosts_mode",
      "target.known_hosts_mode must be strict or accept_new.",
    );
  }
  if (authMethodRaw === "pem_path") {
    if (!pemPathRaw) {
      throw new ApiError(
        400,
        "missing_remote_pem_path",
        "target.pem_path is required when auth_method=pem_path.",
      );
    }
    if (!path.isAbsolute(pemPathRaw) || pemPathRaw.includes("..")) {
      throw new ApiError(
        400,
        "invalid_remote_pem_path",
        "target.pem_path must be an absolute local path without traversal.",
      );
    }
  }

  return {
    target_id: targetIdRaw || `${user}@${host}:${port}`,
    connection_mode: "ssh",
    host,
    user,
    port,
    profile_label: profileLabel,
    auth_method: authMethodRaw,
    pem_path: pemPathRaw,
    known_hosts_mode: knownHostsModeRaw,
    allowlisted_root: allowlistedRootRemote,
    status: "configured",
  };
}

function sanitizeRemoteShellValue(value) {
  const normalized = String(value ?? "").replaceAll("'", "'\"'\"'");
  return `'${normalized}'`;
}

function buildSshArgs(target, remoteCommand = "") {
  const args = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=6"];
  if (target.known_hosts_mode === "accept_new") {
    args.push("-o", "StrictHostKeyChecking=accept-new");
  }
  if (target.auth_method === "pem_path") {
    args.push("-i", target.pem_path, "-o", "IdentitiesOnly=yes");
  }
  args.push("-p", String(target.port), `${target.user}@${target.host}`);
  if (remoteCommand) {
    args.push(remoteCommand);
  }
  return args;
}

function assertRemoteCommandAllowed(command) {
  if (!command) {
    throw new ApiError(400, "invalid_remote_command", "command is required.");
  }

  const allowed = sshAllowedCommands.some(
    (allowedPrefix) =>
      command === allowedPrefix || command.startsWith(`${allowedPrefix} `),
  );
  if (!allowed) {
    throw new ApiError(
      403,
      "remote_command_not_allowed",
      "Command is not allowlisted for remote execution.",
      {
        allowlisted_prefixes: sshAllowedCommands,
      },
    );
  }
}

async function testRemoteSsh(payload) {
  assertSshRemoteEnabled();
  const target = normalizeRemoteTarget(payload?.target ?? payload ?? {});
  if (!commandExists("ssh")) {
    throw new ApiError(
      500,
      "ssh_binary_missing",
      "ssh command is not available on this host.",
    );
  }
  const args = buildSshArgs(target, "pwd");

  try {
    const stdout = execFileSync("ssh", args, {
      encoding: "utf8",
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 10_000,
      maxBuffer: 2 * 1024 * 1024,
    }).trim();
    await recordBuilderAudit({
      action: "remote-ssh-test",
      status: "pass",
      destinationPath: `${target.user}@${target.host}:${target.port}`,
      detail: `target=${target.target_id}; remote_pwd=${discloseText(stdout)}`,
    });
    return {
      version: "RemoteSshTestResponseV1",
      target: {
        ...target,
        allowlisted_root: discloseText(target.allowlisted_root),
      },
      status: "pass",
      detail: stdout
        ? `remote pwd: ${discloseText(stdout)}`
        : "ssh test executed successfully.",
    };
  } catch (error) {
    const detail = String(
      error?.stderr || error?.stdout || error?.message || error,
    ).trim();
    await recordBuilderAudit({
      action: "remote-ssh-test",
      status: "fail",
      destinationPath: `${target.user}@${target.host}:${target.port}`,
      detail: discloseText(detail),
    });
    return {
      version: "RemoteSshTestResponseV1",
      target: {
        ...target,
        allowlisted_root: discloseText(target.allowlisted_root),
      },
      status: "fail",
      detail: discloseText(detail) || "remote ssh test failed",
    };
  }
}

async function executeRemoteSsh(payload) {
  assertSshRemoteEnabled();
  const target = normalizeRemoteTarget(payload?.target ?? payload ?? {});
  if (!commandExists("ssh")) {
    throw new ApiError(
      500,
      "ssh_binary_missing",
      "ssh command is not available on this host.",
    );
  }

  const command = String(payload?.command ?? "").trim();
  assertRemoteCommandAllowed(command);

  const remoteCommand = `cd ${sanitizeRemoteShellValue(target.allowlisted_root)} && ${command}`;
  const args = buildSshArgs(target, remoteCommand);

  try {
    const stdout = execFileSync("ssh", args, {
      encoding: "utf8",
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 15_000,
      maxBuffer: 3 * 1024 * 1024,
    });
    await recordBuilderAudit({
      action: "remote-ssh-execute",
      status: "pass",
      destinationPath: `${target.user}@${target.host}:${target.port}`,
      detail: `command=${command}`,
    });
    return {
      version: "RemoteSshExecuteResponseV1",
      target: {
        ...target,
        allowlisted_root: discloseText(target.allowlisted_root),
      },
      status: "pass",
      command,
      stdout: discloseText(String(stdout ?? "")),
      stderr: "",
      exit_code: 0,
    };
  } catch (error) {
    const stdout = String(error?.stdout ?? "");
    const stderr = String(error?.stderr ?? error?.message ?? "");
    const exitCode = Number(error?.status ?? 1);
    await recordBuilderAudit({
      action: "remote-ssh-execute",
      status: "fail",
      destinationPath: `${target.user}@${target.host}:${target.port}`,
      detail: `command=${command}; error=${discloseText(stderr)}`,
    });
    return {
      version: "RemoteSshExecuteResponseV1",
      target: {
        ...target,
        allowlisted_root: discloseText(target.allowlisted_root),
      },
      status: "fail",
      command,
      stdout: discloseText(stdout),
      stderr: discloseText(stderr),
      exit_code: Number.isFinite(exitCode) ? exitCode : 1,
    };
  }
}

async function materializeBundle(payload) {
  const bundlePathRaw = String(payload?.bundle_path ?? "").trim();
  const bundleBase64 =
    typeof payload?.bundle_base64 === "string" ? payload.bundle_base64 : "";
  const filename = String(payload?.filename ?? "").trim();

  if (!bundlePathRaw && !bundleBase64) {
    throw new ApiError(
      400,
      "missing_bundle",
      "Provide bundle_path or bundle_base64.",
    );
  }

  if (bundlePathRaw) {
    const bundlePath = path.resolve(bundlePathRaw);
    if (!(await pathExists(bundlePath))) {
      throw new ApiError(
        404,
        "bundle_missing",
        `Bundle path does not exist: ${disclosePath(bundlePath)}`,
      );
    }
    return {
      path: bundlePath,
      displayName: disclosePath(bundlePath),
      cleanup: async () => {},
    };
  }

  const bundleFileName = sanitizeBundleFileName(filename);
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "moradins-bundle-"));
  const bundlePath = path.join(tempRoot, bundleFileName);
  const normalizedBase64 = bundleBase64.includes(",")
    ? bundleBase64.split(",").pop()
    : bundleBase64;
  const buffer = Buffer.from(normalizedBase64, "base64");
  await fs.writeFile(bundlePath, buffer);

  return {
    path: bundlePath,
    displayName: bundleFileName,
    cleanup: async () => {
      await fs.rm(tempRoot, { recursive: true, force: true });
    },
  };
}

function sanitizeBundleFileName(rawName) {
  const fallback = `import_${Date.now()}.zip`;
  const value = String(rawName ?? "").trim();
  if (!value) {
    return fallback;
  }

  if (value.includes("/") || value.includes("\\") || value.includes("\0")) {
    throw new ApiError(
      400,
      "invalid_bundle_filename",
      "filename must not contain path separators.",
    );
  }

  const normalized = path.basename(value);
  if (!normalized || normalized === "." || normalized === "..") {
    throw new ApiError(
      400,
      "invalid_bundle_filename",
      "filename must be a valid file name.",
    );
  }

  return normalized;
}

async function extractBundleSafely(bundleInfo) {
  const extractionRoot = await fs.mkdtemp(
    path.join(os.tmpdir(), "moradins-extract-"),
  );
  const bundlePath = bundleInfo.path;
  const lower = bundlePath.toLowerCase();

  try {
    if (lower.endsWith(".zip")) {
      const listing = execFileSync("unzip", ["-Z1", bundlePath], {
        encoding: "utf8",
      });
      validateArchiveListing(listing.split(/\r?\n/).filter(Boolean));
      execFileSync("unzip", ["-oq", bundlePath, "-d", extractionRoot], {
        stdio: "ignore",
      });
    } else if (lower.endsWith(".tar.gz") || lower.endsWith(".tgz")) {
      const listing = execFileSync("tar", ["-tzf", bundlePath], {
        encoding: "utf8",
      });
      validateArchiveListing(listing.split(/\r?\n/).filter(Boolean));
      execFileSync("tar", ["-xzf", bundlePath, "-C", extractionRoot], {
        stdio: "ignore",
      });
    } else {
      throw new ApiError(
        400,
        "unsupported_bundle_format",
        "Only .zip, .tar.gz, and .tgz bundles are supported.",
      );
    }

    const entries = await fs.readdir(extractionRoot, { withFileTypes: true });
    const visibleEntries = entries.filter(
      (entry) => !entry.name.startsWith("."),
    );

    if (visibleEntries.length === 1 && visibleEntries[0].isDirectory()) {
      return path.join(extractionRoot, visibleEntries[0].name);
    }
    return extractionRoot;
  } catch (error) {
    await fs.rm(extractionRoot, { recursive: true, force: true });
    throw error;
  } finally {
    await bundleInfo.cleanup();
  }
}

function validateArchiveListing(entries) {
  for (const entry of entries) {
    const normalized = entry.replaceAll("\\", "/").trim();
    if (!normalized || normalized.endsWith("/")) {
      continue;
    }
    if (
      normalized.startsWith("/") ||
      normalized.includes("../") ||
      normalized.includes("..\\")
    ) {
      throw new ApiError(
        400,
        "unsafe_archive_path",
        `Archive contains unsafe path: ${normalized}`,
      );
    }
  }
}

async function loadMoradinPayloadManifest() {
  const manifestPath = path.join(repoRoot, MORADIN_PAYLOAD_MANIFEST_RELATIVE_PATH);
  const content = await fs.readFile(manifestPath, "utf8").catch((error) => {
    throw new ApiError(
      500,
      "payload_manifest_missing",
      `Moradin payload manifest is required at ${MORADIN_PAYLOAD_MANIFEST_RELATIVE_PATH}.`,
      { error: String(error) },
    );
  });
  const manifest = parseSimpleYamlManifest(content);
  const includePaths = normalizePayloadPathList(manifest.include_paths);
  const excludePaths = normalizePayloadPathList(manifest.exclude_paths);
  const missingIncludes = REQUIRED_MORADIN_PAYLOAD_INCLUDES.filter(
    (requiredPath) => !includePaths.includes(requiredPath),
  );

  if (
    Number(manifest.manifest_version) !== 1 ||
    manifest.kind !== "moradin_payload" ||
    manifest.payload_id !== "moradin_harness_payload" ||
    manifest.source_root !== "." ||
    includePaths.length === 0 ||
    missingIncludes.length > 0
  ) {
    throw new ApiError(
      500,
      "payload_manifest_invalid",
      "Moradin payload manifest is invalid.",
      {
        manifest_path: MORADIN_PAYLOAD_MANIFEST_RELATIVE_PATH,
        missing_required_includes: missingIncludes,
      },
    );
  }

  return {
    version: "MoradinPayloadManifestV1",
    manifest_version: Number(manifest.manifest_version),
    name: String(manifest.name ?? ""),
    kind: String(manifest.kind ?? ""),
    payload_id: String(manifest.payload_id ?? ""),
    payload_version: String(manifest.payload_version ?? ""),
    source_root: String(manifest.source_root ?? "."),
    compatibility_template_root: String(
      manifest.compatibility_template_root ?? ".harness_template",
    ),
    materialization_target: String(
      manifest.materialization_target ?? "target_repo_root",
    ),
    sidecar_default_dir: String(
      manifest.sidecar_default_dir ?? ".moradins-harness",
    ),
    compatibility_window: String(manifest.compatibility_window ?? ""),
    include_paths: includePaths,
    exclude_paths: excludePaths,
  };
}

function parseSimpleYamlManifest(content) {
  const result = {};
  let activeListKey = "";
  for (const line of String(content ?? "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const listMatch = trimmed.match(/^-\s+(.*)$/);
    if (listMatch && activeListKey) {
      if (!Array.isArray(result[activeListKey])) {
        result[activeListKey] = [];
      }
      result[activeListKey].push(parseYamlScalar(listMatch[1]));
      continue;
    }
    const keyMatch = trimmed.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!keyMatch) {
      continue;
    }
    const key = keyMatch[1];
    const rawValue = keyMatch[2] ?? "";
    if (!rawValue.trim()) {
      result[key] = [];
      activeListKey = key;
      continue;
    }
    result[key] = parseYamlScalar(rawValue);
    activeListKey = "";
  }
  return result;
}

function parseYamlScalar(rawValue) {
  const value = String(rawValue ?? "").trim();
  if (/^-?\d+$/.test(value)) {
    return Number(value);
  }
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function normalizePayloadPathList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  const paths = [];
  for (const entry of value) {
    const normalized = normalizePayloadRelativePath(entry);
    if (normalized && !paths.includes(normalized)) {
      paths.push(normalized);
    }
  }
  return paths;
}

function normalizePayloadRelativePath(value) {
  const raw = String(value ?? "").trim();
  if (!raw || path.isAbsolute(raw)) {
    return "";
  }
  const normalized = normalizePath(path.normalize(raw)).replace(/^\.\//, "");
  if (
    !normalized ||
    normalized === "." ||
    normalized.startsWith("../") ||
    normalized.includes("/../")
  ) {
    return "";
  }
  return normalized;
}

function isPayloadPathExcluded(relativePath, manifest) {
  const normalized = normalizePath(relativePath);
  return manifest.exclude_paths.some(
    (excludePath) =>
      normalized === excludePath || normalized.startsWith(`${excludePath}/`),
  );
}

async function seedHarnessRepo(destinationPath, generatedFiles) {
  const manifest = await loadMoradinPayloadManifest();
  for (const relativePath of manifest.include_paths) {
    if (isPayloadPathExcluded(relativePath, manifest)) {
      continue;
    }
    const sourcePath = path.join(repoRoot, relativePath);
    if (!(await pathExists(sourcePath))) {
      throw new ApiError(
        500,
        "seed_source_missing",
        `Harness seed source path missing: ${relativePath}`,
      );
    }
    const targetPath = path.join(destinationPath, relativePath);
    await copySeedPath(
      sourcePath,
      targetPath,
      relativePath,
      generatedFiles,
      manifest,
    );
  }
}

async function copySeedPath(
  sourcePath,
  destinationPath,
  relativePath,
  generatedFiles,
  manifest,
) {
  const stats = await fs.lstat(sourcePath);
  if (stats.isSymbolicLink()) {
    throw new ApiError(
      400,
      "seed_symlink_blocked",
      `Seed source cannot include symlink: ${relativePath}`,
    );
  }

  if (shouldSkipSeedPath(relativePath, manifest)) {
    return;
  }

  if (stats.isDirectory()) {
    await fs.mkdir(destinationPath, { recursive: true });
    const entries = await fs.readdir(sourcePath, { withFileTypes: true });
    for (const entry of entries) {
      if (
        entry.name === ".git" ||
        entry.name === ".vite" ||
        entry.name === "node_modules" ||
        entry.name === "dist"
      ) {
        continue;
      }
      if (entry.name.endsWith(".tsbuildinfo") || entry.name === "__pycache__") {
        continue;
      }
      const childRelative = normalizePath(path.join(relativePath, entry.name));
      const childSource = path.join(sourcePath, entry.name);
      const childDestination = path.join(destinationPath, entry.name);
      await copySeedPath(
        childSource,
        childDestination,
        childRelative,
        generatedFiles,
        manifest,
      );
    }
    return;
  }

  if (!stats.isFile()) {
    return;
  }

  await fs.mkdir(path.dirname(destinationPath), { recursive: true });
  await fs.copyFile(sourcePath, destinationPath);
  generatedFiles.push(normalizePath(relativePath));
}

async function buildHarnessSidecarAtPath({
  destinationPath,
  profile,
  session,
  sessionId,
  generatedFiles,
}) {
  await fs.mkdir(destinationPath, { recursive: true });
  await seedHarnessRepo(destinationPath, generatedFiles);
  await applyProfileOverlay(
    destinationPath,
    profile,
    sessionId,
    generatedFiles,
  );
  await writeGeneratedDiscoveryArtifacts({
    destinationPath,
    profile,
    session,
    sessionId,
    generatedFiles,
  });
  return validateGeneratedHarnessSeed(destinationPath);
}

async function applyProfileOverlay(
  destinationPath,
  profile,
  sessionId,
  generatedFiles,
) {
  const overlay = PROFILE_OVERLAYS[profile];
  if (!overlay) {
    throw new ApiError(
      400,
      "invalid_profile_overlay",
      `No profile overlay available for profile: ${profile}`,
    );
  }

  const overlayPath = path.join(
    destinationPath,
    "docs",
    "product_specs",
    "generated_profile_overlay.md",
  );
  const onboardingDay0Path = path.join(
    destinationPath,
    "docs",
    "11_ops",
    "day0_onboarding_runbook.md",
  );
  const onboardingDay1Path = path.join(
    destinationPath,
    "docs",
    "11_ops",
    "day1_onboarding_runbook.md",
  );

  const overlayMarkdown = [
    "---",
    `title: \"Generated Profile Overlay ${profile}\"`,
    "status: generated",
    "owner: platform-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    "  - template_profiles.md",
    `  - discovery_${sessionId}_project_spec.md`,
    "---",
    "",
    `# Generated Profile Overlay ${profile}`,
    "",
    `- profile: \`${profile}\``,
    `- harness_seed_version: \`${HARNESS_SEED_VERSION}\``,
    "",
    "## Defaults",
    "",
    ...overlay.defaults.map((item) => `- ${item}`),
    "",
  ].join("\n");

  const day0Markdown = [
    "---",
    'title: "Day 0 Onboarding Runbook"',
    "status: approved",
    "owner: platform-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    "  - codex_run_loop.md",
    "  - docs/entrypoint_guide/index.md",
    "---",
    "",
    "# Day 0 Onboarding Runbook",
    "",
    "## Objectives",
    "",
    "- Verify local dependencies and deterministic quality gates.",
    "- Confirm branch routing marker and human-gate workflow.",
    "- Validate tracker sync and builder endpoint availability.",
    "",
  ].join("\n");

  const day1Markdown = [
    "---",
    'title: "Day 1 Onboarding Runbook"',
    "status: approved",
    "owner: platform-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    "  - day0_onboarding_runbook.md",
    "  - ../15_checklists/agent_cycle_gate.md",
    "---",
    "",
    "# Day 1 Onboarding Runbook",
    "",
    "## Objectives",
    "",
    "- Execute first scoped cycle with explicit plan and acceptance checks.",
    "- Update control artifacts and changelog with approval reference.",
    "- Confirm release-gate health for handoff readiness.",
    "",
  ].join("\n");

  await fs.mkdir(path.dirname(overlayPath), { recursive: true });
  await fs.mkdir(path.dirname(onboardingDay0Path), { recursive: true });
  await fs.writeFile(overlayPath, `${overlayMarkdown}\n`, "utf8");
  await fs.writeFile(onboardingDay0Path, `${day0Markdown}\n`, "utf8");
  await fs.writeFile(onboardingDay1Path, `${day1Markdown}\n`, "utf8");

  generatedFiles.push("docs/product_specs/generated_profile_overlay.md");
  generatedFiles.push("docs/11_ops/day0_onboarding_runbook.md");
  generatedFiles.push("docs/11_ops/day1_onboarding_runbook.md");
}

async function writeGeneratedDiscoveryArtifacts({
  destinationPath,
  profile,
  session,
  sessionId,
  generatedFiles,
}) {
  const sessionRelativeRoot = normalizePath(
    path.join("Harness/artifacts/control/discovery_sessions", sessionId),
  );
  const sessionRoot = path.join(destinationPath, sessionRelativeRoot);
  const intakePath = path.join(sessionRoot, "intake.md");
  const synthesisPath = path.join(sessionRoot, "synthesis.md");
  const sessionJsonPath = path.join(sessionRoot, "session.json");
  const specRelativePath = normalizePath(
    path.join("docs/product_specs", `discovery_${sessionId}_project_spec.md`),
  );
  const designRelativePath = normalizePath(
    path.join("docs/design_docs", `discovery_${sessionId}_architecture.md`),
  );
  const planRelativePath = normalizePath(
    path.join(
      "docs/exec_plans/implementation/active",
      `plan_${sessionId}_discovery_generated.md`,
    ),
  );

  await fs.mkdir(sessionRoot, { recursive: true });
  await fs.mkdir(path.join(destinationPath, "docs", "product_specs"), {
    recursive: true,
  });
  await fs.mkdir(path.join(destinationPath, "docs", "design_docs"), {
    recursive: true,
  });
  await fs.mkdir(
    path.join(
      destinationPath,
      "docs",
      "exec_plans",
      "implementation",
      "active",
    ),
    { recursive: true },
  );

  const intakeLines = [
    "# Discovery Intake",
    "",
    `- session_id: \`${sessionId}\``,
    `- input_mode: \`${session.intake.input_mode}\``,
    "",
    "## Intake Fields",
    "",
    ...Object.entries(session.intake).map(
      ([key, value]) => `- ${key}: ${String(value ?? "")}`,
    ),
    "",
  ];

  const synthesisLines = [
    "# Discovery Synthesis",
    "",
    `- session_id: \`${sessionId}\``,
    `- profile: \`${profile}\``,
    `- harness_seed_version: \`${HARNESS_SEED_VERSION}\``,
    "",
    "## Summary",
    "",
    String(session.synthesis?.summary ?? ""),
    "",
    "## Must Haves",
    "",
    ...normalizeStringArray(session.synthesis?.must_haves).map(
      (item) => `- ${item}`,
    ),
    "",
  ];

  const specLines = [
    `# Discovery Project Spec (${sessionId})`,
    "",
    `- profile: \`${profile}\``,
    `- input_mode: \`${session.intake.input_mode}\``,
    "",
    "## Intent",
    "",
    String(
      session.synthesis?.product_spec?.intent ??
        session.intake.project_goal ??
        "",
    ),
    "",
    "## Target Users",
    "",
    ...normalizeStringArray(session.synthesis?.product_spec?.target_users).map(
      (item) => `- ${item}`,
    ),
    "",
    "## Constraints",
    "",
    ...normalizeStringArray(session.synthesis?.product_spec?.constraints).map(
      (item) => `- ${item}`,
    ),
    "",
  ];

  const designLines = [
    `# Discovery Architecture (${sessionId})`,
    "",
    `- profile: \`${profile}\``,
    "",
    "## Components",
    "",
    ...normalizeStringArray(session.synthesis?.design?.components).map(
      (item) => `- ${item}`,
    ),
    "",
    "## Data Flows",
    "",
    ...normalizeStringArray(session.synthesis?.design?.data_flows).map(
      (item) => `- ${item}`,
    ),
    "",
    "## Risks",
    "",
    ...normalizeStringArray(session.synthesis?.design?.risks).map(
      (item) => `- ${item}`,
    ),
    "",
  ];

  const planLines = [
    `# Generated Implementation Plan (${sessionId})`,
    "",
    `- profile: \`${profile}\``,
    `- harness_seed_version: \`${HARNESS_SEED_VERSION}\``,
    "",
    "## Workstreams",
    "",
    ...normalizeStringArray(session.synthesis?.plan?.workstreams).map(
      (item) => `- ${item}`,
    ),
    "",
    "## Initial Backlog",
    "",
    ...normalizeStringArray(session.synthesis?.plan?.initial_backlog).map(
      (item) => `- ${item}`,
    ),
    "",
  ];

  await fs.writeFile(intakePath, `${intakeLines.join("\n")}\n`, "utf8");
  await fs.writeFile(synthesisPath, `${synthesisLines.join("\n")}\n`, "utf8");
  await fs.writeFile(
    sessionJsonPath,
    `${JSON.stringify(session, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(
    path.join(destinationPath, specRelativePath),
    `${specLines.join("\n")}\n`,
    "utf8",
  );
  await fs.writeFile(
    path.join(destinationPath, designRelativePath),
    `${designLines.join("\n")}\n`,
    "utf8",
  );
  await fs.writeFile(
    path.join(destinationPath, planRelativePath),
    `${planLines.join("\n")}\n`,
    "utf8",
  );

  generatedFiles.push(
    normalizePath(path.join(sessionRelativeRoot, "intake.md")),
  );
  generatedFiles.push(
    normalizePath(path.join(sessionRelativeRoot, "synthesis.md")),
  );
  generatedFiles.push(
    normalizePath(path.join(sessionRelativeRoot, "session.json")),
  );
  generatedFiles.push(specRelativePath);
  generatedFiles.push(designRelativePath);
  generatedFiles.push(planRelativePath);
}

function classifyGeneratedFileSource(relativePath) {
  const normalized = normalizePath(relativePath);
  if (normalized.startsWith("Harness/artifacts/control/discovery_sessions/")) {
    return "scan_derived";
  }
  if (
    normalized === "docs/product_specs/generated_profile_overlay.md" ||
    normalized.startsWith("docs/11_ops/day")
  ) {
    return "profile_overlay";
  }
  if (
    normalized.startsWith("docs/product_specs/discovery_") ||
    normalized.startsWith("docs/design_docs/discovery_") ||
    normalized.startsWith("docs/exec_plans/implementation/active/plan_")
  ) {
    return "user_filled";
  }
  return "seed_template";
}

async function writeTemplateFillMapArtifacts({
  sessionId,
  workflowType,
  targetRepo,
  targetMode,
  profile,
  generatedFiles,
  scanSummary = null,
}) {
  const normalizedScanSummary = isRecord(scanSummary)
    ? {
        languages: normalizeStringArray(scanSummary.languages),
        package_managers: normalizeStringArray(scanSummary.package_managers),
        ci_surfaces: normalizeStringArray(scanSummary.ci_surfaces),
        deployment_surfaces: normalizeStringArray(scanSummary.deployment_surfaces),
        critical_gaps: normalizeStringArray(scanSummary.critical_gaps),
      }
    : null;
  const rows = [...generatedFiles]
    .sort((a, b) => a.localeCompare(b))
    .map((relativePath) => ({
      path: relativePath,
      source_kind: classifyGeneratedFileSource(relativePath),
      profile,
      workflow_type: workflowType,
      target_mode: targetMode,
    }));
  const payload = {
    version: "TemplateFillMapV1",
    session_id: sessionId,
    generated_at: new Date().toISOString(),
    workflow_type: workflowType,
    target_repo: targetRepo,
    target_mode: targetMode,
    profile,
    scan_summary: normalizedScanSummary,
    rows,
  };
  const jsonRelativePath = `${DISCOVERY_SESSIONS_RELATIVE_ROOT}/${sessionId}/template_fill_map.json`;
  const markdownRelativePath = `${DISCOVERY_SESSIONS_RELATIVE_ROOT}/${sessionId}/template_fill_map.md`;
  const markdown = [
    "# Template Fill Map",
    "",
    `- session_id: \`${sessionId}\``,
    `- workflow_type: \`${workflowType}\``,
    `- target_mode: \`${targetMode}\``,
    `- target_repo: \`${targetRepo}\``,
    `- profile: \`${profile}\``,
    "",
    ...(normalizedScanSummary
      ? [
          "## Scan-Derived Context",
          "",
          `- languages: ${normalizedScanSummary.languages.join(", ") || "none"}`,
          `- package_managers: ${normalizedScanSummary.package_managers.join(", ") || "none"}`,
          `- ci_surfaces: ${normalizedScanSummary.ci_surfaces.join(", ") || "none"}`,
          `- deployment_surfaces: ${normalizedScanSummary.deployment_surfaces.join(", ") || "none"}`,
          `- critical_gaps: ${normalizedScanSummary.critical_gaps.join(", ") || "none"}`,
          "",
        ]
      : []),
    "| path | source_kind |",
    "| --- | --- |",
    ...rows.map((row) => `| ${row.path} | ${row.source_kind} |`),
    "",
  ].join("\n");

  await writeDiscoveryFile(
    sessionId,
    "template_fill_map.json",
    JSON.stringify(payload, null, 2),
  );
  await writeDiscoveryFile(sessionId, "template_fill_map.md", markdown);

  return {
    json: jsonRelativePath,
    markdown: markdownRelativePath,
  };
}

async function validateGeneratedHarnessSeed(destinationPath) {
  const checks = [];

  async function checkPaths(name, pathsToCheck) {
    const missing = [];
    for (const relPath of pathsToCheck) {
      if (!(await pathExists(path.join(destinationPath, relPath)))) {
        missing.push(relPath);
      }
    }
    if (missing.length > 0) {
      checks.push({
        name,
        status: "fail",
        detail: `missing: ${missing.join(", ")}`,
      });
      return;
    }
    checks.push({
      name,
      status: "pass",
      detail: "all required paths present",
    });
  }

  await checkPaths("root_manifests", [
    "AGENTS.md",
    "README.md",
    "Makefile",
    "pyproject.toml",
  ]);
  await checkPaths("canonical_docs", [
    "docs/engineer_entry/index.md",
    "docs/00_overview/implementation_phases.md",
    "docs/03_architecture/container_topology.md",
    "docs/11_ops/codex_run_loop.md",
    "docs/15_checklists/agent_cycle_gate.md",
    "Harness/moradin_payload/manifest.yaml",
    "Harness/artifacts/control/loop_state.md",
  ]);
  await checkPaths("tracker_surface", [
    "dev_tracker/ui/src/App.tsx",
    "dev_tracker/ui/scripts/control-api.mjs",
    "dev_tracker/ui/tests/builder-page.test.tsx",
  ]);
  await checkPaths("skills_and_tests", [
    "skills",
    "tests/contracts/test_validators.py",
    "tests/scripts/test_moradin_forge.py",
  ]);

  const controlApiDocPath = path.join(
    destinationPath,
    "docs/design_docs/project_builder_control_api.md",
  );
  if (await pathExists(controlApiDocPath)) {
    const content = await fs.readFile(controlApiDocPath, "utf8");
    const hasNoAutoExecution = content.includes(
      "No auto-execution endpoint is exposed.",
    );
    checks.push({
      name: "no_auto_execution_invariant",
      status: hasNoAutoExecution ? "pass" : "fail",
      detail: hasNoAutoExecution
        ? "control API contract explicitly keeps no auto-execution endpoint"
        : "missing no-auto-execution statement in project_builder_control_api.md",
    });
  } else {
    checks.push({
      name: "no_auto_execution_invariant",
      status: "fail",
      detail: "missing docs/design_docs/project_builder_control_api.md",
    });
  }

  return {
    status: checks.every((check) => check.status === "pass") ? "pass" : "fail",
    checks,
  };
}

async function startDiscoverySession(payload) {
  const intake = normalizeIntake(payload?.intake ?? payload ?? {});
  const provider = normalizeDiscoveryProviderId(payload?.provider);
  const model = normalizeDiscoveryModel({
    provider,
    requestedModel: payload?.model,
  });
  const sessionId = buildSessionId();
  const session = {
    version: "DiscoverySessionV1",
    session_id: sessionId,
    status: "intake",
    provider,
    model,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    intake,
    questions: [],
    answers: {},
    question_round: 0,
    project_scan_summary: null,
    project_scan_artifact_paths: null,
    synthesis: null,
    approval: {
      required: true,
      approved: false,
      approval_artifact_path: `Harness/artifacts/control/discovery_sessions/${sessionId}/approval_required.md`,
    },
    artifacts: {
      session_json: `Harness/artifacts/control/discovery_sessions/${sessionId}/session.json`,
    },
  };

  await saveDiscoverySession(session);
  await writeDiscoveryIntakeArtifact(session);
  await writeDiscoveryPromptBundleArtifacts({
    session,
    stage: "questions",
    selectedProfile: "",
  });

  return session;
}

async function answerDiscoverySession(payload) {
  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }

  const session = await loadDiscoverySession(sessionId);
  const incomingAnswers = isRecord(payload?.answers) ? payload.answers : {};

  for (const [key, value] of Object.entries(incomingAnswers)) {
    session.answers[key] = String(value ?? "").trim();
  }

  if (isRecord(payload?.intake_updates)) {
    session.intake = {
      ...session.intake,
      ...normalizeIntake(payload.intake_updates),
    };
  }

  if (payload?.provider) {
    session.provider = normalizeDiscoveryProviderId(payload.provider);
  }
  if (payload?.model) {
    session.model = normalizeDiscoveryModel({
      provider: normalizeDiscoveryProviderId(session.provider),
      requestedModel: payload.model,
    });
  }

  session.updated_at = new Date().toISOString();
  if (session.questions.length > 0) {
    session.status = "answering";
  }

  await saveDiscoverySession(session);
  await writeDiscoveryPromptBundleArtifacts({
    session,
    stage: session.status === "synthesized" ? "synthesis" : "questions",
    selectedProfile: session.synthesis?.recommended_profile ?? "",
  });
  return session;
}

async function generateDiscoverySession(payload) {
  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }

  const session = await loadDiscoverySession(sessionId);

  if (session.questions.length === 0) {
    session.questions = await generateDiscoveryQuestions(session);
    session.status = "questions_generated";
    session.question_round = Number(session.question_round ?? 0);
    session.updated_at = new Date().toISOString();
    await saveDiscoverySession(session);
    await writeDiscoveryQuestionsArtifact(session);
    await writeDiscoveryPromptBundleArtifacts({
      session,
      stage: "questions",
      selectedProfile: "",
    });
    return session;
  }

  if (
    Number(session.question_round ?? 0) < 1 &&
    hasDiscoveryAnswerContent(session.answers)
  ) {
    const followupQuestions = buildAdaptiveFollowupQuestions(session);
    if (followupQuestions.length > 0) {
      const existingIds = new Set(
        session.questions.map((question) => String(question.question_id ?? "")),
      );
      session.questions = [
        ...session.questions,
        ...followupQuestions.filter(
          (question) => !existingIds.has(question.question_id),
        ),
      ];
      session.status = "questions_generated";
      session.question_round = Number(session.question_round ?? 0) + 1;
      session.updated_at = new Date().toISOString();
      await saveDiscoverySession(session);
      await writeDiscoveryQuestionsArtifact(session);
      await writeDiscoveryPromptBundleArtifacts({
        session,
        stage: "questions",
        selectedProfile: "",
      });
      await recordBuilderAudit({
        action: "discovery-followup-generate",
        status: "generated",
        destinationPath: `Harness/artifacts/control/discovery_sessions/${session.session_id}`,
        detail: `followup_questions=${followupQuestions.length}`,
      });
      return session;
    }
  }

  session.synthesis = await generateDiscoverySynthesis(session);
  session.status = "synthesized";
  session.updated_at = new Date().toISOString();
  session.approval = {
    ...session.approval,
    required: true,
    approved: false,
  };

  await saveDiscoverySession(session);
  await writeDiscoverySynthesisArtifacts(session);
  await writeDiscoveryPromptBundleArtifacts({
    session,
    stage: "synthesis",
    selectedProfile: session.synthesis?.recommended_profile ?? "",
  });
  await recordBuilderAudit({
    action: "discovery-synthesis-generate",
    status: "generated",
    destinationPath: `Harness/artifacts/control/discovery_sessions/${session.session_id}`,
    detail: "pending human gate approval",
  });

  return session;
}

async function loadDiscoverySession(sessionId) {
  const sessionPath = getSessionJsonPath(sessionId);
  if (!(await pathExists(sessionPath))) {
    throw new ApiError(
      404,
      "session_not_found",
      `Discovery session not found: ${sessionId}`,
    );
  }
  const session = await safeReadJson(sessionPath, null);
  if (!session) {
    throw new ApiError(
      500,
      "session_unreadable",
      `Discovery session unreadable: ${sessionId}`,
    );
  }
  const approved = await isDiscoveryApprovalGranted(sessionId);
  return {
    ...session,
    provider: normalizeDiscoveryProviderId(session.provider),
    model: normalizeDiscoveryModel({
      provider: normalizeDiscoveryProviderId(session.provider),
      requestedModel: session.model,
    }),
    intake: normalizeIntake(session.intake ?? {}),
    question_round: Number(session.question_round ?? 0),
    project_scan_summary: isRecord(session.project_scan_summary)
      ? session.project_scan_summary
      : null,
    project_scan_artifact_paths: isRecord(session.project_scan_artifact_paths)
      ? session.project_scan_artifact_paths
      : null,
    approval: {
      required: true,
      approved,
      approval_artifact_path:
        String(session?.approval?.approval_artifact_path ?? "").trim() ||
        `Harness/artifacts/control/discovery_sessions/${sessionId}/approval_required.md`,
    },
  };
}

async function saveDiscoverySession(session) {
  const dirPath = path.dirname(getSessionJsonPath(session.session_id));
  await fs.mkdir(dirPath, { recursive: true });
  await fs.writeFile(
    getSessionJsonPath(session.session_id),
    `${JSON.stringify(session, null, 2)}\n`,
    "utf8",
  );
}

async function writeDiscoveryIntakeArtifact(session) {
  const content = [
    "# Discovery Intake",
    "",
    `- session_id: \`${session.session_id}\``,
    `- created_at: \`${session.created_at}\``,
    "",
    "## Intake",
    "",
    ...Object.entries(session.intake).map(
      ([key, value]) => `- ${key}: ${value || ""}`,
    ),
    "",
  ].join("\n");

  await writeDiscoveryFile(session.session_id, "intake.md", content);
  await ensureApprovalArtifact(session.session_id);
}

async function writeDiscoveryQuestionsArtifact(session) {
  const lines = [
    "# Discovery Questions",
    "",
    `- session_id: \`${session.session_id}\``,
    `- generated_at: \`${session.updated_at}\``,
    "",
    "## Questions",
    "",
  ];

  for (const question of session.questions) {
    lines.push(`### ${question.question_id}`);
    lines.push("");
    lines.push(`- prompt: ${question.prompt}`);
    lines.push(`- rationale: ${question.rationale}`);
    lines.push(`- required: ${question.required ? "true" : "false"}`);
    lines.push("");
  }

  await writeDiscoveryFile(
    session.session_id,
    "questions.md",
    lines.join("\n"),
  );
}

async function writeDiscoverySynthesisArtifacts(session) {
  if (!session.synthesis) {
    return;
  }

  const sessionDir = `Harness/artifacts/control/discovery_sessions/${session.session_id}`;
  const productSpecPath = `docs/product_specs/discovery_${session.session_id}_project_spec.md`;
  const designDocPath = `docs/design_docs/discovery_${session.session_id}_architecture.md`;
  const planPath = `docs/exec_plans/implementation/active/plan_${session.session_id}_discovery_generated.md`;
  const productSpecAbsolutePath = path.join(
    discoveryDocsRoot,
    "product_specs",
    `discovery_${session.session_id}_project_spec.md`,
  );
  const designDocAbsolutePath = path.join(
    discoveryDocsRoot,
    "design_docs",
    `discovery_${session.session_id}_architecture.md`,
  );
  const planAbsolutePath = path.join(
    discoveryDocsRoot,
    "exec_plans",
    "implementation",
    "active",
    `plan_${session.session_id}_discovery_generated.md`,
  );

  await fs.mkdir(path.dirname(productSpecAbsolutePath), { recursive: true });
  await fs.mkdir(path.dirname(designDocAbsolutePath), { recursive: true });
  await fs.mkdir(path.dirname(planAbsolutePath), { recursive: true });

  const synthesisContent = [
    "# Discovery Synthesis",
    "",
    `- session_id: \`${session.session_id}\``,
    `- generated_at: \`${session.updated_at}\``,
    "",
    "## Summary",
    "",
    session.synthesis.summary,
    "",
    "## Recommended Profile",
    "",
    `- ${session.synthesis.recommended_profile}`,
    "",
    "## Must-Have Outcomes",
    "",
    ...session.synthesis.must_haves.map((item) => `- ${item}`),
    "",
    "## Open Questions",
    "",
    ...(session.synthesis.open_questions.length > 0
      ? session.synthesis.open_questions.map((item) => `- ${item}`)
      : ["- none"]),
    "",
    "## Human Gate",
    "",
    "- status: pending",
    `- required_approval_artifact: \`${session.approval.approval_artifact_path}\``,
    "",
    "Generated planning artifacts remain non-executable until the approval artifact is marked approved by a human reviewer.",
    "",
  ].join("\n");

  const productSpecContent = [
    "---",
    `title: \"Discovery Project Spec ${session.session_id}\"`,
    "status: draft-pending-human-gate",
    "owner: product-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    `  - Harness/artifacts/control/discovery_sessions/${session.session_id}/synthesis.md`,
    `  - docs/exec_plans/implementation/active/plan_${session.session_id}_discovery_generated.md`,
    "---",
    "",
    `# Discovery Project Spec ${session.session_id}`,
    "",
    "> Execution blocked pending human approval.",
    "",
    "## Project Intent",
    "",
    session.synthesis.product_spec.intent,
    "",
    "## Target Users",
    "",
    ...session.synthesis.product_spec.target_users.map((item) => `- ${item}`),
    "",
    "## Constraints",
    "",
    ...session.synthesis.product_spec.constraints.map((item) => `- ${item}`),
    "",
    "## Milestones",
    "",
    ...session.synthesis.product_spec.milestones.map((item) => `- ${item}`),
    "",
  ].join("\n");

  const designDocContent = [
    "---",
    `title: \"Discovery Architecture Draft ${session.session_id}\"`,
    "status: draft-pending-human-gate",
    "owner: architecture-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    `  - Harness/artifacts/control/discovery_sessions/${session.session_id}/synthesis.md`,
    "---",
    "",
    `# Discovery Architecture Draft ${session.session_id}`,
    "",
    "> Execution blocked pending human approval.",
    "",
    "## Proposed Components",
    "",
    ...session.synthesis.design.components.map((item) => `- ${item}`),
    "",
    "## Data Flows",
    "",
    ...session.synthesis.design.data_flows.map((item) => `- ${item}`),
    "",
    "## Risks",
    "",
    ...session.synthesis.design.risks.map((item) => `- ${item}`),
    "",
  ].join("\n");

  const planContent = [
    "---",
    `title: \"Plan ${session.session_id} Discovery Generated\"`,
    "status: draft-pending-human-gate",
    "owner: platform-operations",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    `  - Harness/artifacts/control/discovery_sessions/${session.session_id}/synthesis.md`,
    `  - ../../docs/product_specs/discovery_${session.session_id}_project_spec.md`,
    "---",
    "",
    `# Plan ${session.session_id} Discovery Generated`,
    "",
    "## Gate",
    "",
    "- approval_status: pending_human_gate",
    `- approval_artifact_path: ${session.approval.approval_artifact_path}`,
    "- execution_scope_active: false",
    "",
    "## Proposed Workstreams",
    "",
    ...session.synthesis.plan.workstreams.map((item) => `- ${item}`),
    "",
    "## Initial Backlog",
    "",
    ...session.synthesis.plan.initial_backlog.map((item) => `- ${item}`),
    "",
  ].join("\n");

  await writeDiscoveryFile(
    session.session_id,
    "synthesis.md",
    synthesisContent,
  );
  await fs.writeFile(
    productSpecAbsolutePath,
    `${productSpecContent}\n`,
    "utf8",
  );
  await fs.writeFile(designDocAbsolutePath, `${designDocContent}\n`, "utf8");
  await fs.writeFile(planAbsolutePath, `${planContent}\n`, "utf8");

  session.artifacts = {
    ...session.artifacts,
    synthesis_markdown: `${sessionDir}/synthesis.md`,
    product_spec: productSpecPath,
    design_doc: designDocPath,
    implementation_plan: planPath,
  };
  await saveDiscoverySession(session);
}

async function buildPromptBundleForSession(payload) {
  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }

  const stageRaw = String(payload?.stage ?? "")
    .trim()
    .toLowerCase();
  const stage = stageRaw === "synthesis" ? "synthesis" : "questions";
  const selectedProfile = String(payload?.selected_profile ?? "").trim();
  const session = await loadDiscoverySession(sessionId);
  const bundle = await writeDiscoveryPromptBundleArtifacts({
    session,
    stage,
    selectedProfile,
  });
  return bundle;
}

async function buildFollowOnPlanForSession(payload) {
  const sessionId = String(payload?.session_id ?? "").trim();
  if (!sessionId) {
    throw new ApiError(400, "invalid_session_id", "session_id is required.");
  }

  const targetRepo = String(payload?.target_repo ?? "").trim();
  if (!targetRepo) {
    throw new ApiError(400, "invalid_target_repo", "target_repo is required.");
  }

  const session = await loadDiscoverySession(sessionId);
  if (!session?.synthesis) {
    throw new ApiError(
      409,
      "missing_synthesis",
      "Discovery session does not have synthesis output yet.",
    );
  }

  const workflowType = session.project_scan_summary?.target_repo
    ? "existing_project"
    : "new_project";
  const selectedProfile =
    String(payload?.selected_profile ?? "").trim() ||
    String(session.synthesis?.recommended_profile ?? "").trim() ||
    recommendProfile(session.intake);
  const phasePlan = buildDeterministicPhasePlan({
    session,
    targetRepo,
    workflowType,
  });
  const alignmentState = await buildAlignmentState({
    session,
    targetRepo,
    workflowType,
    selectedProfile,
    phasePlan,
    targetMode:
      String(session.project_scan_summary?.target_mode ?? "").trim() ===
      "remote_ssh"
        ? "remote_ssh"
        : "local",
    targetPath:
      String(session.artifacts?.generated_repo_path ?? "").trim() ||
      String(session.artifacts?.deployed_sidecar_path ?? "").trim(),
  });
  const prompts = buildFollowOnPrompts({
    session,
    targetRepo,
    selectedProfile,
    workflowType,
    phasePlan,
    alignmentState,
  });
  const artifactPaths = await writeDiscoveryFollowOnPlanArtifacts({
    session,
    targetRepo,
    selectedProfile,
    phasePlan,
    alignmentState,
    prompts,
  });

  return {
    version: "DiscoveryFollowOnPlanResponseV1",
    session_id: session.session_id,
    target_repo: targetRepo,
    workflow_type: workflowType,
    selected_profile: selectedProfile,
    generated_at: new Date().toISOString(),
    phase_plan: phasePlan,
    alignment_state: alignmentState,
    prompts,
    artifact_paths: artifactPaths,
  };
}

async function writeDiscoveryPromptBundleArtifacts({
  session,
  stage,
  selectedProfile,
}) {
  const promptContext = await buildPromptContextForSession({
    session,
    stage,
    selectedProfile,
  });
  await writeDiscoveryFile(
    session.session_id,
    "prompt_context_v1.json",
    JSON.stringify(promptContext, null, 2),
  );
  const bundle = assembleDiscoveryPromptBundle({
    session,
    stage,
    selectedProfile,
    promptContext,
  });
  await writeDiscoveryFile(
    session.session_id,
    "prompt_bundle.json",
    JSON.stringify(bundle, null, 2),
  );
  await writeDiscoveryFile(
    session.session_id,
    "prompt_bundle.md",
    formatPromptBundleMarkdown(bundle),
  );

  session.artifacts = {
    ...session.artifacts,
    prompt_context_json: `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_context_v1.json`,
    context_pack_json: GENERATED_CONTEXT_PACK_RELATIVE_PATH,
    prompt_bundle_json: `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_bundle.json`,
    prompt_bundle_markdown: `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_bundle.md`,
  };
  await saveDiscoverySession(session);
  return bundle;
}

async function buildPromptContextForSession({
  session,
  stage,
  selectedProfile,
}) {
  const selectedProfileSafe =
    String(selectedProfile ?? "").trim() ||
    String(session.synthesis?.recommended_profile ?? "").trim();
  const workflowType = session.project_scan_summary?.target_repo
    ? "existing_project"
    : "new_project";
  const answeredQuestionCount = Object.values(session.answers ?? {}).filter(
    (value) => String(value ?? "").trim().length > 0,
  ).length;
  const contextPack = await safeReadJson(
    path.join(generatedRoot, "context_pack_v1.json"),
    {
      version: "ContextPackV1",
      generated_at: new Date().toISOString(),
      template_manifest: {
        harness_seed_version: HARNESS_SEED_VERSION,
        seed_groups: [],
      },
      service_inventory_summary: {
        planned_count: 0,
        implemented_count: 0,
        planned_only_count: 0,
        top_rows: [],
      },
      route_inventory_summary: {
        router_route_count: 0,
        context_route_count: 0,
        coverage_percent: 0,
        key_routes: [],
      },
      active_guidance: [],
      key_doc_anchors: [],
    },
  );
  const citations = [
    ...(Array.isArray(contextPack?.key_doc_anchors)
      ? contextPack.key_doc_anchors.map((item) => String(item.path ?? ""))
      : []),
    String(session.project_scan_artifact_paths?.markdown ?? ""),
    String(session.artifacts?.synthesis_markdown ?? ""),
    String(session.approval?.approval_artifact_path ?? ""),
  ]
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    version: "PromptContextV1",
    session_id: session.session_id,
    stage,
    workflow_type: workflowType,
    selected_profile: selectedProfileSafe,
    generated_at: new Date().toISOString(),
    included_context_sections: [
      "template_manifest",
      "service_inventory_summary",
      "route_inventory_summary",
      "active_guidance",
      "key_doc_anchors",
      "session_context",
      ...(session.project_scan_summary ? ["project_scan_summary"] : []),
      ...(session.synthesis ? ["synthesis_context"] : []),
    ],
    source_citations: [...new Set(citations)],
    context_pack: contextPack,
    session_context: {
      input_mode: session.intake.input_mode,
      project_goal: session.intake.project_goal,
      users: session.intake.users,
      constraints: session.intake.constraints,
      timeline: session.intake.timeline,
      integrations: session.intake.integrations,
      compliance: session.intake.compliance,
      deployment_target: session.intake.deployment_target,
      other_context: session.intake.other_context,
      answered_question_count: answeredQuestionCount,
      project_scan_summary: session.project_scan_summary ?? null,
      synthesis_context: session.synthesis ?? null,
    },
  };
}

function buildDeterministicPhasePlan({ session, targetRepo, workflowType }) {
  const synthesis = session.synthesis ?? {
    summary: "",
    must_haves: [],
    design: { components: [], risks: [] },
    plan: { workstreams: [], initial_backlog: [] },
    product_spec: { intent: "", target_users: [], constraints: [], milestones: [] },
  };
  const mustHaves = normalizeStringArray(synthesis.must_haves);
  const backlog = normalizeStringArray(synthesis.plan?.initial_backlog);
  const workstreams = normalizeStringArray(synthesis.plan?.workstreams);
  const components = normalizeStringArray(synthesis.design?.components);
  const risks = normalizeStringArray(synthesis.design?.risks);
  const gaps = normalizeStringArray(session.project_scan_summary?.critical_gaps);
  const scanLanguages = normalizeStringArray(session.project_scan_summary?.languages);
  const scanPackageManagers = normalizeStringArray(
    session.project_scan_summary?.package_managers,
  );
  const scanCiSurfaces = normalizeStringArray(
    session.project_scan_summary?.ci_surfaces,
  );
  const scanDeploymentSurfaces = normalizeStringArray(
    session.project_scan_summary?.deployment_surfaces,
  );
  const goal =
    String(synthesis.product_spec?.intent ?? "").trim() ||
    session.intake.project_goal ||
    session.intake.project_prompt ||
    targetRepo;
  const extraContext = String(session.intake.other_context ?? "").trim();
  const repoSurfaceSummary = [
    scanLanguages.length > 0 ? `languages ${scanLanguages.join(", ")}` : "",
    scanPackageManagers.length > 0
      ? `package managers ${scanPackageManagers.join(", ")}`
      : "",
    scanCiSurfaces.length > 0 ? `CI ${scanCiSurfaces.join(", ")}` : "",
    scanDeploymentSurfaces.length > 0
      ? `deployment ${scanDeploymentSurfaces.join(", ")}`
      : "",
  ]
    .filter(Boolean)
    .join("; ");

  return {
    summary: `Phase plan for ${targetRepo} derived from ${workflowType} discovery, synthesis, and harness bootstrap context.`,
    next_recommended_phase_id: "phase_1",
    phases: [
      {
        phase_id: "phase_1",
        title: "Hydrate Harness And Lock Scope",
        objective: `Hydrate the deployed harness for ${targetRepo} and lock a concrete execution boundary for ${goal}.`,
        deliverables: [
          "Fill remaining placeholders and align canonical docs under docs/ with the project context.",
          ...(repoSurfaceSummary
            ? [
                `Respect existing repo surfaces discovered during scan: ${repoSurfaceSummary}.`,
              ]
            : []),
          ...backlog.slice(0, 2),
          ...(extraContext ? [`Capture extra operator context: ${extraContext}`] : []),
        ]
          .filter(Boolean)
          .slice(0, 4),
        execution_focus:
          "Do the minimum repo alignment needed to make the harness trustworthy before feature implementation starts.",
      },
      {
        phase_id: "phase_2",
        title: "Build The Core Project Path",
        objective: `Deliver the thinnest working path that satisfies the approved scope for ${goal}.`,
        deliverables: [...mustHaves.slice(0, 2), ...components.slice(0, 2)]
          .filter(Boolean)
          .slice(0, 4),
        execution_focus:
          "Implement the main user-facing or operator-facing path without expanding beyond the approved scope.",
      },
      {
        phase_id: "phase_3",
        title: "Validate And Prepare Rollout",
        objective: `Stabilize ${targetRepo}, close validation gaps, and prepare rollout evidence.`,
        deliverables: [
          "Run repo-native checks and close the remaining validation gaps.",
          ...(scanCiSurfaces.length > 0
            ? [
                `Preserve and extend the detected validation surface: ${scanCiSurfaces.join(", ")}.`,
              ]
            : []),
          ...gaps.slice(0, 1),
          ...risks.slice(0, 2),
        ]
          .filter(Boolean)
          .slice(0, 4),
        execution_focus:
          "Treat validation, rollout notes, and operational readiness as first-class deliverables.",
      },
    ].map((phase, index) => ({
      ...phase,
      deliverables:
        phase.deliverables.length > 0
          ? phase.deliverables
          : [workstreams[index] ?? `Define ${phase.title.toLowerCase()} deliverables.`],
    })),
  };
}

function buildPromptContextSummary(
  session,
  { targetRepo, selectedProfile, workflowType, alignmentState = null },
) {
  const lines = [
    `target_repo=${targetRepo}`,
    `workflow_type=${workflowType}`,
    `selected_profile=${selectedProfile || "unselected"}`,
    `project_goal=${session.intake.project_goal || "unset"}`,
    `users=${session.intake.users || "unset"}`,
    `constraints=${session.intake.constraints || "unset"}`,
    `timeline=${session.intake.timeline || "unset"}`,
    `integrations=${session.intake.integrations || "unset"}`,
    `compliance=${session.intake.compliance || "unset"}`,
    `deployment_target=${session.intake.deployment_target || "unset"}`,
    `other_context=${session.intake.other_context || "unset"}`,
    `approval_required=${session.approval?.approved ? "approved" : "pending"}`,
  ];

  const scanLanguages = normalizeStringArray(session.project_scan_summary?.languages);
  const scanPackageManagers = normalizeStringArray(
    session.project_scan_summary?.package_managers,
  );
  const scanCiSurfaces = normalizeStringArray(
    session.project_scan_summary?.ci_surfaces,
  );
  const scanDeploymentSurfaces = normalizeStringArray(
    session.project_scan_summary?.deployment_surfaces,
  );
  lines.push(`languages=${scanLanguages.join("; ") || "none"}`);
  lines.push(`package_managers=${scanPackageManagers.join("; ") || "none"}`);
  lines.push(`ci_surfaces=${scanCiSurfaces.join("; ") || "none"}`);
  lines.push(`deployment_surfaces=${scanDeploymentSurfaces.join("; ") || "none"}`);
  if (session.project_scan_summary?.critical_gaps?.length) {
    lines.push(`critical_gaps=${session.project_scan_summary.critical_gaps.join("; ")}`);
  }
  if (alignmentState) {
    lines.push(`alignment_overall=${alignmentState.summary.overall_status}`);
    lines.push(
      `alignment_manual_required=${alignmentState.summary.manual_required_count}`,
    );
    lines.push(`alignment_missing=${alignmentState.summary.missing_count}`);
    if (alignmentState.next_recommended_action) {
      lines.push(
        `alignment_next_action=${alignmentState.next_recommended_action.next_action}`,
      );
      lines.push(
        `alignment_next_route=${alignmentState.next_recommended_action.route}`,
      );
    }
  }

  return lines.join("\n");
}

function buildFollowOnPrompts({
  session,
  targetRepo,
  selectedProfile,
  workflowType,
  phasePlan,
  alignmentState,
}) {
  const contextSummary = buildPromptContextSummary(session, {
    targetRepo,
    selectedProfile,
    workflowType,
    alignmentState,
  });
  const phaseOne = phasePlan.phases[0];
  const phaseLines = phasePlan.phases.flatMap((phase) => [
    `- ${phase.phase_id}: ${phase.title}`,
    `  objective: ${phase.objective}`,
    ...phase.deliverables.map((item) => `  deliverable: ${item}`),
    `  focus: ${phase.execution_focus}`,
  ]);
  const alignmentLines = alignmentState
    ? [
        "Alignment summary:",
        `- overall_status: ${alignmentState.summary.overall_status}`,
        `- manual_required_count: ${alignmentState.summary.manual_required_count}`,
        `- missing_count: ${alignmentState.summary.missing_count}`,
        `- next_recommended_phase_id: ${alignmentState.next_recommended_phase_id}`,
        ...(alignmentState.next_recommended_action
          ? [
              `- next_recommended_action: ${alignmentState.next_recommended_action.next_action}`,
              `- next_recommended_route: ${alignmentState.next_recommended_action.route}`,
            ]
          : []),
        `- alignment_artifact: Harness/artifacts/control/discovery_sessions/${session.session_id}/alignment_state.md`,
      ]
    : [];

  return [
    {
      prompt_id: "bootstrap_hydration",
      title: "Bootstrap Hydration",
      summary:
        "Hydrate the deployed harness, fill placeholders, and align canonical docs before implementation begins.",
      prompt: [
        `You are onboarding Moradins Harness inside the repo "${targetRepo}".`,
        "This project is initially deploying the harness template. Start by inspecting the repo, then hydrate the deployed harness with grounded project truth.",
        "Fill remaining placeholders, update canonical docs under docs/, align the template to the project context, preserve deterministic checks, and keep the human-gate model intact.",
        "Treat the detected repo language, package-manager, CI, and deployment surfaces as constraints unless discovery artifacts explicitly justify a change.",
        "Do not remove the harness loop. Prefer minimal, methodical edits over broad redesigns.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        "Use these source artifacts if present:",
        `- ${session.artifacts?.product_spec ?? "docs/product_specs/discovery_<session>_project_spec.md"}`,
        `- ${session.artifacts?.design_doc ?? "docs/design_docs/discovery_<session>_architecture.md"}`,
        `- ${session.artifacts?.implementation_plan ?? "docs/exec_plans/implementation/active/plan_<session>_discovery_generated.md"}`,
        `- ${session.artifacts?.alignment_state_markdown ?? `Harness/artifacts/control/discovery_sessions/${session.session_id}/alignment_state.md`}`,
      ].join("\n"),
    },
    {
      prompt_id: "phase_planning",
      title: "Build Project Phases",
      summary:
        "Turn the discovery output into a project-specific phase plan with concrete deliverables and verification.",
      prompt: [
        `Create or update the project phase plan for "${targetRepo}".`,
        "Use the deployed harness, discovery output, and the draft phase structure below to produce a concrete implementation route.",
        "Write the plan in the repo's canonical docs/exec_plans and implementation phase surfaces, keeping the scope explicit and verification repo-native.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        "Draft phase structure:",
        ...phaseLines,
      ].join("\n"),
    },
    {
      prompt_id: "phase_1_execution",
      title: "Implement Phase 1",
      summary:
        "Focus only on the first phase so the repo is hydrated and scoped before broader implementation work starts.",
      prompt: [
        `Implement only ${phaseOne.phase_id} (${phaseOne.title}) for "${targetRepo}".`,
        "Do not jump ahead to later phases. Keep changes bounded to harness hydration, scope lock, and repo-readiness work.",
        "",
        "Phase objective:",
        phaseOne.objective,
        "",
        "Required deliverables:",
        ...phaseOne.deliverables.map((item) => `- ${item}`),
        "",
        "Execution focus:",
        phaseOne.execution_focus,
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
      ].join("\n"),
    },
    {
      prompt_id: "run_all_phases",
      title: "Run All Phases",
      summary:
        "Prepare a full multi-phase execution route while preserving human review and approval checkpoints.",
      prompt: [
        `Work through the planned phases for "${targetRepo}" in order.`,
        "Preserve human confirmation at phase boundaries. Do not assume unattended execution privileges.",
        "For each phase, state the scoped objective, required artifacts, verification commands, and the point where the operator should review before continuing.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        "Phase sequence:",
        ...phaseLines,
      ].join("\n"),
    },
  ];
}

function formatDiscoveryPhasePlanMarkdown({ targetRepo, phasePlan, selectedProfile }) {
  return [
    "# Discovery Phase Plan",
    "",
    `- target_repo: \`${targetRepo}\``,
    `- selected_profile: \`${selectedProfile || "unselected"}\``,
    "",
    phasePlan.summary,
    "",
    ...phasePlan.phases.flatMap((phase) => [
      `## ${phase.title}`,
      "",
      `- phase_id: \`${phase.phase_id}\``,
      `- objective: ${phase.objective}`,
      `- execution_focus: ${phase.execution_focus}`,
      "",
      "### Deliverables",
      "",
      ...phase.deliverables.map((item) => `- ${item}`),
      "",
    ]),
  ].join("\n");
}

function formatFollowOnPromptsMarkdown({ targetRepo, prompts }) {
  return [
    "# Discovery Follow-On Prompts",
    "",
    `- target_repo: \`${targetRepo}\``,
    "",
    ...prompts.flatMap((prompt) => [
      `## ${prompt.title}`,
      "",
      `- prompt_id: \`${prompt.prompt_id}\``,
      `- summary: ${prompt.summary}`,
      "",
      "```text",
      prompt.prompt,
      "```",
      "",
    ]),
  ].join("\n");
}

async function writeDiscoveryFollowOnPlanArtifacts({
  session,
  targetRepo,
  selectedProfile,
  phasePlan,
  alignmentState,
  prompts,
}) {
  const sessionRoot = `Harness/artifacts/control/discovery_sessions/${session.session_id}`;
  const artifactPaths = {
    bootstrap_prompt_markdown: `${sessionRoot}/bootstrap_prompt.md`,
    phase_plan_json: `${sessionRoot}/phase_plan.json`,
    phase_plan_markdown: `${sessionRoot}/phase_plan.md`,
    execution_prompts_json: `${sessionRoot}/execution_prompts.json`,
    execution_prompts_markdown: `${sessionRoot}/execution_prompts.md`,
    alignment_state_json: `${sessionRoot}/alignment_state.json`,
    alignment_state_markdown: `${sessionRoot}/alignment_state.md`,
  };
  await writeAlignmentStateArtifacts({ session, alignmentState });

  const bootstrapPrompt = prompts.find(
    (prompt) => prompt.prompt_id === "bootstrap_hydration",
  );
  await writeDiscoveryFile(
    session.session_id,
    "bootstrap_prompt.md",
    [
      "# Bootstrap Hydration Prompt",
      "",
      `- target_repo: \`${targetRepo}\``,
      `- selected_profile: \`${selectedProfile || "unselected"}\``,
      "",
      "```text",
      bootstrapPrompt?.prompt ?? "",
      "```",
    ].join("\n"),
  );
  await writeDiscoveryFile(
    session.session_id,
    "phase_plan.json",
    JSON.stringify(phasePlan, null, 2),
  );
  await writeDiscoveryFile(
    session.session_id,
    "phase_plan.md",
    formatDiscoveryPhasePlanMarkdown({
      targetRepo,
      phasePlan,
      selectedProfile,
    }),
  );
  await writeDiscoveryFile(
    session.session_id,
    "execution_prompts.json",
    JSON.stringify(
      {
        version: "DiscoveryFollowOnPromptsV1",
        target_repo: targetRepo,
        prompts,
      },
      null,
      2,
    ),
  );
  await writeDiscoveryFile(
    session.session_id,
    "execution_prompts.md",
    formatFollowOnPromptsMarkdown({ targetRepo, prompts }),
  );

  session.artifacts = {
    ...session.artifacts,
    bootstrap_prompt_markdown: artifactPaths.bootstrap_prompt_markdown,
    phase_plan_json: artifactPaths.phase_plan_json,
    phase_plan_markdown: artifactPaths.phase_plan_markdown,
    execution_prompts_json: artifactPaths.execution_prompts_json,
    execution_prompts_markdown: artifactPaths.execution_prompts_markdown,
    alignment_state_json: artifactPaths.alignment_state_json,
    alignment_state_markdown: artifactPaths.alignment_state_markdown,
  };
  await saveDiscoverySession(session);
  return artifactPaths;
}

function buildDiscoveryPromptTemplateId(workflowType, stage) {
  return workflowType === "existing_project"
    ? `existing_project_${stage}`
    : `new_project_${stage}`;
}

function buildPromptArtifactReferences(session) {
  return [
    String(session.project_scan_artifact_paths?.json ?? ""),
    String(session.project_scan_artifact_paths?.markdown ?? ""),
    String(session.artifacts?.synthesis_markdown ?? ""),
    String(session.artifacts?.product_spec ?? ""),
    String(session.artifacts?.design_doc ?? ""),
    String(session.artifacts?.implementation_plan ?? ""),
    String(session.artifacts?.template_fill_map_json ?? ""),
    String(session.artifacts?.template_fill_map_markdown ?? ""),
    String(session.artifacts?.alignment_state_json ?? ""),
    String(session.artifacts?.alignment_state_markdown ?? ""),
    String(session.approval?.approval_artifact_path ?? ""),
  ]
    .map((value) => value.trim())
    .filter(Boolean);
}

function assembleDiscoveryPromptBundle({
  session,
  stage,
  selectedProfile,
  promptContext,
}) {
  const provider = normalizeDiscoveryProviderId(session.provider);
  const model = normalizeDiscoveryModel({
    provider,
    requestedModel: session.model,
  });
  const selectedProfileSafe =
    String(selectedProfile ?? "").trim() ||
    String(session.synthesis?.recommended_profile ?? "").trim();
  const workflowType = String(promptContext?.workflow_type ?? "new_project");
  const promptTemplateId = buildDiscoveryPromptTemplateId(workflowType, stage);
  const artifactReferences = [
    `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_context_v1.json`,
    GENERATED_CONTEXT_PACK_RELATIVE_PATH,
    ...buildPromptArtifactReferences(session),
  ];

  const promptInputs = {
    prompt_context: promptContext?.session_context ?? {},
    included_context_sections: promptContext?.included_context_sections ?? [],
    context_pack: promptContext?.context_pack ?? {},
    selected_profile: selectedProfileSafe,
    stage,
  };

  const assembledPrompt = [
    `workflow_type: ${workflowType}`,
    `stage: ${stage}`,
    `stage_template: ${promptTemplateId}`,
    `provider: ${provider}`,
    `model: ${model}`,
    `selected_profile: ${selectedProfileSafe || "unselected"}`,
    "",
    "included_context_sections:",
    JSON.stringify(promptContext?.included_context_sections ?? [], null, 2),
    "",
    "context_pack:",
    JSON.stringify(promptContext?.context_pack ?? {}, null, 2),
    "",
    "session_context:",
    JSON.stringify(promptContext?.session_context ?? {}, null, 2),
    "",
    "artifact_references:",
    JSON.stringify(artifactReferences, null, 2),
    "",
    "source_citations:",
    JSON.stringify(promptContext?.source_citations ?? [], null, 2),
  ].join("\n");

  const generatedAt = new Date().toISOString();
  const hash = crypto
    .createHash("sha256")
    .update(`${DISCOVERY_PROMPT_SYSTEM_INSTRUCTIONS}\n${assembledPrompt}`)
    .digest("hex");
  return {
    version: "DiscoveryPromptBundleV1",
    session_id: session.session_id,
    provider,
    model,
    stage,
    selected_profile: selectedProfileSafe,
    workflow_type: workflowType,
    prompt_template_id: promptTemplateId,
    prompt_inputs: promptInputs,
    included_context_sections: promptContext?.included_context_sections ?? [],
    artifact_references: artifactReferences,
    source_citations: promptContext?.source_citations ?? [],
    prompt_context_artifact_path: `Harness/artifacts/control/discovery_sessions/${session.session_id}/prompt_context_v1.json`,
    context_pack_artifact_path: GENERATED_CONTEXT_PACK_RELATIVE_PATH,
    deterministic_system_instructions: DISCOVERY_PROMPT_SYSTEM_INSTRUCTIONS,
    assembled_prompt: assembledPrompt,
    generated_at: generatedAt,
    hash,
  };
}

function formatPromptBundleMarkdown(bundle) {
  return [
    "# Discovery Prompt Bundle",
    "",
    `- session_id: \`${bundle.session_id}\``,
    `- generated_at: \`${bundle.generated_at}\``,
    `- provider: \`${bundle.provider}\``,
    `- model: \`${bundle.model}\``,
    `- stage: \`${bundle.stage}\``,
    `- selected_profile: \`${bundle.selected_profile || "unselected"}\``,
    `- workflow_type: \`${bundle.workflow_type}\``,
    `- prompt_template_id: \`${bundle.prompt_template_id}\``,
    `- hash: \`${bundle.hash}\``,
    "",
    "## Included Context Sections",
    "",
    ...(bundle.included_context_sections ?? []).map((item) => `- ${item}`),
    "",
    "## Artifact References",
    "",
    ...((bundle.artifact_references ?? []).length > 0
      ? bundle.artifact_references.map((item) => `- ${item}`)
      : ["- none"]),
    "",
    "## Source Citations",
    "",
    ...((bundle.source_citations ?? []).length > 0
      ? bundle.source_citations.map((item) => `- ${item}`)
      : ["- none"]),
    "",
    "## Deterministic System Instructions",
    "",
    bundle.deterministic_system_instructions,
    "",
    "## Assembled Prompt",
    "",
    "```text",
    bundle.assembled_prompt,
    "```",
  ].join("\n");
}

function buildDiscoveryQuestionPrompt(bundle) {
  const workflowInstructions =
    bundle.workflow_type === "existing_project"
      ? [
          "Generate follow-up discovery questions for integrating the harness into an already-existing codebase.",
          "Prioritize repository gaps, CI/test posture, sidecar boundaries, and adoption blockers.",
        ]
      : [
          "Generate discovery questions for bootstrapping a new project from the harness template.",
          "Prioritize scope boundaries, default template fit, deployment target, and first-release constraints.",
        ];

  return [
    ...workflowInstructions,
    'Return a JSON object with key "questions" only.',
    "Limit the result to 8 concise, operator-facing questions.",
    "Return valid JSON only.",
    "",
    "Prompt bundle:",
    bundle.assembled_prompt,
  ].join("\n");
}

function buildDiscoverySynthesisPrompt(bundle) {
  const workflowInstructions =
    bundle.workflow_type === "existing_project"
      ? [
          "Generate synthesis for an established repository adopting the harness as a guarded sidecar.",
          "The output must explicitly account for existing CI/test gaps, sidecar boundaries, and operator approvals.",
        ]
      : [
          "Generate synthesis for a new project bootstrapping from the harness template.",
          "The output must explicitly account for template defaults, initial implementation phases, and launch readiness.",
        ];

  return [
    ...workflowInstructions,
    "Generate a JSON object with keys summary, recommended_profile, must_haves, open_questions, product_spec, design, and plan.",
    "Return valid JSON only.",
    "",
    "Prompt bundle:",
    bundle.assembled_prompt,
  ].join("\n");
}

async function ensureApprovalArtifact(sessionId) {
  const approvalPath = path.join(
    discoveryRoot,
    sessionId,
    "approval_required.md",
  );
  if (await pathExists(approvalPath)) {
    return;
  }

  const content = [
    "# Discovery Human Approval",
    "",
    `- session_id: \`${sessionId}\``,
    "- approval_status: pending",
    "- approved_by: ",
    "- approved_at: ",
    "",
    "## Decision",
    "",
    "- [ ] Approved for execution scope",
    "- [ ] Rejected for rework",
    "",
  ].join("\n");

  await fs.writeFile(approvalPath, `${content}\n`, "utf8");
}

async function isDiscoveryApprovalGranted(sessionId) {
  const approvalPath = path.join(
    discoveryRoot,
    sessionId,
    "approval_required.md",
  );
  if (!(await pathExists(approvalPath))) {
    return false;
  }

  const content = await fs.readFile(approvalPath, "utf8");
  const approvedChecked = content.includes(
    "- [x] Approved for execution scope",
  );
  const rejectedChecked = content.includes("- [x] Rejected for rework");
  return approvedChecked && !rejectedChecked;
}

async function generateDiscoveryQuestions(session) {
  const promptContext = await buildPromptContextForSession({
    session,
    stage: "questions",
    selectedProfile: "",
  });
  const bundle = assembleDiscoveryPromptBundle({
    session,
    stage: "questions",
    selectedProfile: "",
    promptContext,
  });
  const prompt = buildDiscoveryQuestionPrompt(bundle);
  const modelResult = await runDiscoveryLlmJson({
    session,
    prompt,
    systemInstructions: bundle.deterministic_system_instructions,
  });

  if (isRecord(modelResult) && Array.isArray(modelResult.questions)) {
    const normalized = modelResult.questions
      .map((row, index) => normalizeQuestion(row, index))
      .filter((row) => row.prompt.length > 0)
      .slice(0, 14);
    if (normalized.length > 0) {
      return normalized;
    }
  }

  const baseQuestions = [
    {
      question_id: "q_01_success_metric",
      prompt:
        "What concrete success metric must be achieved in the first 90 days?",
      rationale:
        "Defines measurable outcome for commissioning and quality scoring.",
      required: true,
    },
    {
      question_id: "q_02_user_workflow",
      prompt:
        "What is the highest-value user workflow and what are its critical path steps?",
      rationale: "Anchors architecture and MVP sequencing to user value.",
      required: true,
    },
    {
      question_id: "q_03_constraints",
      prompt:
        "Which hard constraints (budget, compliance, infra, timeline) cannot be violated?",
      rationale: "Prevents non-viable design choices.",
      required: true,
    },
    {
      question_id: "q_04_integrations",
      prompt: "What external integrations are mandatory for launch?",
      rationale: "Determines interface contracts and dependency risk.",
      required: true,
    },
    {
      question_id: "q_05_risk",
      prompt: "Which top risks would block launch if unresolved?",
      rationale: "Feeds risk-based blocking and tech debt routing.",
      required: true,
    },
    {
      question_id: "q_06_operations",
      prompt:
        "What operations model is expected for observability, on-call, and incident handling?",
      rationale: "Sets reliability and support readiness requirements.",
      required: false,
    },
  ];

  if (session.intake.input_mode === "prompt") {
    return [
      {
        question_id: "q_00_prompt_scope",
        prompt:
          "What exact scope boundary should be enforced for the supplied project prompt?",
        rationale:
          "Converts free-form prompt intake into deterministic in-scope and out-of-scope boundaries.",
        required: true,
      },
      ...baseQuestions,
    ];
  }

  return baseQuestions;
}

function hasDiscoveryAnswerContent(answers) {
  return Object.values(answers ?? {}).some(
    (value) => String(value ?? "").trim().length > 0,
  );
}

function buildAdaptiveFollowupQuestions(session) {
  const missingRequired = (session.questions ?? []).filter((question) => {
    if (!question.required) {
      return false;
    }
    return (
      String(session.answers?.[question.question_id] ?? "").trim().length === 0
    );
  });

  const questions = missingRequired.slice(0, 3).map((question, index) => ({
    question_id: `q_followup_required_${String(index + 1).padStart(2, "0")}`,
    prompt: `Follow-up required: provide explicit detail for "${question.prompt}" so synthesis can proceed without assumptions.`,
    rationale:
      "Required fields were left blank and would reduce synthesis quality.",
    required: true,
  }));

  const scanGaps = Array.isArray(session?.project_scan_summary?.critical_gaps)
    ? session.project_scan_summary.critical_gaps.filter(
        (value) => String(value ?? "").trim().length > 0,
      )
    : [];
  if (scanGaps.length > 0) {
    questions.push({
      question_id: "q_followup_scan_gap_01",
      prompt: `Project scan found critical gaps: ${scanGaps.slice(0, 2).join(" ")} What exact remediation sequence should be enforced first?`,
      rationale:
        "Converts detected baseline risk into an explicit remediation plan.",
      required: true,
    });
  }

  return questions;
}

async function generateDiscoverySynthesis(session) {
  const promptContext = await buildPromptContextForSession({
    session,
    stage: "synthesis",
    selectedProfile: session.synthesis?.recommended_profile ?? "",
  });
  const bundle = assembleDiscoveryPromptBundle({
    session,
    stage: "synthesis",
    selectedProfile: session.synthesis?.recommended_profile ?? "",
    promptContext,
  });
  const prompt = buildDiscoverySynthesisPrompt(bundle);

  const modelResult = await runDiscoveryLlmJson({
    session,
    prompt,
    systemInstructions: bundle.deterministic_system_instructions,
  });
  if (isRecord(modelResult)) {
    const normalized = normalizeSynthesis(modelResult);
    if (normalized.summary.length > 0) {
      return normalized;
    }
  }

  return deterministicSynthesis(session);
}

function deterministicSynthesis(session) {
  const intake = session.intake;
  const answeredPairs = Object.entries(session.answers).filter(
    ([, value]) => String(value).trim().length > 0,
  );
  const intentSeed =
    intake.project_goal || intake.project_prompt || "new project";
  const scanCriticalGaps = Array.isArray(
    session?.project_scan_summary?.critical_gaps,
  )
    ? session.project_scan_summary.critical_gaps.filter(
        (value) => String(value ?? "").trim().length > 0,
      )
    : [];

  return {
    summary: `Discovery synthesis for ${intentSeed}. Intake, baseline scan context, and ${answeredPairs.length} answered prompts converted into initial harness planning artifacts.`,
    recommended_profile: recommendProfile(intake),
    must_haves: [
      "Define approved MVP boundary and stop conditions.",
      "Establish canonical contract artifacts under Harness/artifacts/control.",
      "Route implementation work into docs/exec_plans/implementation/active with human gate enforcement.",
      ...(scanCriticalGaps.length > 0
        ? ["Resolve critical project-scan gaps before phase execution."]
        : []),
    ],
    open_questions:
      answeredPairs.length < 3
        ? [
            "Insufficient discovery answers. Add more detail before implementation kickoff.",
            ...scanCriticalGaps.slice(0, 2),
          ]
        : [],
    product_spec: {
      intent: intentSeed || "Define project goal during intake.",
      target_users: splitCsv(intake.users),
      constraints: [
        ...splitCsv(intake.constraints),
        ...(intake.timeline ? [`timeline: ${intake.timeline}`] : []),
        ...(intake.compliance ? [`compliance: ${intake.compliance}`] : []),
        ...(intake.deployment_target
          ? [`deployment_target: ${intake.deployment_target}`]
          : []),
        ...(intake.other_context
          ? [`other_context: ${intake.other_context}`]
          : []),
      ],
      milestones: [
        "Discovery approval and scope lock",
        "MVP implementation plan approval",
        "Validation and release readiness review",
      ],
    },
    design: {
      components: [
        "Project-facing API/service boundary",
        "Persistence and observability surface",
        "Harness governance and cycle execution artifacts",
      ],
      data_flows: [
        "User request -> service boundary -> persistence",
        "Execution events -> observability -> governance reports",
      ],
      risks: [
        "Scope creep without approval gate enforcement",
        "Contract drift between generated plans and implementation",
      ],
    },
    plan: {
      workstreams: [
        "Commissioning and contract setup",
        "Core implementation and integration",
        "Validation, governance, and stabilization",
      ],
      initial_backlog: [
        "Create implementation active plan from approved discovery output",
        "Define service contracts and schema artifacts",
        "Establish QA gates for target deployment profile",
      ],
    },
  };
}

function recommendProfile(intake) {
  const goal =
    `${intake.project_goal || ""} ${intake.project_prompt || ""} ${intake.integrations || ""}`.toLowerCase();
  if (
    goal.includes("pipeline") ||
    goal.includes("etl") ||
    goal.includes("batch")
  ) {
    return "data_pipeline";
  }
  if (goal.includes("agent") || goal.includes("assistant")) {
    return "agent_platform";
  }
  if (
    goal.includes("internal") ||
    goal.includes("ops") ||
    goal.includes("admin")
  ) {
    return "internal_tooling";
  }
  return "web_app";
}

function normalizeSynthesis(raw) {
  return {
    summary: String(raw.summary ?? "").trim(),
    recommended_profile:
      String(raw.recommended_profile ?? "web_app").trim() || "web_app",
    must_haves: normalizeStringArray(raw.must_haves),
    open_questions: normalizeStringArray(raw.open_questions),
    product_spec: {
      intent: String(raw.product_spec?.intent ?? "").trim(),
      target_users: normalizeStringArray(raw.product_spec?.target_users),
      constraints: normalizeStringArray(raw.product_spec?.constraints),
      milestones: normalizeStringArray(raw.product_spec?.milestones),
    },
    design: {
      components: normalizeStringArray(raw.design?.components),
      data_flows: normalizeStringArray(raw.design?.data_flows),
      risks: normalizeStringArray(raw.design?.risks),
    },
    plan: {
      workstreams: normalizeStringArray(raw.plan?.workstreams),
      initial_backlog: normalizeStringArray(raw.plan?.initial_backlog),
    },
  };
}

async function runDiscoveryLlmJson({ session, prompt, systemInstructions }) {
  const provider = normalizeDiscoveryProviderId(session?.provider);
  const model = normalizeDiscoveryModel({
    provider,
    requestedModel: session?.model,
  });

  if (provider === "none") {
    return null;
  }

  const availability = await detectProviderAvailability(provider);
  if (!availability.available) {
    return null;
  }

  if (provider === "openai") {
    return runOpenAiDiscoveryJson({
      prompt,
      model,
      systemInstructions,
      promptCache: buildPromptCacheHint({
        provider,
        sessionId: session?.session_id,
        model,
      }),
    });
  }

  if (provider === "codex_cli" || provider === "claude_code") {
    return runCliDiscoveryJson({
      provider,
      prompt,
      model,
      systemInstructions,
    });
  }

  return null;
}

function normalizeDiscoveryProviderId(rawProvider) {
  const normalized = String(rawProvider ?? "")
    .trim()
    .toLowerCase();
  if (normalized && DISCOVERY_PROVIDER_SPECS[normalized]) {
    return normalized;
  }
  if (DISCOVERY_PROVIDER_SPECS[discoveryProviderDefault]) {
    return discoveryProviderDefault;
  }
  return "none";
}

function normalizeDiscoveryModel({ provider, requestedModel }) {
  const requested = String(requestedModel ?? "").trim();
  if (requested) {
    return requested;
  }
  if (provider === "openai") {
    return (
      String(
        process.env.OPENAI_MODEL ??
          DISCOVERY_PROVIDER_SPECS.openai.default_model,
      ).trim() || "gpt-5-mini"
    );
  }
  return (
    DISCOVERY_PROVIDER_SPECS[provider]?.default_model ?? "deterministic-v1"
  );
}

async function detectProviderAvailability(provider) {
  if (provider === "none") {
    return { available: true, detail: "deterministic fallback" };
  }

  if (provider === "openai") {
    const apiKey = String(process.env.OPENAI_API_KEY ?? "").trim();
    if (!apiKey) {
      return { available: false, detail: "OPENAI_API_KEY is not configured." };
    }
    return { available: true, detail: "OPENAI_API_KEY configured." };
  }

  if (provider === "codex_cli") {
    const command =
      String(process.env.CODEX_CLI_COMMAND ?? "codex").trim() || "codex";
    if (!commandExists(command)) {
      return { available: false, detail: `${command} command not found.` };
    }
    return { available: true, detail: `${command} command detected.` };
  }

  if (provider === "claude_code") {
    const command =
      String(process.env.CLAUDE_CODE_COMMAND ?? "claude").trim() || "claude";
    if (!commandExists(command)) {
      return { available: false, detail: `${command} command not found.` };
    }
    return { available: true, detail: `${command} command detected.` };
  }

  return { available: false, detail: "Unsupported provider." };
}

function commandExists(command) {
  try {
    execFileSync("which", [command], {
      stdio: "ignore",
      env: process.env,
    });
    return true;
  } catch {
    return false;
  }
}

function buildPromptCacheHint({ provider, sessionId, model }) {
  if (provider !== "openai") {
    return null;
  }
  const enabled =
    String(process.env.OPENAI_PROMPT_CACHE_ENABLED ?? "true")
      .trim()
      .toLowerCase() !== "false";
  if (!enabled) {
    return null;
  }
  const retention =
    String(process.env.OPENAI_PROMPT_CACHE_RETENTION ?? "24h").trim() || "24h";
  const cacheSessionId = String(sessionId ?? "").trim() || "discovery";
  return {
    prompt_cache_key: `moradins-harness:${cacheSessionId}:${model}`,
    prompt_cache_retention: retention,
  };
}

async function runOpenAiDiscoveryJson({
  prompt,
  model,
  systemInstructions,
  promptCache,
}) {
  const apiKey = String(process.env.OPENAI_API_KEY ?? "").trim();
  if (!apiKey) {
    return null;
  }

  try {
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        ...(promptCache ?? {}),
        input: [
          {
            role: "system",
            content: [
              {
                type: "input_text",
                text:
                  systemInstructions ||
                  "You are a strict JSON generator for harness discovery. Return valid JSON only.",
              },
            ],
          },
          {
            role: "user",
            content: [{ type: "input_text", text: prompt }],
          },
        ],
      }),
    });

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    const outputText = String(payload?.output_text ?? "").trim();
    if (!outputText) {
      return null;
    }

    return parseJsonObject(outputText);
  } catch {
    return null;
  }
}

function runCliDiscoveryJson({ provider, prompt, model, systemInstructions }) {
  const isCodex = provider === "codex_cli";
  const command = isCodex
    ? String(process.env.CODEX_CLI_COMMAND ?? "codex").trim() || "codex"
    : String(process.env.CLAUDE_CODE_COMMAND ?? "claude").trim() || "claude";
  const argsRaw = isCodex
    ? String(process.env.CODEX_CLI_ARGS ?? "").trim()
    : String(process.env.CLAUDE_CODE_ARGS ?? "").trim();
  const defaultArgs = isCodex ? ["--json"] : ["--print", "--format", "json"];
  const args = argsRaw ? splitShellLikeArgs(argsRaw) : defaultArgs;

  const composedPrompt = [`model: ${model}`, systemInstructions, "", prompt]
    .filter(Boolean)
    .join("\n");

  const usesPromptPlaceholder = args.some((arg) => arg.includes("{{prompt}}"));
  const preparedArgs = args.map((arg) =>
    arg.replaceAll("{{prompt}}", composedPrompt),
  );

  try {
    const output = execFileSync(command, preparedArgs, {
      encoding: "utf8",
      env: process.env,
      input: usesPromptPlaceholder ? undefined : composedPrompt,
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 30_000,
      maxBuffer: 5 * 1024 * 1024,
    }).trim();
    if (!output) {
      return null;
    }
    return parseJsonObject(output);
  } catch {
    return null;
  }
}

function splitShellLikeArgs(rawArgs) {
  return rawArgs
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function normalizeAssistantId(rawAssistant) {
  const normalized = String(rawAssistant ?? "")
    .trim()
    .toLowerCase();
  if (normalized === "codex_cli" || normalized === "claude_code") {
    return normalized;
  }
  throw new ApiError(
    400,
    "invalid_assistant_id",
    "assistant must be one of: codex_cli, claude_code.",
  );
}

function normalizeAssistantSourceMode(rawSourceMode) {
  const normalized = String(rawSourceMode ?? "")
    .trim()
    .toLowerCase();
  if (["builder", "review", "project_status", "docs"].includes(normalized)) {
    return normalized;
  }
  throw new ApiError(
    400,
    "invalid_assistant_source_mode",
    "source_mode must be one of: builder, review, project_status, docs.",
  );
}

function normalizeAssistantExecutionScope(rawExecutionScope) {
  const normalized = String(rawExecutionScope ?? "")
    .trim()
    .toLowerCase();
  if (!normalized || normalized === "manager_repo") {
    return "manager_repo";
  }
  if (normalized === "local_repo") {
    return "local_repo";
  }
  throw new ApiError(
    400,
    "invalid_assistant_execution_scope",
    "execution_scope must be one of: manager_repo, local_repo.",
  );
}

function buildAssistantCommandSpec(assistant) {
  if (assistant === "codex_cli") {
    return {
      command:
        String(process.env.CODEX_CLI_COMMAND ?? "codex").trim() || "codex",
      argsRaw: String(process.env.CODEX_CLI_ARGS ?? "").trim(),
      defaultArgs: [
        "exec",
        "--color",
        "never",
        "--sandbox",
        "read-only",
      ],
    };
  }

  return {
    command:
      String(process.env.CLAUDE_CODE_COMMAND ?? "claude").trim() || "claude",
    argsRaw: String(process.env.CLAUDE_CODE_ARGS ?? "").trim(),
    defaultArgs: ["--print"],
  };
}

async function resolveAssistantExecutionContext({
  executionScope,
  targetRepo,
}) {
  if (executionScope === "manager_repo") {
    return {
      scope: "manager_repo",
      targetLabel: "Moradins Harness",
      workingDirectory: repoRoot,
      workingDirectoryDisplay: disclosePath(repoRoot),
    };
  }

  const normalizedTargetRepo = String(targetRepo ?? "").trim();
  if (!normalizedTargetRepo) {
    throw new ApiError(
      400,
      "assistant_target_repo_required",
      "target_repo is required when execution_scope=local_repo.",
    );
  }

  const workingDirectory = await resolveDestinationPath(normalizedTargetRepo);
  const stats = await fs.lstat(workingDirectory).catch(() => null);
  if (!stats) {
    throw new ApiError(
      404,
      "assistant_target_repo_missing",
      "target_repo must resolve to an existing local directory for assistant execution.",
    );
  }
  if (!stats.isDirectory()) {
    throw new ApiError(
      400,
      "assistant_target_repo_not_directory",
      "target_repo must resolve to a local directory for assistant execution.",
    );
  }

  return {
    scope: "local_repo",
    targetLabel: normalizedTargetRepo,
    workingDirectory,
    workingDirectoryDisplay: disclosePath(workingDirectory),
  };
}

function buildAssistantTerminalCommand({
  assistant,
  command,
  argsRaw,
  defaultArgs,
}) {
  const args = argsRaw ? splitShellLikeArgs(argsRaw) : defaultArgs;
  const printableArgs = args
    .map((value) => value.replaceAll("{{prompt}}", "<paste prompt here>"))
    .join(" ")
    .trim();
  if (args.some((value) => value.includes("{{prompt}}"))) {
    return `${command}${printableArgs ? ` ${printableArgs}` : ""}`;
  }
  return `printf '%s\\n' '<paste prompt here>' | ${command}${printableArgs ? ` ${printableArgs}` : ""}`;
}

function normalizeAssistantRunRecord(value) {
  if (!isRecord(value)) {
    return null;
  }

  const runId = String(value.run_id ?? "").trim();
  if (!runId) {
    return null;
  }

  const status = ["queued", "running", "pass", "fail"].includes(
    String(value.status ?? ""),
  )
    ? String(value.status)
    : "fail";
  const stage = [
    "queued",
    "launching_cli",
    "running_cli",
    "writing_artifacts",
    "completed",
    "failed",
  ].includes(String(value.stage ?? ""))
    ? String(value.stage)
    : status === "pass"
      ? "completed"
      : status === "fail"
        ? "failed"
        : "running_cli";
  const artifactPaths = isRecord(value.artifact_paths)
    ? {
        json: String(value.artifact_paths.json ?? ""),
        markdown: String(value.artifact_paths.markdown ?? ""),
      }
    : { json: "", markdown: "" };
  let assistant = null;
  let sourceMode = null;
  try {
    assistant = normalizeAssistantId(value.assistant);
    sourceMode = normalizeAssistantSourceMode(value.source_mode);
  } catch {
    return null;
  }
  const rawExitCode = value.exit_code;
  const exitCode =
    rawExitCode === null || rawExitCode === undefined || rawExitCode === ""
      ? null
      : Number.isFinite(Number(rawExitCode))
        ? Number(rawExitCode)
        : null;

  return {
    version: "AssistantRunResponseV1",
    run_id: runId,
    assistant,
    source_mode: sourceMode,
    session_id: String(value.session_id ?? "").trim(),
    target_repo: String(value.target_repo ?? "").trim(),
    execution_scope: normalizeAssistantExecutionScope(value.execution_scope),
    execution_context:
      isRecord(value.execution_context) &&
      (value.execution_context.scope === "manager_repo" ||
        value.execution_context.scope === "local_repo")
        ? {
            scope: value.execution_context.scope,
            target_label: String(
              value.execution_context.target_label ?? "",
            ).trim(),
            working_directory: String(
              value.execution_context.working_directory ?? "",
            ).trim(),
          }
        : undefined,
    status,
    stage,
    prompt: String(value.prompt ?? ""),
    prompt_preview:
      String(value.prompt_preview ?? "").trim() ||
      summarizePrompt(String(value.prompt ?? "")),
    stdout: String(value.stdout ?? ""),
    stderr: String(value.stderr ?? ""),
    stdout_tail:
      String(value.stdout_tail ?? "").trim() ||
      tailText(String(value.stdout ?? ""), ASSISTANT_OUTPUT_TAIL_LIMIT),
    stderr_tail:
      String(value.stderr_tail ?? "").trim() ||
      tailText(String(value.stderr ?? ""), ASSISTANT_OUTPUT_TAIL_LIMIT),
    started_at: String(value.started_at ?? ""),
    updated_at: String(value.updated_at ?? ""),
    finished_at: String(value.finished_at ?? "").trim(),
    detail: String(value.detail ?? "").trim(),
    duration_ms: Number.isFinite(Number(value.duration_ms))
      ? Number(value.duration_ms)
      : undefined,
    exit_code: exitCode,
    terminal_command: String(value.terminal_command ?? "").trim(),
    needs_operator_input: Boolean(value.needs_operator_input),
    artifact_paths: artifactPaths,
  };
}

function summarizePrompt(prompt) {
  const compact = String(prompt ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (compact.length <= 180) {
    return compact;
  }
  return `${compact.slice(0, 177)}...`;
}

function detectAssistantNeedsOperatorInput({ status, stdout, stderr }) {
  if (status !== "pass") {
    return false;
  }
  const combined = `${String(stdout ?? "")}\n${String(stderr ?? "")}`.trim();
  if (!combined) {
    return false;
  }
  const normalized = combined.toLowerCase();
  if (
    /(^|\n)\s*(question|questions|clarification|clarifications)\s*:/u.test(
      normalized,
    )
  ) {
    return true;
  }
  if (
    /\b(can you|could you|please provide|which option|which one|what should|what is|do you want|would you like|should i)\b/u.test(
      normalized,
    )
  ) {
    return true;
  }
  const lines = combined
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.some((line) => line.endsWith("?"));
}

function tailText(value, maxLength) {
  const normalized = String(value ?? "");
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return normalized.slice(-maxLength);
}

function appendWithLimit(currentValue, chunk, maxLength) {
  const combined = `${String(currentValue ?? "")}${String(chunk ?? "")}`;
  if (combined.length <= maxLength) {
    return combined;
  }
  return combined.slice(0, maxLength);
}

function finalizeAssistantOutput(fullText, tailValue) {
  const normalizedFullText = String(fullText ?? "");
  const preservedTail =
    String(tailValue ?? "") ||
    tailText(normalizedFullText, ASSISTANT_OUTPUT_TAIL_LIMIT);
  return {
    text: discloseText(normalizedFullText),
    tail: tailText(discloseText(preservedTail), ASSISTANT_OUTPUT_TAIL_LIMIT),
  };
}

function buildAssistantRunMarkdown(record) {
  return [
    "# Assistant Run",
    "",
    `- run_id: \`${record.run_id}\``,
    `- assistant: \`${record.assistant}\``,
    `- source_mode: \`${record.source_mode}\``,
    `- execution_scope: \`${record.execution_scope}\``,
    `- status: \`${record.status}\``,
    `- stage: \`${record.stage}\``,
    `- exit_code: \`${record.exit_code === null ? "pending" : record.exit_code}\``,
    `- started_at: \`${record.started_at}\``,
    `- updated_at: \`${record.updated_at}\``,
    ...(record.finished_at ? [`- finished_at: \`${record.finished_at}\``] : []),
    ...(record.session_id ? [`- session_id: \`${record.session_id}\``] : []),
    ...(record.target_repo ? [`- target_repo: \`${record.target_repo}\``] : []),
    ...(record.execution_context
      ? [
          `- execution_target: \`${record.execution_context.target_label}\``,
          `- working_directory: \`${record.execution_context.working_directory}\``,
        ]
      : []),
    ...(record.detail ? [`- detail: ${record.detail}`] : []),
    "",
    "## Prompt",
    "",
    "```text",
    record.prompt,
    "```",
    "",
    "## Stdout Tail",
    "",
    "```text",
    record.stdout_tail || "",
    "```",
    "",
    "## Stderr Tail",
    "",
    "```text",
    record.stderr_tail || "",
    "```",
    "",
    "## Observation",
    "",
    `Full run artifact path: \`${record.artifact_paths.json}\``,
  ].join("\n");
}

async function persistAssistantRunRecord(record) {
  activeAssistantRuns.set(record.run_id, record);
  await fs.writeFile(
    path.join(assistantRunsRoot, `${record.run_id}.json`),
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(
    path.join(assistantRunsRoot, `${record.run_id}.md`),
    `${buildAssistantRunMarkdown(record)}\n`,
    "utf8",
  );
}

function summarizeAssistantRun(record) {
  return {
    version: "AssistantRunSummaryV1",
    run_id: record.run_id,
    assistant: record.assistant,
    source_mode: record.source_mode,
    target_repo: record.target_repo,
    execution_scope: record.execution_scope,
    execution_context: record.execution_context,
    status: record.status,
    stage: record.stage,
    started_at: record.started_at,
    updated_at: record.updated_at,
    finished_at: record.finished_at,
    detail: record.detail,
    duration_ms: record.duration_ms,
    exit_code: record.exit_code,
    needs_operator_input: Boolean(record.needs_operator_input),
    artifact_paths: record.artifact_paths,
  };
}

async function loadAssistantRunRecord(runId) {
  if (activeAssistantRuns.has(runId)) {
    return activeAssistantRuns.get(runId);
  }
  const record = normalizeAssistantRunRecord(
    await safeReadJson(path.join(assistantRunsRoot, `${runId}.json`), null),
  );
  if (!record) {
    return null;
  }
  if (record.status === "queued" || record.status === "running") {
    activeAssistantRuns.set(runId, record);
  }
  return record;
}

async function buildAssistantRunListResponse(limit = 8) {
  const entries = await fs.readdir(assistantRunsRoot, { withFileTypes: true });
  const jsonFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => entry.name)
    .sort()
    .reverse();

  const runs = [];
  for (const fileName of jsonFiles) {
    if (runs.length >= limit) {
      break;
    }
    const runId = fileName.replace(/\.json$/u, "");
    const record = await loadAssistantRunRecord(runId);
    if (!record) {
      continue;
    }
    runs.push(summarizeAssistantRun(record));
  }

  const activeRun = runs.find(
    (run) => run.status === "queued" || run.status === "running",
  );
  return {
    version: "AssistantRunListResponseV1",
    generated_at: new Date().toISOString(),
    active_run_id: activeRun?.run_id ?? "",
    runs,
  };
}

function updateAssistantRun(record, patch) {
  const nextRecord = {
    ...record,
    ...patch,
    updated_at: new Date().toISOString(),
  };
  if (nextRecord.started_at && nextRecord.finished_at) {
    nextRecord.duration_ms = Math.max(
      0,
      new Date(nextRecord.finished_at).getTime() -
        new Date(nextRecord.started_at).getTime(),
    );
  }
  return nextRecord;
}

async function startAssistantRun(payload) {
  const assistant = normalizeAssistantId(payload?.assistant);
  const sourceMode = normalizeAssistantSourceMode(payload?.source_mode);
  const executionScope = normalizeAssistantExecutionScope(
    payload?.execution_scope,
  );
  const prompt = String(payload?.prompt ?? "").trim();
  if (!prompt) {
    throw new ApiError(400, "invalid_assistant_prompt", "prompt is required.");
  }

  const { command, argsRaw, defaultArgs } =
    buildAssistantCommandSpec(assistant);
  if (!commandExists(command)) {
    throw new ApiError(
      500,
      "assistant_command_missing",
      `${command} command is not available on this host.`,
    );
  }

  const args = argsRaw ? splitShellLikeArgs(argsRaw) : defaultArgs;
  const usesPromptPlaceholder = args.some((arg) => arg.includes("{{prompt}}"));
  const preparedArgs = args.map((arg) => arg.replaceAll("{{prompt}}", prompt));
  const sessionId = String(payload?.session_id ?? "").trim();
  const targetRepo = String(payload?.target_repo ?? "").trim();
  const executionContext = await resolveAssistantExecutionContext({
    executionScope,
    targetRepo,
  });
  const runId = `assistant_${new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-")}_${assistant}_${sourceMode}`;
  const jsonAbsolutePath = path.join(assistantRunsRoot, `${runId}.json`);
  const jsonRelativePath = `${ASSISTANT_RUNS_RELATIVE_ROOT}/${runId}.json`;
  const markdownRelativePath = `${ASSISTANT_RUNS_RELATIVE_ROOT}/${runId}.md`;
  const terminalCommand = buildAssistantTerminalCommand({
    assistant,
    command,
    argsRaw,
    defaultArgs,
  });
  const startedAt = new Date().toISOString();
  let record = {
    version: "AssistantRunResponseV1",
    run_id: runId,
    assistant,
    source_mode: sourceMode,
    session_id: sessionId,
    target_repo: targetRepo,
    execution_scope: executionScope,
    execution_context: {
      scope: executionContext.scope,
      target_label: executionContext.targetLabel,
      working_directory: executionContext.workingDirectoryDisplay,
    },
    status: "queued",
    stage: "queued",
    prompt,
    prompt_preview: summarizePrompt(prompt),
    stdout: "",
    stderr: "",
    stdout_tail: "",
    stderr_tail: "",
    started_at: startedAt,
    updated_at: startedAt,
    finished_at: "",
    detail: "Queued and preparing assistant process.",
    duration_ms: undefined,
    exit_code: null,
    terminal_command: terminalCommand,
    needs_operator_input: false,
    artifact_paths: {
      json: jsonRelativePath,
      markdown: markdownRelativePath,
    },
  };
  await persistAssistantRunRecord(record);

  let completed = false;
  let timedOut = false;
  const assistantEnv = {
    ...process.env,
    MORADINS_HARNESS_EXECUTION_SCOPE: executionScope,
    MORADINS_HARNESS_ACTIVE_REPO_LABEL: executionContext.targetLabel,
    MORADINS_HARNESS_ACTIVE_REPO_ROOT: executionContext.workingDirectory,
    GIT_CEILING_DIRECTORIES: path.dirname(executionContext.workingDirectory),
  };
  const child = spawn(command, preparedArgs, {
    cwd: executionContext.workingDirectory,
    env: assistantEnv,
    stdio: ["pipe", "pipe", "pipe"],
  });
  activeAssistantChildren.add(child);

  async function finalizeRun({ status, stage, exitCode, detail }) {
    if (completed) {
      return;
    }
    completed = true;
    const finishedAt = new Date().toISOString();
    const rawStdout = record.stdout;
    const rawStderr = record.stderr;
    const finalizedStdout = finalizeAssistantOutput(
      rawStdout,
      record.stdout_tail,
    );
    const finalizedStderr = finalizeAssistantOutput(
      rawStderr,
      record.stderr_tail,
    );
    record = updateAssistantRun(record, {
      status,
      stage,
      exit_code: exitCode,
      detail,
      finished_at: finishedAt,
      stdout: finalizedStdout.text,
      stderr: finalizedStderr.text,
      stdout_tail: finalizedStdout.tail,
      stderr_tail: finalizedStderr.tail,
      needs_operator_input: detectAssistantNeedsOperatorInput({
        status,
        stdout: rawStdout,
        stderr: rawStderr,
      }),
    });
    await persistAssistantRunRecord(record);
    await recordBuilderAudit({
      action: "assistant-run",
      status,
      destinationPath: jsonRelativePath,
      targetRepo,
      detail: `assistant=${assistant}; source_mode=${sourceMode}; exit_code=${exitCode ?? "pending"}`,
    });
    activeAssistantChildren.delete(child);
    activeAssistantRuns.set(runId, record);
  }

  child.on("spawn", () => {
    record = updateAssistantRun(record, {
      status: "running",
      stage: "launching_cli",
      detail: `Launching ${command}.`,
    });
    void persistAssistantRunRecord(record);
  });

  child.stdout.on("data", (chunk) => {
    const text = String(chunk ?? "");
    record = updateAssistantRun(record, {
      status: "running",
      stage: "running_cli",
      detail: `${assistant === "claude_code" ? "Claude Code CLI" : "Codex CLI"} is producing output.`,
      stdout: appendWithLimit(
        record.stdout,
        text,
        ASSISTANT_OUTPUT_CAPTURE_LIMIT,
      ),
      stdout_tail: tailText(
        `${record.stdout_tail ?? ""}${text}`,
        ASSISTANT_OUTPUT_TAIL_LIMIT,
      ),
    });
    void persistAssistantRunRecord(record);
  });

  child.stderr.on("data", (chunk) => {
    const text = String(chunk ?? "");
    record = updateAssistantRun(record, {
      status: "running",
      stage: "running_cli",
      detail: `${assistant === "claude_code" ? "Claude Code CLI" : "Codex CLI"} emitted stderr.`,
      stderr: appendWithLimit(
        record.stderr,
        text,
        ASSISTANT_OUTPUT_CAPTURE_LIMIT,
      ),
      stderr_tail: tailText(
        `${record.stderr_tail ?? ""}${text}`,
        ASSISTANT_OUTPUT_TAIL_LIMIT,
      ),
    });
    void persistAssistantRunRecord(record);
  });

  child.on("error", (error) => {
    void finalizeRun({
      status: "fail",
      stage: "failed",
      exitCode: 1,
      detail: `Assistant process failed to start: ${String(error?.message ?? error)}`,
    });
  });

  const timeout = setTimeout(() => {
    timedOut = true;
    record = updateAssistantRun(record, {
      status: "running",
      stage: "running_cli",
      detail: `Assistant run exceeded ${Math.round(assistantRunTimeoutMs / 1000)} seconds and is being terminated.`,
    });
    void persistAssistantRunRecord(record);
    try {
      child.kill("SIGTERM");
    } catch {
      // Ignore if already exited.
    }
  }, assistantRunTimeoutMs);

  child.on("close", (code, signal) => {
    clearTimeout(timeout);
    const exitCode = Number.isFinite(Number(code))
      ? Number(code)
      : timedOut
        ? 124
        : 1;
    record = updateAssistantRun(record, {
      stage: "writing_artifacts",
      detail: "Writing assistant run artifacts.",
    });
    void persistAssistantRunRecord(record).then(() =>
      finalizeRun({
        status: exitCode === 0 && !timedOut ? "pass" : "fail",
        stage: exitCode === 0 && !timedOut ? "completed" : "failed",
        exitCode,
        detail:
          exitCode === 0 && !timedOut
            ? "Assistant run completed."
            : timedOut
              ? `Assistant run timed out after ${Math.round(assistantRunTimeoutMs / 1000)} seconds.`
              : signal
                ? `Assistant exited via signal ${signal}.`
                : `Assistant exited with code ${exitCode}.`,
      }),
    );
  });

  if (usesPromptPlaceholder) {
    child.stdin.end();
  } else {
    child.stdin.end(prompt);
  }

  await fs.writeFile(
    jsonAbsolutePath,
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8",
  );
  return record;
}

function parseJsonObject(raw) {
  const trimmed = raw.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const objectStart = trimmed.indexOf("{");
    const objectEnd = trimmed.lastIndexOf("}");
    if (objectStart >= 0 && objectEnd > objectStart) {
      const candidate = trimmed.slice(objectStart, objectEnd + 1);
      try {
        return JSON.parse(candidate);
      } catch {
        return null;
      }
    }
    return null;
  }
}

async function prepareDestination({
  destinationPath,
  overwrite,
  confirmation,
}) {
  const exists = await pathExists(destinationPath);
  if (!exists) {
    return { canProceed: true, overwrote: false, conflict: null };
  }

  const empty = await isDirectoryEmpty(destinationPath);
  if (empty) {
    return { canProceed: true, overwrote: false, conflict: null };
  }

  const expectedConfirmation = buildOverwriteConfirmation(destinationPath);

  if (!overwrite) {
    return {
      canProceed: false,
      overwrote: false,
      conflict: {
        destination_path: destinationPath,
        expected_confirmation: expectedConfirmation,
      },
    };
  }

  if (String(confirmation ?? "").trim() !== expectedConfirmation) {
    throw new ApiError(
      400,
      "invalid_overwrite_confirmation",
      "overwrite_confirmation is required and did not match expected value.",
      {
        expected_confirmation: expectedConfirmation,
        destination_path: disclosePath(destinationPath),
      },
    );
  }

  await removeDirectoryContents(destinationPath, { preserveGit: true });
  return { canProceed: true, overwrote: true, conflict: null };
}

function buildOverwriteConfirmation(destinationPath) {
  return `overwrite:${path.basename(destinationPath)}`;
}

async function resolveDestinationPath(input) {
  const value = String(input ?? "").trim();
  if (!value) {
    throw new ApiError(
      400,
      "invalid_destination",
      "destination_repo is required.",
    );
  }

  const candidate =
    value.includes(path.sep) || value.includes("/")
      ? path.resolve(value)
      : path.join(allowlistedRoot, value);
  await assertPathInAllowlist(candidate);
  return candidate;
}

async function assertPathInAllowlist(candidatePath) {
  const rootReal = await fs.realpath(allowlistedRoot);
  const resolved = path.resolve(candidatePath);
  const relative = path.relative(rootReal, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new ApiError(
      403,
      "outside_allowlist",
      "Path is outside allowlisted root.",
      {
        candidate_path: disclosePath(candidatePath),
        allowlisted_root: disclosePath(rootReal),
      },
    );
  }

  const ancestor = await nearestExistingAncestor(resolved);
  const ancestorReal = await fs.realpath(ancestor);
  const ancestorRelative = path.relative(rootReal, ancestorReal);
  if (ancestorRelative.startsWith("..") || path.isAbsolute(ancestorRelative)) {
    throw new ApiError(
      403,
      "symlink_escape_blocked",
      "Path escapes allowlisted root via symlink.",
      {
        candidate_path: disclosePath(candidatePath),
        allowlisted_root: disclosePath(rootReal),
        ancestor_realpath: disclosePath(ancestorReal),
      },
    );
  }
}

async function nearestExistingAncestor(candidatePath) {
  let current = path.resolve(candidatePath);
  while (!(await pathExists(current))) {
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return current;
}

async function copyDirectoryContentsSafe(
  sourceDir,
  destinationDir,
  { skipGit },
) {
  const entries = await fs.readdir(sourceDir, { withFileTypes: true });

  for (const entry of entries) {
    if (skipGit && entry.name === ".git") {
      continue;
    }

    const sourcePath = path.join(sourceDir, entry.name);
    const destinationPath = path.join(destinationDir, entry.name);

    if (entry.isSymbolicLink()) {
      throw new ApiError(
        400,
        "symlink_entry_blocked",
        `Symlink entries are not allowed during import: ${sourcePath}`,
      );
    }

    if (entry.isDirectory()) {
      await fs.mkdir(destinationPath, { recursive: true });
      await copyDirectoryContentsSafe(sourcePath, destinationPath, { skipGit });
      continue;
    }

    if (entry.isFile()) {
      await fs.mkdir(path.dirname(destinationPath), { recursive: true });
      await fs.copyFile(sourcePath, destinationPath);
      continue;
    }
  }
}

async function removeDirectoryContents(directoryPath, { preserveGit }) {
  const entries = await fs.readdir(directoryPath, { withFileTypes: true });
  for (const entry of entries) {
    if (preserveGit && entry.name === ".git") {
      continue;
    }
    await fs.rm(path.join(directoryPath, entry.name), {
      recursive: true,
      force: true,
    });
  }
}

async function ensureRuntimeDirs() {
  await fs.mkdir(generatedRoot, { recursive: true });
  await fs.mkdir(controlRoot, { recursive: true });
  await fs.mkdir(discoveryRoot, { recursive: true });
  await fs.mkdir(assistantRunsRoot, { recursive: true });
  await fs.mkdir(projectStatusHistoryRoot, { recursive: true });
  await fs.mkdir(installRequestsRoot, { recursive: true });
  await fs.mkdir(repoRegistryRoot, { recursive: true });
  await fs.mkdir(discoveryDocsRoot, { recursive: true });
  await fs.mkdir(allowlistedRoot, { recursive: true });
  await ensureBuilderAuditFile();
}

async function ensureBuilderAuditFile() {
  if (await pathExists(builderAuditPath)) {
    return;
  }

  const initial = [
    "# Builder Operation Audit",
    "",
    "| timestamp | action | status | target_repo | destination_path | sidecar_path | detail |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    "",
  ].join("\n");

  await fs.writeFile(builderAuditPath, `${initial}\n`, "utf8");
}

async function recordBuilderAudit({
  action,
  status,
  destinationPath,
  targetRepo = "",
  sidecarPath = "",
  detail,
}) {
  await ensureBuilderAuditFile();

  const timestamp = new Date().toISOString();
  const safeAction = sanitizeAuditCell(action);
  const safeStatus = sanitizeAuditCell(status);
  const safeTargetRepo = sanitizeAuditCell(discloseText(targetRepo));
  const safeDestination = sanitizeAuditCell(disclosePath(destinationPath));
  const safeSidecarPath = sanitizeAuditCell(disclosePath(sidecarPath));
  const safeDetail = sanitizeAuditCell(discloseText(detail ?? ""));

  const row = `| ${timestamp} | ${safeAction} | ${safeStatus} | ${safeTargetRepo} | ${safeDestination} | ${safeSidecarPath} | ${safeDetail} |`;
  await fs.appendFile(builderAuditPath, `${row}\n`, "utf8");

  builderState.recent_operations.unshift({
    timestamp,
    action,
    status,
    target_repo: targetRepo,
    destination_path: destinationPath,
    sidecar_path: sidecarPath,
    detail,
  });
  if (builderState.recent_operations.length > 25) {
    builderState.recent_operations.length = 25;
  }
}

function sanitizeAuditCell(value) {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replaceAll("\n", " ")
    .trim();
}

function getSessionJsonPath(sessionId) {
  return path.join(discoveryRoot, sessionId, "session.json");
}

async function writeDiscoveryFile(sessionId, filename, content) {
  const filePath = path.join(discoveryRoot, sessionId, filename);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${content.trimEnd()}\n`, "utf8");
}

function normalizePath(inputPath) {
  return inputPath.split(path.sep).join("/");
}

function disclosePath(rawPath) {
  const value = String(rawPath ?? "").trim();
  if (!value) {
    return "";
  }
  if (pathDisclosureMode === "full") {
    return value;
  }

  const normalized = normalizePath(path.resolve(value));
  const normalizedAllowlistedRoot = normalizePath(
    path.resolve(allowlistedRoot),
  );
  const normalizedRepoRoot = normalizePath(path.resolve(repoRoot));
  const normalizedHarnessSourceRoot = harnessSourceRoot
    ? normalizePath(path.resolve(harnessSourceRoot))
    : "";
  const normalizedExternalTemplateRoot = externalTemplateRoot
    ? normalizePath(path.resolve(externalTemplateRoot))
    : "";

  if (normalized === normalizedAllowlistedRoot) {
    return "<LOCAL_PROJECTS_ROOT>";
  }
  if (normalized.startsWith(`${normalizedAllowlistedRoot}/`)) {
    return `<LOCAL_PROJECTS_ROOT>/${normalized.slice(normalizedAllowlistedRoot.length + 1)}`;
  }

  if (normalized === normalizedRepoRoot) {
    return "<REPO_ROOT>";
  }
  if (normalized.startsWith(`${normalizedRepoRoot}/`)) {
    return `<REPO_ROOT>/${normalized.slice(normalizedRepoRoot.length + 1)}`;
  }

  if (normalizedHarnessSourceRoot) {
    if (normalized === normalizedHarnessSourceRoot) {
      return "<HARNESS_SOURCE_ROOT>";
    }
    if (normalized.startsWith(`${normalizedHarnessSourceRoot}/`)) {
      return `<HARNESS_SOURCE_ROOT>/${normalized.slice(normalizedHarnessSourceRoot.length + 1)}`;
    }
  }

  if (normalizedExternalTemplateRoot) {
    if (normalized === normalizedExternalTemplateRoot) {
      return "<EXTERNAL_TEMPLATE_ROOT>";
    }
    if (normalized.startsWith(`${normalizedExternalTemplateRoot}/`)) {
      return `<EXTERNAL_TEMPLATE_ROOT>/${normalized.slice(normalizedExternalTemplateRoot.length + 1)}`;
    }
  }

  if (path.isAbsolute(value)) {
    return `<LOCAL_PATH:${path.basename(normalized) || "masked"}>`;
  }
  return value;
}

function discloseText(rawText) {
  const value = String(rawText ?? "");
  if (!value || pathDisclosureMode === "full") {
    return value;
  }
  const replacements = [
    [normalizePath(path.resolve(allowlistedRoot)), "<LOCAL_PROJECTS_ROOT>"],
    [normalizePath(path.resolve(repoRoot)), "<REPO_ROOT>"],
  ];
  if (harnessSourceRoot) {
    replacements.push([
      normalizePath(path.resolve(harnessSourceRoot)),
      "<HARNESS_SOURCE_ROOT>",
    ]);
  }
  if (externalTemplateRoot) {
    replacements.push([
      normalizePath(path.resolve(externalTemplateRoot)),
      "<EXTERNAL_TEMPLATE_ROOT>",
    ]);
  }

  let sanitized = value;
  for (const [rawPath, token] of replacements) {
    sanitized = sanitized.replaceAll(rawPath, token);
  }

  return sanitized
    .replaceAll(normalizePath(path.resolve(os.homedir())), "<LOCAL_PATH>")
    .replace(/\/home\/[^\s|,;:]+/g, "<LOCAL_PATH>");
}

function shouldSkipSeedPath(relativePath, manifest) {
  const normalized = normalizePath(relativePath);
  if (manifest && isPayloadPathExcluded(normalized, manifest)) {
    return true;
  }

  if (
    VOLATILE_DISCOVERY_FILE_PATTERNS.some((pattern) => pattern.test(normalized))
  ) {
    return true;
  }

  if (normalized.startsWith(`${DISCOVERY_SESSIONS_RELATIVE_ROOT}/`)) {
    const remainder = normalized.slice(
      DISCOVERY_SESSIONS_RELATIVE_ROOT.length + 1,
    );
    return remainder !== "README.md" && remainder !== "index.md";
  }

  if (normalized.startsWith(`${PROJECT_STATUS_HISTORY_RELATIVE_ROOT}/`)) {
    return true;
  }

  return false;
}

function normalizeIntake(raw) {
  const inputModeRaw = String(raw.input_mode ?? "onboarding")
    .trim()
    .toLowerCase();
  const inputMode = inputModeRaw === "prompt" ? "prompt" : "onboarding";
  const projectPrompt = String(raw.project_prompt ?? "").trim();
  const projectGoal =
    String(raw.project_goal ?? "").trim() ||
    (inputMode === "prompt" ? projectPrompt : "");

  return {
    input_mode: inputMode,
    project_prompt: projectPrompt,
    project_goal: projectGoal,
    users: String(raw.users ?? "").trim(),
    constraints: String(raw.constraints ?? "").trim(),
    timeline: String(raw.timeline ?? "").trim(),
    integrations: String(raw.integrations ?? "").trim(),
    compliance: String(raw.compliance ?? "").trim(),
    deployment_target: String(raw.deployment_target ?? "").trim(),
    other_context: String(raw.other_context ?? "").trim(),
  };
}

function normalizeQuestion(raw, index) {
  const position = String(index + 1).padStart(2, "0");
  return {
    question_id:
      String(raw?.question_id ?? `q_${position}`).trim() || `q_${position}`,
    prompt: String(raw?.prompt ?? "").trim(),
    rationale: String(raw?.rationale ?? "").trim(),
    required: Boolean(raw?.required),
  };
}

function normalizeStringArray(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((entry) => String(entry ?? "").trim())
    .filter((entry) => entry.length > 0);
}

function splitCsv(value) {
  return String(value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function buildSessionId() {
  const timestamp = new Date()
    .toISOString()
    .replaceAll("-", "")
    .replaceAll(":", "")
    .replace("T", "_")
    .slice(0, 15);
  const nonce = crypto.randomBytes(3).toString("hex");
  return `disc_${timestamp}_${nonce}`;
}

async function readJsonBody(req, maxBytes = 5 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let bytesRead = 0;

    req.on("data", (chunk) => {
      bytesRead += chunk.length;
      if (bytesRead > maxBytes) {
        reject(
          new ApiError(
            413,
            "payload_too_large",
            "Request payload exceeds max allowed size.",
          ),
        );
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => {
      if (chunks.length === 0) {
        resolve({});
        return;
      }

      try {
        const raw = Buffer.concat(chunks).toString("utf8");
        resolve(JSON.parse(raw));
      } catch {
        reject(
          new ApiError(400, "invalid_json", "Request body must be valid JSON."),
        );
      }
    });

    req.on("error", (error) => {
      reject(error);
    });
  });
}

async function safeReadJson(filePath, fallback) {
  try {
    const content = await fs.readFile(filePath, "utf8");
    return JSON.parse(content);
  } catch {
    return fallback;
  }
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function isDirectoryEmpty(directoryPath) {
  const stats = await fs.lstat(directoryPath);
  if (!stats.isDirectory()) {
    return false;
  }

  const entries = await fs.readdir(directoryPath);
  return entries.length === 0;
}

function isRecord(value) {
  return typeof value === "object" && value !== null;
}

function buildTrustedOrigins(rawOrigins, portValue, wslIpv4 = "") {
  const configuredOrigins = String(rawOrigins ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  if (configuredOrigins.length > 0) {
    const normalized = new Set();
    for (const origin of configuredOrigins) {
      try {
        normalized.add(new URL(origin).origin);
      } catch {
        // Ignore invalid configured origins.
      }
    }
    if (normalized.size > 0) {
      return normalized;
    }
  }

  const defaults = new Set([
    `http://127.0.0.1:${portValue}`,
    `http://localhost:${portValue}`,
    `http://[::1]:${portValue}`,
  ]);
  if (wslIpv4) {
    defaults.add(`http://${wslIpv4}:${portValue}`);
  }
  return defaults;
}

function isWslRuntime() {
  if (process.platform !== "linux") {
    return false;
  }
  if (process.env.WSL_DISTRO_NAME || process.env.WSL_INTEROP) {
    return true;
  }
  return os.release().toLowerCase().includes("microsoft");
}

function detectWslIpv4() {
  if (!isWslRuntime()) {
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

function resolveTrackerUiHost() {
  const configuredHost = String(process.env.TRACKER_UI_HOST ?? "").trim();
  if (configuredHost) {
    return configuredHost;
  }
  return isWslRuntime() ? "0.0.0.0" : "127.0.0.1";
}

function isLoopbackBindHost(host) {
  const normalized = String(host ?? "")
    .trim()
    .toLowerCase();
  return (
    normalized === "127.0.0.1" ||
    normalized === "localhost" ||
    normalized === "::1" ||
    normalized === "[::1]"
  );
}

function buildUiAccessStatus() {
  const runtimeMode = isWslRuntime()
    ? "wsl"
    : process.platform === "linux"
      ? "linux"
      : "other";
  const preferredUrls = [
    uiPreferredUrl,
    uiLoopbackUrl,
    ...(uiWslUrl ? [uiWslUrl] : []),
  ];
  const browserAccessSummary =
    runtimeMode === "wsl"
      ? "Run the harness in WSL and open it from Windows with localhost or the WSL IPv4 address."
      : runtimeMode === "linux"
        ? "Open the UI on localhost when browsing from the same Linux host. If the harness host is remote, keep the UI loopback-only and use SSH local port forwarding."
        : "Open the UI on localhost from the same machine that launched the harness.";

  return {
    runtime_mode: runtimeMode,
    bind_host: uiHost,
    ui_port: uiPort,
    preferred_urls: preferredUrls,
    browser_access_summary: browserAccessSummary,
    remote_ssh_tunnel_example: `ssh -L ${uiPort}:127.0.0.1:${uiPort} <linux-host>`,
    execution_host_summary:
      "Assistant commands run on the Linux host that launched the harness.",
    public_bind_supported: false,
  };
}

function shellQuote(value) {
  return `'${String(value ?? "").replaceAll("'", `'\\''`)}'`;
}

function joinShellCommand(command, args = []) {
  return [command, ...args]
    .map((part, index) => {
      const value = String(part ?? "");
      if (index === 0 && /^[a-zA-Z0-9_./:+-]+$/.test(value)) {
        return value;
      }
      return shellQuote(value);
    })
    .join(" ");
}

function buildAssistantTerminalCommandTemplate(command, args) {
  const normalizedArgs = Array.isArray(args)
    ? args.map((entry) => String(entry ?? ""))
    : [];
  if (normalizedArgs.some((arg) => arg.includes("{{prompt}}"))) {
    return joinShellCommand(
      command,
      normalizedArgs.map((arg) =>
        arg.replaceAll("{{prompt}}", "<paste prompt here>"),
      ),
    );
  }
  return `printf '%s\\n' '<paste prompt here>' | ${joinShellCommand(command, normalizedArgs)}`;
}

function buildAssistantRuntimeStatus(assistant) {
  const { command, argsRaw, defaultArgs } =
    buildAssistantCommandSpec(assistant);
  const args = argsRaw ? splitShellLikeArgs(argsRaw) : defaultArgs;
  const available = commandExists(command);
  return {
    assistant,
    label: assistant === "claude_code" ? "Claude Code CLI" : "Codex CLI",
    command,
    args,
    terminal_command_template: buildAssistantTerminalCommandTemplate(
      command,
      args,
    ),
    availability_status: available ? "available" : "unavailable",
    detail: available
      ? `${command} is available on the Linux host running this harness.`
      : `${command} is not available on the Linux host running this harness.`,
  };
}

function getRequestOrigin(req) {
  const originHeader = req.headers.origin;
  if (Array.isArray(originHeader)) {
    return String(originHeader[0] ?? "").trim();
  }
  if (typeof originHeader === "string") {
    return originHeader.trim();
  }
  return "";
}

function isTrustedOrigin(origin) {
  return trustedOrigins.has(origin);
}

function assertTrustedOrigin(req) {
  const origin = getRequestOrigin(req);
  if (!origin) {
    return;
  }
  if (!isTrustedOrigin(origin)) {
    throw new ApiError(
      403,
      "origin_not_allowed",
      `Origin is not allowed: ${origin}`,
    );
  }
}

function setCorsHeaders(req, res) {
  const origin = getRequestOrigin(req);
  if (origin && isTrustedOrigin(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

function json(res, statusCode, body) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
  });
  res.end(`${JSON.stringify(body, null, 2)}\n`);
}

class ApiError extends Error {
  constructor(statusCode, code, message, detail = {}) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.detail = detail;
  }
}
