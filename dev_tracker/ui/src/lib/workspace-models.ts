import type {
  BuilderOperationRecordV1,
  BuilderStatusV1,
  ControlStatusV1,
  TemplateStudioV1,
  TrackerSnapshotV6,
} from "./contracts";
import { isOverviewManagerProject, OVERVIEW_MANAGER_PROJECT_LABEL } from "./overview-project";
import { PRODUCT_METADATA } from "./product-metadata";

type HealthTone = "success" | "warning" | "info";

export interface WorkspaceStatusChipModel {
  label: string;
  tone: HealthTone;
}

export interface ManagerWorkspaceModel {
  trackedProjectCount: number;
  pendingApprovals: number;
  openGaps: number;
  attentionProjectCount: number;
  templateVersion: string;
  templateStatus: WorkspaceStatusChipModel;
  dryRunStatus: WorkspaceStatusChipModel;
  currentObjective: string;
  currentObjectiveScope: string;
  nextAction: string;
  nextActionDetail: string;
  reviewQueues: Array<{
    id: string;
    label: string;
    actionableDocs: number;
    implementedDocs: number;
  }>;
  recentOperations: BuilderOperationRecordV1[];
  runtime: {
    host: string;
    mode: string;
    codex: string;
    claude: string;
    ssh: string;
  };
}

export interface ProjectPortfolioRowModel {
  id: string;
  label: string;
  scope: "manager" | "tracked";
  path: string;
  connection: string;
  harnessVersion: string;
  templateDrift: WorkspaceStatusChipModel;
  health: WorkspaceStatusChipModel;
  lastActivity: string;
  docsIndexed: string;
  pendingApprovals: number;
  selected: boolean;
}

export interface ProjectsWorkspaceModel {
  rows: ProjectPortfolioRowModel[];
  totalProjects: number;
  trackedProjects: number;
  attentionProjects: number;
}

export interface TemplateWorkspaceModel {
  templateId: string;
  templateVersion: string;
  managerVersion: string;
  releaseStage: string;
  pathConvention: string;
  compatibilityMode: string;
  sectionCount: number;
  placeholderCount: number;
  readyCount: number;
  sections: TemplateStudioV1["sections"];
  validationStatus: WorkspaceStatusChipModel;
  dryRunStatus: WorkspaceStatusChipModel;
  inventory: TemplateStudioV1["inventory"];
}

function formatOperation(operation: BuilderOperationRecordV1 | undefined) {
  if (!operation) {
    return "No recorded operation";
  }
  const value = new Date(operation.timestamp);
  const timestamp = Number.isNaN(value.getTime()) ? operation.timestamp : value.toLocaleString();
  return `${operation.action} · ${timestamp}`;
}

function templateStatusFromData(templateStudio: TemplateStudioV1 | null): WorkspaceStatusChipModel {
  if (!templateStudio?.validation.available) {
    return { label: "Validation pending", tone: "warning" };
  }
  return templateStudio.validation.overall_ok
    ? { label: "Payload validated", tone: "success" }
    : { label: "Payload validation failed", tone: "warning" };
}

function dryRunStatusFromData(templateStudio: TemplateStudioV1 | null): WorkspaceStatusChipModel {
  if (!templateStudio?.dry_run.available) {
    return { label: "Dry run pending", tone: "warning" };
  }
  return templateStudio.dry_run.blank_ok && templateStudio.dry_run.existing_ok
    ? { label: "Dry runs passing", tone: "success" }
    : { label: "Dry run attention", tone: "warning" };
}

function deriveTrackedProjectHealth(operation: BuilderOperationRecordV1 | undefined): WorkspaceStatusChipModel {
  if (!operation) {
    return { label: "Awaiting deploy", tone: "info" };
  }
  if (operation.status === "success") {
    return { label: "Operational", tone: "success" };
  }
  return { label: "Needs review", tone: "warning" };
}

function deriveTrackedProjectDrift(operation: BuilderOperationRecordV1 | undefined): WorkspaceStatusChipModel {
  if (!operation) {
    return { label: "Not deployed", tone: "warning" };
  }
  return operation.status === "success"
    ? { label: `Aligned to ${PRODUCT_METADATA.templateVersion}`, tone: "success" }
    : { label: "Payload drift unknown", tone: "info" };
}

