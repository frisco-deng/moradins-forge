import type {
  AssistantRunListResponseV1,
  AssistantRunRequestV1,
  AssistantRunResponseV1,
  BuilderProviderListV1,
  BuilderRepoCompletenessRequestV1,
  BuilderRepoCompletenessResponseV1,
  BuilderStatusV1,
  ControlStatusV1,
  CreateLocalRepoRequestV1,
  CreateLocalRepoResponseV1,
  DiscoveryFollowOnPlanResponseV1,
  DiscoveryIntakeV1,
  DiscoveryPromptBundleV1,
  DiscoverySessionV1,
  DeployExistingProjectRequestV1,
  DeployExistingProjectResponseV1,
  GenerateProjectRepoRequestV1,
  GenerateProjectRepoResponseV1,
  GitStateV1,
  ImportHarnessRequestV1,
  ImportHarnessResponseV1,
  ProjectScanResponseV1,
  ProjectScanRequestV1,
  ProjectStatusReportV1,
  ProjectStatusHistoryResponseV1,
  RemoteTargetConfigV1,
  RemoteSshExecuteResponseV1,
  RemoteSshTestResponseV1,
  ReviewQueueV1,
  TemplateStudioV1,
  HumanReviewRowV1,
  MoradinInstallRequestV1,
  MoradinRepoRegistryV1,
  MoradinToolingReadinessV1,
  TrackerSnapshotV4,
  TrackerSnapshotV5,
  TrackerSnapshotV6,
} from "./contracts";
import { classifyDocRecord, deriveSummaryV2FromDocs } from "./doc-classification";