export function deriveManagerWorkspaceModel({
  snapshot,
  status,
  builderStatus,
  templateStudio,
}: {
  snapshot: TrackerSnapshotV6;
  status: ControlStatusV1 | null;
  builderStatus: BuilderStatusV1 | null;
  templateStudio: TemplateStudioV1 | null;
}): ManagerWorkspaceModel {
  const currentObjective = snapshot.project_overview.active_objectives[0] ?? null;
  const attentionProjects = (builderStatus?.known_repos ?? []).filter((repo) => {
    const operation = builderStatus?.recent_operations.find((row) => row.target_repo === repo.name);
    return !operation || operation.status !== "success";
  });

  return {
    trackedProjectCount: builderStatus?.known_repos.length ?? 0,
    pendingApprovals: snapshot.review_queue.pending_approvals,
    openGaps: snapshot.capability_gaps.open_count,
    attentionProjectCount: attentionProjects.length,
    templateVersion: templateStudio?.template_manifest.template_version ?? PRODUCT_METADATA.templateVersion,
    templateStatus: templateStatusFromData(templateStudio),
    dryRunStatus: dryRunStatusFromData(templateStudio),
    currentObjective: currentObjective?.goal ?? "No active objective recorded.",
    currentObjectiveScope: currentObjective?.in_scope ?? "Manager repo is between active objectives.",
    nextAction: snapshot.human_review_summary.next_action.toUpperCase(),
    nextActionDetail: `Loop next action: ${snapshot.loop_state.next_action || "n/a"} · Pending reviews: ${snapshot.review_queue.pending_total}`,
    reviewQueues: snapshot.review_queue.queues.map((queue) => ({
      id: queue.queue_id,
      label: queue.label,
      actionableDocs: queue.actionable_docs,
      implementedDocs: queue.implemented_docs,
    })),
    recentOperations: (builderStatus?.recent_operations ?? []).slice(0, 5),
    runtime: {
      host: status?.ui_access?.execution_host_summary ?? "Host details unavailable",
      mode: status?.ui_access?.runtime_mode ?? "unknown",
      codex: status?.assistant_runtimes?.codex_cli.availability_status ?? "unknown",
      claude: status?.assistant_runtimes?.claude_code.availability_status ?? "unknown",
      ssh: status?.remote_ssh?.mode ?? "unknown",
    },
  };
}

export function deriveProjectsWorkspaceModel({
  snapshot,
  builderStatus,
  selectedProject,
}: {
  snapshot: TrackerSnapshotV6;
  builderStatus: BuilderStatusV1 | null;
  selectedProject: string;
}): ProjectsWorkspaceModel {
  const latestOperationByRepo = new Map<string, BuilderOperationRecordV1>();
  for (const row of builderStatus?.recent_operations ?? []) {
    if (row.target_repo && !latestOperationByRepo.has(row.target_repo)) {
      latestOperationByRepo.set(row.target_repo, row);
    }
  }

  const managerRow: ProjectPortfolioRowModel = {
    id: "manager",
    label: OVERVIEW_MANAGER_PROJECT_LABEL,
    scope: "manager",
    path: snapshot.repo_root,
    connection: "Linux local",
    harnessVersion: PRODUCT_METADATA.managerVersion,
    templateDrift: { label: `Payload ${PRODUCT_METADATA.templateVersion}`, tone: "success" },
    health: snapshot.git.dirty || snapshot.review_queue.pending_total > 0 ? { label: "Needs attention", tone: "warning" } : { label: "Stable", tone: "success" },
    lastActivity: snapshot.git.last_commit || "No recent commit data",
    docsIndexed: `${snapshot.summary.docs_total} indexed`,
    pendingApprovals: snapshot.review_queue.pending_approvals,
    selected: isOverviewManagerProject(selectedProject),
  };

  const trackedRows = (builderStatus?.known_repos ?? []).map<ProjectPortfolioRowModel>((repo) => {
    const latestOperation = latestOperationByRepo.get(repo.name);
    return {
      id: repo.name,
      label: repo.name,
      scope: "tracked",
      path: repo.path,
      connection: "Local repo",
      harnessVersion: latestOperation?.status === "success" ? PRODUCT_METADATA.templateVersion : "Undetected",
      templateDrift: deriveTrackedProjectDrift(latestOperation),
      health: deriveTrackedProjectHealth(latestOperation),
      lastActivity: formatOperation(latestOperation),
      docsIndexed: latestOperation ? "Harness activity recorded" : "Awaiting first scan",
      pendingApprovals: 0,
      selected: repo.name === selectedProject,
    };
  });

  const rows = [managerRow, ...trackedRows];
  const attentionProjects = rows.filter((row) => row.health.tone === "warning").length;

  return {
    rows,
    totalProjects: rows.length,
    trackedProjects: trackedRows.length,
    attentionProjects,
  };
}

export function deriveTemplateWorkspaceModel(templateStudio: TemplateStudioV1 | null): TemplateWorkspaceModel {
  const sections = templateStudio?.sections ?? [];
  const placeholderCount = templateStudio?.inventory.placeholder_count ?? sections.filter((section) => section.placeholder).length;
  const sectionCount = templateStudio?.required_sections.length ?? sections.length;

  return {
    templateId: templateStudio?.template_manifest.template_id ?? PRODUCT_METADATA.templateId,
    templateVersion: templateStudio?.template_manifest.template_version ?? PRODUCT_METADATA.templateVersion,
    managerVersion: templateStudio?.manager_manifest.template_version ?? PRODUCT_METADATA.managerVersion,
    releaseStage: templateStudio?.template_manifest.release_stage ?? PRODUCT_METADATA.releaseStage,
    pathConvention: templateStudio?.template_manifest.path_convention ?? "snake_case",
    compatibilityMode: templateStudio?.template_manifest.compatibility_mode ?? "canonical_only",
    sectionCount,
    placeholderCount,
    readyCount: Math.max(sectionCount - placeholderCount, 0),
    sections,
    validationStatus: templateStatusFromData(templateStudio),
    dryRunStatus: dryRunStatusFromData(templateStudio),
    inventory: templateStudio?.inventory ?? {
      total_files: 0,
      docs_markdown_count: 0,
      harness_markdown_count: 0,
      placeholder_count: placeholderCount,
    },
  };
}