const TRACKER_SNAPSHOT_V4 = "TrackerSnapshotV4";
const TRACKER_SNAPSHOT_V5 = "TrackerSnapshotV5";
const TRACKER_SNAPSHOT_V6 = "TrackerSnapshotV6";
const NON_ACTIONABLE_STATUSES = new Set([
  "implemented",
  "closed",
  "archived",
  "completed",
  "rejected",
  "cancelled",
  "superseded",
  "done",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasVersion(value: unknown, expected: string): boolean {
  return isRecord(value) && value.version === expected;
}

function hasRequiredSnapshotFields(value: Record<string, unknown>): boolean {
  if (typeof value.generated_at !== "string" || typeof value.repo_root !== "string" || !isRecord(value.summary)) {
    return false;
  }

  if (
    !hasVersion(value.phases, "PhaseBoardV1") ||
    !hasVersion(value.loop_state, "LoopStateV1") ||
    !hasVersion(value.capability_gaps, "CapabilityGapV1") ||
    !hasVersion(value.changelog, "ChangelogV1") ||
    !hasVersion(value.current_features, "CurrentFeaturesV1") ||
    !hasVersion(value.current_guidance, "CurrentGuidanceV1") ||
    !hasVersion(value.loop_processes, "LoopProcessesV1") ||
    !hasVersion(value.human_gate_stats, "HumanGateStatsV1") ||
    !hasVersion(value.archive_register, "ArchiveRegisterV1") ||
    !hasVersion(value.policies, "PolicyDomainSummaryV1") ||
    !hasVersion(value.topology, "TopologySnapshotV1") ||
    !hasVersion(value.project_overview, "ProjectOverviewV1") ||
    !hasVersion(value.service_inventory, "ServiceInventoryV1") ||
    !hasVersion(value.harness_help, "HarnessHelpV1") ||
    !hasVersion(value.git, "GitStateV1")
  ) {
    return false;
  }

  if (!Array.isArray(value.docs)) {
    return false;
  }

  return value.docs.every((doc) => hasVersion(doc, "DocRecordV1"));
}

function isTrackerSnapshotV4(value: unknown): value is TrackerSnapshotV4 {
  if (!isRecord(value)) {
    return false;
  }

  if (value.version !== TRACKER_SNAPSHOT_V4) {
    return false;
  }

  return hasRequiredSnapshotFields(value);
}

function isTrackerSnapshotV5(value: unknown): value is TrackerSnapshotV5 {
  if (!isRecord(value)) {
    return false;
  }

  if (value.version !== TRACKER_SNAPSHOT_V5) {
    return false;
  }

  if (!hasRequiredSnapshotFields(value)) {
    return false;
  }

  return (
    hasVersion(value.review_queue, "ReviewQueueV1") &&
    hasVersion(value.route_context_coverage, "RouteContextCoverageV1") &&
    hasVersion(value.human_review_summary, "HumanReviewSummaryV1")
  );
}

function isTrackerSnapshotV6(value: unknown): value is TrackerSnapshotV6 {
  if (!isRecord(value)) {
    return false;
  }

  if (value.version !== TRACKER_SNAPSHOT_V6) {
    return false;
  }

  if (!hasRequiredSnapshotFields(value)) {
    return false;
  }

  return (
    hasVersion(value.review_queue, "ReviewQueueV1") &&
    hasVersion(value.route_context_coverage, "RouteContextCoverageV1") &&
    hasVersion(value.human_review_summary, "HumanReviewSummaryV1")
  );
}

function isActionableStatus(status: string | null | undefined): boolean {
  const normalized = String(status ?? "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return !NON_ACTIONABLE_STATUSES.has(normalized);
}

function buildFallbackReviewQueue(snapshot: TrackerSnapshotV4): ReviewQueueV1 {
  const queueSpecs = [
    {
      queue_id: "updates" as const,
      label: "Updates",
      include: (relativePath: string) =>
        relativePath.startsWith("docs/exec_plans/updates/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "upgrades" as const,
      label: "Upgrades",
      include: (relativePath: string) =>
        relativePath.startsWith("docs/exec_plans/upgrades/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "tooling" as const,
      label: "Tooling",
      include: (relativePath: string) =>
        relativePath.startsWith("docs/exec_plans/tooling/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "suggestions" as const,
      label: "Suggestions",
      include: (relativePath: string) =>
        relativePath.startsWith("docs/exec_plans/implementation/active/sug_") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "governance" as const,
      label: "Governance",
      include: (relativePath: string) =>
        relativePath.startsWith("docs/exec_plans/implementation/active/") &&
        !relativePath.endsWith("/index.md") &&
        !relativePath.includes("/sug_"),
    },
  ];

  const queues = queueSpecs.map((spec) => {
    const rows = snapshot.docs
      .filter((doc) => spec.include(String(doc.relative_path ?? "")))
      .map((doc) => ({
        doc_id: String(doc.id ?? ""),
        relative_path: String(doc.relative_path ?? ""),
        title: String(doc.title ?? ""),
        status: String(doc.status ?? ""),
        owner: String(doc.owner ?? ""),
        actionable: isActionableStatus(doc.status),
      }));
    return {
      queue_id: spec.queue_id,
      label: spec.label,
      active_docs: rows.length,
      actionable_docs: rows.filter((row) => row.actionable).length,
      implemented_docs: rows.filter((row) => !row.actionable).length,
      rows,
    };
  });

  const queueById = Object.fromEntries(queues.map((queue) => [queue.queue_id, queue]));
  const pendingTotal = queues.reduce((sum, queue) => sum + queue.actionable_docs, 0);
  return {
    version: "ReviewQueueV1",
    generated_at: snapshot.generated_at,
    pending_approvals: snapshot.changelog.awaiting_human_review_count,
    pending_total: pendingTotal,
    queues,
    zero_state: {
      updates: (queueById.updates?.actionable_docs ?? 0) === 0,
      upgrades: (queueById.upgrades?.actionable_docs ?? 0) === 0,
      tooling: (queueById.tooling?.actionable_docs ?? 0) === 0,
      suggestions: (queueById.suggestions?.actionable_docs ?? 0) === 0,
    },
    reconciliation: {
      status: "warn",
      issues: ["Snapshot upgraded from V4 fallback fields; run sync-docs to generate canonical V5 review queue data."],
    },
  };
}

function upgradeDocs(snapshot: Pick<TrackerSnapshotV4, "docs">): TrackerSnapshotV4["docs"] {
  return snapshot.docs.map((doc) => ({
    ...doc,
    classification: doc.classification ?? classifyDocRecord(doc),
  }));
}

function coerceV4ToV6(snapshot: TrackerSnapshotV4): TrackerSnapshotV6 {
  const docs = upgradeDocs(snapshot);
  const reviewQueue = buildFallbackReviewQueue(snapshot);
  const projectReview: HumanReviewRowV1[] = [
    {
      review_id: "project-approvals",
      label: "Pending approvals",
      pending_count: snapshot.changelog.awaiting_human_review_count,
      severity: snapshot.changelog.awaiting_human_review_count > 0 ? "high" : "none",
      route: "/exchange",
      source: "changelog.awaiting_human_review_count",
    },
    {
      review_id: "project-features",
      label: "Pending features",
      pending_count: snapshot.current_features.pending_count,
      severity: snapshot.current_features.pending_count > 0 ? "medium" : "none",
      route: "/features",
      source: "current_features.pending_count",
    },
  ];
  const harnessReview: HumanReviewRowV1[] = [
    {
      review_id: "harness-updates",
      label: "Actionable updates",
      pending_count: reviewQueue.queues.find((queue) => queue.queue_id === "updates")?.actionable_docs ?? 0,
      severity:
        (reviewQueue.queues.find((queue) => queue.queue_id === "updates")?.actionable_docs ?? 0) > 0 ? "medium" : "none",
      route: "/exchange",
      source: "review_queue.updates.actionable_docs",
    },
    {
      review_id: "harness-upgrades",
      label: "Actionable upgrades",
      pending_count: reviewQueue.queues.find((queue) => queue.queue_id === "upgrades")?.actionable_docs ?? 0,
      severity:
        (reviewQueue.queues.find((queue) => queue.queue_id === "upgrades")?.actionable_docs ?? 0) > 0 ? "medium" : "none",
      route: "/exchange",
      source: "review_queue.upgrades.actionable_docs",
    },
  ];
  const pendingTotal =
    projectReview.reduce((sum, row) => sum + row.pending_count, 0) + harnessReview.reduce((sum, row) => sum + row.pending_count, 0);
  return {
    ...snapshot,
    version: "TrackerSnapshotV6",
    summary: deriveSummaryV2FromDocs(docs, snapshot.summary),
    review_queue: reviewQueue,
    route_context_coverage: {
      version: "RouteContextCoverageV1",
      router_route_count: 0,
      context_route_count: 0,
      coverage_percent: 0,
      missing_in_context: [],
      extra_in_context: [],
      rows: [],
    },
    human_review_summary: {
      version: "HumanReviewSummaryV1",
      generated_at: snapshot.generated_at,
      next_action: pendingTotal > 0 ? "pause" : "continue",
      pending_total: pendingTotal,
      project_review: projectReview,
      harness_review: harnessReview,
      notes: ["Snapshot upgraded from V4. Run sync-docs to generate canonical review summary."],
    },
    docs,
  };
}

function coerceV5ToV6(snapshot: TrackerSnapshotV5): TrackerSnapshotV6 {
  const docs = upgradeDocs(snapshot);
  return {
    ...snapshot,
    version: "TrackerSnapshotV6",
    summary: deriveSummaryV2FromDocs(docs, snapshot.summary),
    docs,
  };
}

async function safeFetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

async function safeFetchVersioned<T extends { version: string }>(
  url: string,
  expectedVersion: string,
): Promise<T | null> {
  const payload = await safeFetchJson<T | null>(url, null);
  if (!payload || payload.version !== expectedVersion) {
    return null;
  }
  return payload;
}

export async function loadTrackerSnapshot(): Promise<TrackerSnapshotV6 | null> {
  const cacheBust = Date.now();
  const snapshot = await safeFetchJson<unknown | null>(
    `/generated/tracker_snapshot_v1.json?t=${cacheBust}`,
    null,
  );

  if (isTrackerSnapshotV6(snapshot)) {
    return {
      ...snapshot,
      docs: upgradeDocs(snapshot),
      summary: deriveSummaryV2FromDocs(upgradeDocs(snapshot), snapshot.summary),
    };
  }

  if (isTrackerSnapshotV5(snapshot)) {
    return coerceV5ToV6(snapshot);
  }

  if (isTrackerSnapshotV4(snapshot)) {
    return coerceV4ToV6(snapshot);
  }

  return null;
}

export async function loadControlStatus(): Promise<ControlStatusV1 | null> {
  const data = await safeFetchJson<ControlStatusV1 | null>("/api/status", null);
  if (!data || data.api !== "TrackerControlStatusV1") {
    return null;
  }
  return data;
}

export async function loadGitState(): Promise<GitStateV1 | null> {
  return safeFetchVersioned<GitStateV1>(`/api/git?t=${Date.now()}`, "GitStateV1");
}

export async function triggerSync(): Promise<ControlStatusV1 | null> {
  try {
    const response = await fetch("/api/sync", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as ControlStatusV1;
    if (payload.api !== "TrackerControlStatusV1") {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

async function postJson<TResponse>(url: string, payload: unknown): Promise<TResponse | null> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as TResponse;
  } catch {
    return null;
  }
}

export async function loadBuilderStatus(): Promise<BuilderStatusV1 | null> {
  const status = await safeFetchJson<BuilderStatusV1 | null>(`/api/builder/status?t=${Date.now()}`, null);
  if (!status || status.version !== "BuilderStatusV1") {
    return null;
  }
  return status;
}

export async function loadMoradinReadiness(): Promise<MoradinToolingReadinessV1 | null> {
  const readiness = await safeFetchJson<MoradinToolingReadinessV1 | null>(`/api/moradin/readiness?t=${Date.now()}`, null);
  if (!readiness || readiness.version !== "MoradinToolingReadinessV1") {
    return null;
  }
  return readiness;
}

export async function createMoradinInstallRequest(payload: {
  tool_ids?: string[];
  assistant_mode?: "codex_cli" | "codex_app_manual_handoff" | "claude_code" | "manual_handoff";
  operator_note?: string;
}): Promise<MoradinInstallRequestV1 | null> {
  const response = await postJson<MoradinInstallRequestV1>("/api/moradin/install-request", payload);
  if (!response || response.version !== "MoradinInstallRequestV1") {
    return null;
  }
  return response;
}

export async function loadMoradinRepoRegistry(): Promise<MoradinRepoRegistryV1 | null> {
  const registry = await safeFetchJson<MoradinRepoRegistryV1 | null>(`/api/moradin/repo-registry?t=${Date.now()}`, null);
  if (!registry || registry.version !== "MoradinRepoRegistryV1") {
    return null;
  }
  return registry;
}

export async function loadTemplateStudio(): Promise<TemplateStudioV1 | null> {
  return safeFetchVersioned<TemplateStudioV1>(`/generated/template_studio_v1.json?t=${Date.now()}`, "TemplateStudioV1");
}

export async function loadBuilderProviders(): Promise<BuilderProviderListV1 | null> {
  const providers = await safeFetchJson<BuilderProviderListV1 | null>(`/api/builder/providers?t=${Date.now()}`, null);
  if (!providers || providers.version !== "BuilderProviderListV1") {
    return null;
  }
  return providers;
}

export async function loadReviewQueue(): Promise<ReviewQueueV1 | null> {
  const reviewQueue = await safeFetchJson<ReviewQueueV1 | null>(`/api/review/queue?t=${Date.now()}`, null);
  if (!reviewQueue || reviewQueue.version !== "ReviewQueueV1") {
    return null;
  }
  return reviewQueue;
}

export async function checkBuilderRepoCompleteness(
  payload: BuilderRepoCompletenessRequestV1,
): Promise<BuilderRepoCompletenessResponseV1 | null> {
  const response = await postJson<BuilderRepoCompletenessResponseV1>("/api/builder/repo-completeness", payload);
  if (!response || response.version !== "BuilderRepoCompletenessResponseV1") {
    return null;
  }
  return response;
}

export async function runProjectBaselineScan(payload: ProjectScanRequestV1): Promise<ProjectScanResponseV1 | null> {
  const response = await postJson<ProjectScanResponseV1>("/api/builder/project-scan", payload);
  if (!response || response.version !== "ProjectBaselineScanV1") {
    return null;
  }
  return response;
}

export async function deployExistingProject(
  payload: DeployExistingProjectRequestV1,
): Promise<DeployExistingProjectResponseV1 | null> {
  const response = await postJson<DeployExistingProjectResponseV1>("/api/builder/deploy-existing", payload);
  if (!response || response.version !== "DeployExistingProjectResponseV1") {
    return null;
  }
  return response;
}

export async function loadProjectStatusReport(payload: {
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetConfigV1;
  session_id?: string;
}): Promise<ProjectStatusReportV1 | null> {
  const response = await postJson<ProjectStatusReportV1>("/api/builder/project-status", payload);
  if (!response || response.version !== "ProjectStatusReportV1") {
    return null;
  }
  return response;
}

export async function loadProjectStatusHistory(payload: {
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetConfigV1;
  limit?: number;
}): Promise<ProjectStatusHistoryResponseV1 | null> {
  const targetRepo = String(payload.target_repo ?? "").trim();
  if (!targetRepo) {
    return null;
  }
  const query = new URLSearchParams();
  query.set("target_repo", targetRepo);
  if (payload.target_mode) {
    query.set("target_mode", payload.target_mode);
  }
  if (payload.remote_target) {
    query.set("remote_target", JSON.stringify(payload.remote_target));
  }
  if (Number.isInteger(payload.limit) && Number(payload.limit) > 0) {
    query.set("limit", String(payload.limit));
  }
  const response = await safeFetchJson<ProjectStatusHistoryResponseV1 | null>(
    `/api/builder/project-status/history?${query.toString()}`,
    null,
  );
  if (!response || response.version !== "ProjectStatusHistoryResponseV1") {
    return null;
  }
  return response;
}

export async function createLocalRepo(
  payload: CreateLocalRepoRequestV1,
): Promise<CreateLocalRepoResponseV1 | null> {
  const response = await postJson<CreateLocalRepoResponseV1>("/api/builder/create-local-repo", payload);
  if (!response || response.version !== "CreateLocalRepoResponseV1") {
    return null;
  }
  return response;
}

export async function importHarnessPath(
  payload: ImportHarnessRequestV1,
): Promise<ImportHarnessResponseV1 | null> {
  const response = await postJson<ImportHarnessResponseV1>("/api/builder/import-harness-path", payload);
  if (!response || response.version !== "ImportHarnessResponseV1") {
    return null;
  }
  return response;
}

export async function importHarnessBundle(
  payload: ImportHarnessRequestV1,
): Promise<ImportHarnessResponseV1 | null> {
  const response = await postJson<ImportHarnessResponseV1>("/api/builder/import-harness-bundle", payload);
  if (!response || response.version !== "ImportHarnessResponseV1") {
    return null;
  }
  return response;
}

export async function generateProjectRepoFromDiscovery(
  payload: GenerateProjectRepoRequestV1,
): Promise<GenerateProjectRepoResponseV1 | null> {
  const response = await postJson<GenerateProjectRepoResponseV1>("/api/builder/generate-from-discovery", payload);
  if (!response || response.version !== "GenerateProjectRepoResponseV1") {
    return null;
  }
  return response;
}

export async function startDiscoverySession(payload: {
  intake: DiscoveryIntakeV1;
  provider?: "none" | "openai" | "codex_cli" | "claude_code";
  model?: string;
}): Promise<DiscoverySessionV1 | null> {
  const response = await postJson<DiscoverySessionV1>("/api/discovery/session/start", {
    intake: payload.intake,
    provider: payload.provider,
    model: payload.model,
  });
  if (!response || response.version !== "DiscoverySessionV1") {
    return null;
  }
  return response;
}

export async function answerDiscoverySession(payload: {
  session_id: string;
  answers: Record<string, string>;
  intake_updates?: Record<string, string>;
  provider?: "none" | "openai" | "codex_cli" | "claude_code";
  model?: string;
}): Promise<DiscoverySessionV1 | null> {
  const response = await postJson<DiscoverySessionV1>("/api/discovery/session/answer", payload);
  if (!response || response.version !== "DiscoverySessionV1") {
    return null;
  }
  return response;
}

export async function generateDiscoverySession(sessionId: string): Promise<DiscoverySessionV1 | null> {
  const response = await postJson<DiscoverySessionV1>("/api/discovery/session/generate", {
    session_id: sessionId,
  });
  if (!response || response.version !== "DiscoverySessionV1") {
    return null;
  }
  return response;
}

export async function loadDiscoverySession(sessionId: string): Promise<DiscoverySessionV1 | null> {
  const response = await safeFetchJson<DiscoverySessionV1 | null>(
    `/api/discovery/session/${encodeURIComponent(sessionId)}?t=${Date.now()}`,
    null,
  );
  if (!response || response.version !== "DiscoverySessionV1") {
    return null;
  }
  return response;
}

export async function buildDiscoveryPromptBundle(payload: {
  session_id: string;
  stage?: "questions" | "synthesis";
  selected_profile?: string;
}): Promise<DiscoveryPromptBundleV1 | null> {
  const response = await postJson<DiscoveryPromptBundleV1>("/api/discovery/session/build-prompt-bundle", payload);
  if (!response || response.version !== "DiscoveryPromptBundleV1") {
    return null;
  }
  return response;
}

export async function buildDiscoveryFollowOnPlan(payload: {
  session_id: string;
  target_repo: string;
  selected_profile?: string;
}): Promise<DiscoveryFollowOnPlanResponseV1 | null> {
  const response = await postJson<DiscoveryFollowOnPlanResponseV1>("/api/discovery/session/build-follow-on-plan", payload);
  if (!response || response.version !== "DiscoveryFollowOnPlanResponseV1") {
    return null;
  }
  return response;
}

export async function testRemoteSsh(payload: {
  target: RemoteTargetConfigV1;
}): Promise<RemoteSshTestResponseV1 | null> {
  const response = await postJson<RemoteSshTestResponseV1>("/api/builder/remote/ssh/test", payload);
  if (!response || response.version !== "RemoteSshTestResponseV1") {
    return null;
  }
  return response;
}

export async function executeRemoteSsh(payload: {
  target: RemoteTargetConfigV1;
  command: string;
}): Promise<RemoteSshExecuteResponseV1 | null> {
  const response = await postJson<RemoteSshExecuteResponseV1>("/api/builder/remote/ssh/execute", payload);
  if (!response || response.version !== "RemoteSshExecuteResponseV1") {
    return null;
  }
  return response;
}

export async function runAssistantAction(
  payload: AssistantRunRequestV1,
): Promise<AssistantRunResponseV1 | null> {
  const response = await postJson<AssistantRunResponseV1>("/api/assistant/run", payload);
  if (!response || response.version !== "AssistantRunResponseV1") {
    return null;
  }
  return response;
}

export async function loadAssistantRun(runId: string): Promise<AssistantRunResponseV1 | null> {
  const normalizedRunId = String(runId ?? "").trim();
  if (!normalizedRunId) {
    return null;
  }
  return safeFetchVersioned<AssistantRunResponseV1>(
    `/api/assistant/run/${encodeURIComponent(normalizedRunId)}?t=${Date.now()}`,
    "AssistantRunResponseV1",
  );
}

export async function loadAssistantRuns(limit = 8): Promise<AssistantRunListResponseV1 | null> {
  const safeLimit = Number.isFinite(limit) ? Math.max(1, Math.min(50, Math.trunc(limit))) : 8;
  return safeFetchVersioned<AssistantRunListResponseV1>(
    `/api/assistant/runs?limit=${safeLimit}&t=${Date.now()}`,
    "AssistantRunListResponseV1",
  );
}

export function resolveRelatedPath(currentPath: string, relatedPath: string): string {
  if (!relatedPath) {
    return "";
  }

  if (
    relatedPath.startsWith("docs/") ||
    relatedPath.startsWith("skills/") ||
    relatedPath === "AGENTS.md"
  ) {
    return relatedPath;
  }

  const currentParts = currentPath.split("/");
  currentParts.pop();
  const relatedParts = relatedPath.split("/");

  for (const part of relatedParts) {
    if (part === "." || part === "") {
      continue;
    }
    if (part === "..") {
      currentParts.pop();
      continue;
    }
    currentParts.push(part);
  }

  return currentParts.join("/");
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
