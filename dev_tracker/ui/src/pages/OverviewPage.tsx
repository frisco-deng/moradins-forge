import { startTransition, useEffect, useMemo, useState } from "react";
import { Activity, MoreHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import { ArchitectureTree } from "../components/ArchitectureTree";
import { GlassPopover } from "../components/GlassPopover";
import { MagicTile } from "../components/MagicTile";
import { PageHero } from "../components/PageHero";
import { PhaseProgressDots, StageProgressDots } from "../components/PhaseProgressDots";
import { StatusChip } from "../components/StatusChip";
import { StatusPillButton } from "../components/StatusPillButton";
import { TooltipHint } from "../components/TooltipHint";
import { notifyAssistantRunStarted } from "../lib/assistant-activity";
import { getDocByPath } from "../lib/doc-helpers";
import { GUIDE_ROUTE_STEPS, setGuideHidden } from "../lib/guide-flow";
import { HARNESS_ARCHITECTURE_TREE } from "../lib/architecture-tree";
import type { DocRecordV1, ProjectStatusHistoryResponseV1, ProjectStatusReportV1, ServiceInventoryRowV1 } from "../lib/contracts";
import { formatPercent, loadBuilderStatus, loadProjectStatusHistory, loadProjectStatusReport, runAssistantAction } from "../lib/loaders";
import {
  isOverviewManagerProject,
  OVERVIEW_MANAGER_PROJECT_LABEL,
  OVERVIEW_PROJECT_CHANGE_EVENT,
  readOverviewActiveProject,
  writeOverviewActiveProject,
} from "../lib/overview-project";
import { useTracker } from "../lib/tracker-context";
import { useGuideState } from "../lib/use-guide-state";

const OVERVIEW_AGENT_ACTIONS = [
  {
    id: "commission_next_phase",
    label: "Commission Next Phase",
    route: "/phases",
    tooltip: "Ask the connected CLI to assess the current board and draft the next commissioning step.",
    quickViewTitle: "What this will do",
    quickViewBody:
      "Reviews the current phase board, loop state, and active objective trail, then commissions the next phase-level move for the operator to review.",
    quickViewList: [
      "assess completed vs pending phases and stages",
      "identify the next commission-ready phase or gate",
      "return a scoped next-phase action plan instead of freeform brainstorming",
    ],
    routeLabel: "Open Phases",
  },
  {
    id: "update",
    label: "Update",
    route: "/review",
    tooltip: "Launch an update-loop prompt through the selected CLI using the current harness context.",
    quickViewTitle: "What this will do",
    quickViewBody:
      "Runs an update-focused prompt that asks the CLI to propose the next bounded implementation update, expected artifacts, and the checks to run before approval.",
    quickViewList: [
      "review current objective, review queue, and changelog pressure",
      "propose the next update artifact path and scope",
      "return a deterministic command/check sequence for the operator",
    ],
    routeLabel: "Open Review Hub",
  },
  {
    id: "upgrade",
    label: "Upgrade",
    route: "/exchange",
    tooltip: "Route upgrade work through the connected CLI with the current tech-debt and governance context.",
    quickViewTitle: "What this will do",
    quickViewBody:
      "Runs an upgrade review prompt focused on platform or harness improvements that should be triaged before the next implementation loop.",
    quickViewList: [
      "evaluate open upgrade candidates and deferrals",
      "separate upgrade-next-cycle work from post-beta debt",
      "return the recommended upgrade route and evidence to capture",
    ],
    routeLabel: "Open Activity",
  },
  {
    id: "tooling",
    label: "Tooling",
    route: "/features",
    tooltip: "Trigger a tooling-loop prompt focused on token economy, command surfaces, linting, testing, and build flow.",
    quickViewTitle: "What this will do",
    quickViewBody:
      "Runs a tooling pass through the selected CLI so it can suggest command-first improvements that reduce token waste and keep verification fast.",
    quickViewList: [
      "review make/uv/npm/python/script surfaces",
      "identify token-heavy workflows that should become short commands",
      "return repo-native tooling recommendations, not generic package churn",
    ],
    routeLabel: "Open Features",
  },
] as const;

function dedupeServiceRows(rows: ServiceInventoryRowV1[]) {
  const byService = new Map<string, ServiceInventoryRowV1>();
  for (const row of rows) {
    const existing = byService.get(row.service);
    if (!existing || existing.status !== "implemented") {
      byService.set(row.service, row);
    }
  }
  return Array.from(byService.values()).sort((left, right) => left.service.localeCompare(right.service));
}

function groupByDomain(rows: ServiceInventoryRowV1[]) {
  const grouped = new Map<string, ServiceInventoryRowV1[]>();
  for (const row of rows) {
    const bucket = grouped.get(row.domain) ?? [];
    bucket.push(row);
    grouped.set(row.domain, bucket);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

export function OverviewPage() {
  const { snapshot, settings, status } = useTracker();
  const guideState = useGuideState();
  const [activeProject, setActiveProject] = useState(() => readOverviewActiveProject());
  const [projectReport, setProjectReport] = useState<ProjectStatusReportV1 | null>(null);
  const [projectHistory, setProjectHistory] = useState<ProjectStatusHistoryResponseV1 | null>(null);
  const [projectOverviewBusy, setProjectOverviewBusy] = useState(false);
  const [projectOverviewError, setProjectOverviewError] = useState("");
  const [assistantBusyAction, setAssistantBusyAction] = useState("");
  const [assistantStatus, setAssistantStatus] = useState("");
  const [assistantArtifactLinks, setAssistantArtifactLinks] = useState<Array<{ label: string; path: string }>>([]);

  useEffect(() => {
    const syncProject = () => {
      startTransition(() => {
        setActiveProject(readOverviewActiveProject());
      });
    };

    window.addEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
    window.addEventListener("storage", syncProject);
    return () => {
      window.removeEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
      window.removeEventListener("storage", syncProject);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const nextBuilderStatus = await loadBuilderStatus();
      if (cancelled) {
        return;
      }
      const knownRepos = nextBuilderStatus?.known_repos ?? [];
      const storedSelection = readOverviewActiveProject();
      const nextSelection =
        isOverviewManagerProject(storedSelection) || storedSelection.length === 0
          ? storedSelection
          : knownRepos.find((repo) => repo.name === storedSelection)?.name ?? "";
      writeOverviewActiveProject(nextSelection);
      startTransition(() => {
        setActiveProject(nextSelection);
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const activeProjectValue = activeProject.trim();
    if (!activeProjectValue || isOverviewManagerProject(activeProjectValue)) {
      setProjectReport(null);
      setProjectHistory(null);
      setProjectOverviewBusy(false);
      setProjectOverviewError("");
      return;
    }
    void (async () => {
      setProjectOverviewBusy(true);
      setProjectOverviewError("");
      const [report, history] = await Promise.all([
        loadProjectStatusReport({ target_repo: activeProjectValue }),
        loadProjectStatusHistory({ target_repo: activeProjectValue, limit: 6 }),
      ]);
      if (cancelled) {
        return;
      }
      setProjectOverviewBusy(false);
      if (!report) {
        setProjectReport(null);
        setProjectHistory(history);
        setProjectOverviewError("Overview data is unavailable for the selected project. Run Builder or Project Status to generate harness signals.");
        return;
      }
      setProjectReport(report);
      setProjectHistory(history);
    })();
    return () => {
      cancelled = true;
    };
  }, [activeProject]);

  useEffect(() => {
    setAssistantStatus("");
    setAssistantArtifactLinks([]);
  }, [activeProject]);

  if (!snapshot) {
    return <div className="card card-pad">No snapshot data found. Run sync and refresh.</div>;
  }

  const completedPhases = snapshot.phases.phases.filter((phase) => phase.phase_status === "completed").length;
  const phaseCompletion = snapshot.phases.stage_count === 0 ? 0 : snapshot.phases.stage_done_count / snapshot.phases.stage_count;
  const recentChanges = snapshot.git.markdown_changed_files.slice(0, 12);
  const policyTop = snapshot.policies.domains.slice(0, 8);
  const objectivePreview = snapshot.project_overview.active_objectives.slice(0, 3);
  const existingPaths = new Set(snapshot.docs.map((doc) => doc.relative_path));
  const serviceRows = dedupeServiceRows(snapshot.service_inventory.rows);
  const implementedServices = serviceRows.filter((row) => row.status === "implemented");
  const awaitingServices = serviceRows.filter((row) => row.status === "planned_only");

  const keyDocs = [
    "docs/engineer_entry/index.md",
    "docs/00_overview/engineer_entrypoint.md",
    "docs/11_ops/quick_start.md",
    "docs/entrypoint_guide/index.md",
    "docs/00_overview/implementation_phases.md",
    "docs/03_architecture/container_topology.md",
    "docs/11_ops/codex_run_loop.md",
    "docs/11_ops/archive_process.md",
    "Harness/artifacts/control/archive_register.md",
    "docs/15_checklists/agent_cycle_gate.md",
  ]
    .map((path) => getDocByPath(snapshot, path))
    .filter((doc): doc is DocRecordV1 => doc !== null);

  const blueprintDocs = [
    "docs/00_overview/architecture.md",
    "docs/00_overview/implementation_phases.md",
    "docs/00_overview/service_catalog.md",
    "docs/03_architecture/container_topology.md",
  ]
    .map((path) => getDocByPath(snapshot, path))
    .filter((doc): doc is DocRecordV1 => doc !== null);

  const nextGuideStep = GUIDE_ROUTE_STEPS[0] ?? null;
  const showIntroCard = !guideState.hidden && !guideState.completed;
  const selectionMode = !activeProject.trim() ? "none" : isOverviewManagerProject(activeProject) ? "manager" : "external";
  const hasProjectTarget = selectionMode !== "none";
  const targetLabel =
    selectionMode === "manager" ? OVERVIEW_MANAGER_PROJECT_LABEL : selectionMode === "external" ? activeProject : "No Project Selected";
  const latestProjectEntry = projectHistory?.entries[0] ?? null;
  const assistantRuntime = status?.assistant_runtimes?.[settings.preferredAssistant] ?? null;
  const assistantRegistered = assistantRuntime?.availability_status === "available";
  const assistantLabel = settings.preferredAssistant === "claude_code" ? "Claude Code CLI" : "Codex CLI";
  const externalActionCount = projectReport?.summary.action_total ?? 0;
  const externalCriticalCount = projectReport?.summary.critical_count ?? 0;
  const externalHighCount = projectReport?.summary.high_count ?? 0;
  const externalHealthyDomains = projectReport?.domain_health.filter((domain) => domain.status === "healthy").length ?? 0;

  const assistantActionPrompts = useMemo(() => {
    const projectLine =
      selectionMode === "manager"
        ? `active_project=${OVERVIEW_MANAGER_PROJECT_LABEL}`
        : selectionMode === "external"
          ? `active_project=${activeProject}`
          : "active_project=none";
    const projectStatusLine = latestProjectEntry ? `active_project_status=${latestProjectEntry.overall_status}` : "active_project_status=unknown";
    const baseLines = [
      "You are operating inside Moradins Harness.",
      "Return a concise operator-ready response.",
      "Do not assume permission to mutate the repo automatically.",
      "",
      `repo_branch=${snapshot.git.branch}`,
      `last_cycle=${snapshot.loop_state.last_run_id}`,
      `halt_reason=${snapshot.loop_state.halt_reason}`,
      `next_action=${snapshot.loop_state.next_action}`,
      `phases_completed=${completedPhases}/${snapshot.phases.phase_count}`,
      `stages_completed=${snapshot.phases.stage_done_count}/${snapshot.phases.stage_count}`,
      `pending_review_total=${snapshot.human_review_summary.pending_total}`,
      projectLine,
      projectStatusLine,
    ];
    return {
      commission_next_phase: [
        "Commission the next phase for this project.",
        "Assess the current phase board, identify the next commissionable phase/stage move, and return the recommended commission scope, required artifacts, and operator checks.",
        "",
        ...baseLines,
      ].join("\n"),
      update: [
        "Run the update loop for this project.",
        "Recommend the highest-value update action to perform next, including the expected update artifact, scoped implementation target, and verification commands.",
        "",
        ...baseLines,
      ].join("\n"),
      upgrade: [
        "Run the upgrade loop for this project.",
        "Review upgrade candidates and tech-debt pressure, then return the best next upgrade action, route decision, and evidence the operator should capture.",
        "",
        ...baseLines,
      ].join("\n"),
      tooling: [
        "Run the tooling loop for this project.",
        "Focus on token-efficient command surfaces, repo-native scripts, lint/test/build ergonomics, and CLI workflows that reduce wasted context.",
        "",
        ...baseLines,
      ].join("\n"),
    };
  }, [
    activeProject,
    completedPhases,
    latestProjectEntry,
    selectionMode,
    snapshot.git.branch,
    snapshot.human_review_summary.pending_total,
    snapshot.loop_state.halt_reason,
    snapshot.loop_state.last_run_id,
    snapshot.loop_state.next_action,
    snapshot.phases.phase_count,
    snapshot.phases.stage_count,
    snapshot.phases.stage_done_count,
  ]);

  async function onRunOverviewAction(actionId: (typeof OVERVIEW_AGENT_ACTIONS)[number]["id"]) {
    if (!hasProjectTarget) {
      setAssistantStatus("Select a project first.");
      return;
    }
    setAssistantBusyAction(actionId);
    setAssistantStatus("");
    setAssistantArtifactLinks([]);
    const response = await runAssistantAction({
      assistant: settings.preferredAssistant,
      source_mode: "docs",
      prompt: assistantActionPrompts[actionId],
      execution_scope: selectionMode === "external" ? "local_repo" : "manager_repo",
      target_repo: selectionMode === "external" ? activeProject : undefined,
    });
    setAssistantBusyAction("");
    if (!response) {
      setAssistantStatus("Assistant run failed.");
      return;
    }
    notifyAssistantRunStarted(response.run_id);
    const actionLabel = OVERVIEW_AGENT_ACTIONS.find((action) => action.id === actionId)?.label ?? "Action";
    setAssistantStatus(
      response.status === "queued" || response.status === "running"
        ? `${actionLabel}: ${response.assistant} started. Follow progress in Assistant Activity.`
        : `${actionLabel}: ${response.assistant} exit=${response.exit_code ?? "pending"} status=${response.status}`,
    );
    setAssistantArtifactLinks([
      { label: "Run JSON", path: response.artifact_paths.json },
      { label: "Run Markdown", path: response.artifact_paths.markdown },
    ]);
  }

  const operatorActionsSection = (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <div className="overview-action-head">
        <div>
          <h2 className="section-title" style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <span>Operator Actions</span>
            <TooltipHint text="Launch a connected CLI prompt for the next commission, update, upgrade, or tooling loop without leaving Overview." />
          </h2>
          <p className="section-subtitle" style={{ marginBottom: 0 }}>
            {hasProjectTarget
              ? `One-click loop prompts for ${targetLabel}, with quick-view context before you launch deeper work.`
              : "Select a project from the header switcher to enable project-scoped loop prompts."}
          </p>
        </div>
        <GlassPopover
          ariaLabel={`${assistantLabel} runtime status`}
          align="end"
          preferredWidth={340}
          triggerClassName={`overview-cli-indicator ${assistantRegistered ? "active" : "inactive"}`.trim()}
          trigger={
            <span className="overview-cli-indicator-inner">
              <Activity size={15} strokeWidth={2.2} />
              <span>{assistantRegistered ? `${assistantLabel} active` : `${assistantLabel} not registered`}</span>
            </span>
          }
        >
          <div className="overview-cli-popover">
            <p className="card-head" style={{ marginTop: 0 }}>Connected CLI</p>
            <p className="metric-sub" style={{ marginTop: "0.3rem" }}>
              {assistantRegistered
                ? `${assistantLabel} is available on the Linux host running this harness.`
                : `${assistantLabel} is not available yet on the Linux host running this harness.`}
            </p>
            <p className="metric-sub" style={{ marginTop: "0.55rem" }}>
              {assistantRuntime?.detail ?? "Runtime availability has not been loaded yet."}
            </p>
            <p className="metric-sub mono" style={{ marginTop: "0.55rem", wordBreak: "break-word" }}>
              {assistantRuntime?.terminal_command_template ?? "Configure the preferred assistant in Settings and ensure the CLI binary is installed on this Linux host."}
            </p>
            <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
              <Link to="/settings" className="btn primary" style={{ textDecoration: "none" }}>
                Open Settings
              </Link>
              {!assistantRegistered ? (
                <span className="chip warning">Install CLI + refresh status</span>
              ) : (
                <span className="chip success">Registered and ready</span>
              )}
            </div>
          </div>
        </GlassPopover>
      </div>

      <div className="overview-action-grid">
        {OVERVIEW_AGENT_ACTIONS.map((action) => (
          <article key={action.id} className="card card-pad overview-action-card">
            <div className="overview-action-card-head">
              <div style={{ minWidth: 0 }}>
                <p className="card-head" style={{ display: "flex", alignItems: "center", gap: "0.35rem", margin: 0 }}>
                  <span>{action.label}</span>
                  <TooltipHint text={action.tooltip} />
                </p>
              </div>
              <GlassPopover
                ariaLabel={`${action.label} quick view`}
                align="end"
                preferredWidth={320}
                triggerClassName="overview-action-more"
                trigger={<MoreHorizontal size={17} strokeWidth={2.1} aria-hidden="true" />}
              >
                {({ close }) => (
                  <div className="overview-action-popover">
                    <p className="card-head" style={{ marginTop: 0 }}>{action.quickViewTitle}</p>
                    <p className="metric-sub" style={{ marginTop: "0.3rem" }}>{action.quickViewBody}</p>
                    <ul className="overview-action-popover-list">
                      {action.quickViewList.map((entry) => (
                        <li key={`${action.id}:${entry}`} className="muted">
                          {entry}
                        </li>
                      ))}
                    </ul>
                    <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
                      <Link
                        to={action.route}
                        className="btn"
                        style={{ textDecoration: "none" }}
                        onClick={() => {
                          close();
                        }}
                      >
                        {action.routeLabel}
                      </Link>
                      <button
                        className="btn primary"
                        type="button"
                        disabled={!assistantRegistered || !hasProjectTarget || assistantBusyAction.length > 0}
                        onClick={() => {
                          close();
                          void onRunOverviewAction(action.id);
                        }}
                      >
                        Run with {assistantLabel}
                      </button>
                    </div>
                  </div>
                )}
              </GlassPopover>
            </div>
            <div className="overview-action-buttons">
              <button
                className="btn primary overview-action-btn"
                type="button"
                disabled={!assistantRegistered || !hasProjectTarget || assistantBusyAction.length > 0}
                onClick={() => void onRunOverviewAction(action.id)}
              >
                {assistantBusyAction === action.id ? `Running ${action.label}...` : action.label}
              </button>
              <Link to={action.route} className="btn overview-action-btn" style={{ textDecoration: "none" }}>
                {action.routeLabel}
              </Link>
            </div>
            {!hasProjectTarget ? (
              <p className="overview-action-disabled-note">Select a project from the header to enable this action.</p>
            ) : null}
          </article>
        ))}
      </div>
      {assistantStatus ? (
        <p className="metric-sub" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
          {assistantStatus}
        </p>
      ) : null}
      {assistantArtifactLinks.length ? (
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
          {assistantArtifactLinks.map((artifact) => (
            <a
              key={`${artifact.label}:${artifact.path}`}
              className="btn"
              href={artifact.path}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              {artifact.label}
            </a>
          ))}
        </div>
      ) : null}
    </section>
  );

  return (
    <div className="page-grid">
      {showIntroCard ? (
        <section className="card card-pad" style={{ gridColumn: "span 12", borderColor: "rgba(34, 197, 94, 0.4)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.9rem", flexWrap: "wrap", alignItems: "flex-start" }}>
            <div>
              <p className="card-head">First-Run Guide</p>
              <h3 style={{ marginTop: "0.3rem", marginBottom: "0.35rem" }}>Use the guided path instead of jumping through disconnected pages.</h3>
              <p className="section-subtitle" style={{ marginBottom: 0 }}>
                Start in Quick Start, then move to Deploy Map, Builder, and System Status in that order.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <Link to="/deploy/quick-start" className="btn primary" style={{ textDecoration: "none" }}>
                Start Guided Setup
              </Link>
              <Link to="/deploy/map" className="btn" style={{ textDecoration: "none" }}>
                Deploy Map
              </Link>
              <Link to="/deploy/builder" className="btn" style={{ textDecoration: "none" }}>
                Builder
              </Link>
              <Link to="/settings/system" className="btn" style={{ textDecoration: "none" }}>
                System Status
              </Link>
                <button
                  className="btn subtle"
                  type="button"
                  onClick={() => {
                    setGuideHidden(true);
                  }}
                >
                Hide Intro for Now
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <PageHero
        title="Overview"
        eyebrow="Quick View"
        chips={
          selectionMode === "manager" ? (
            <>
              <StatusChip tone="info">{`${snapshot.summary.docs_total} indexed docs`}</StatusChip>
              <StatusChip tone="success">{`${completedPhases}/${snapshot.phases.phase_count} phases completed`}</StatusChip>
              <StatusChip tone={snapshot.git.dirty ? "warning" : "success"}>{snapshot.git.dirty ? "Working tree dirty" : "Working tree clean"}</StatusChip>
            </>
          ) : selectionMode === "external" ? (
            <>
              <StatusChip tone={projectReport?.summary.overall_status === "ready" ? "success" : projectReport?.summary.overall_status === "attention" ? "warning" : "error"}>
                {projectReport ? `status ${projectReport.summary.overall_status}` : "status pending"}
              </StatusChip>
              <StatusChip tone={externalCriticalCount > 0 ? "error" : externalHighCount > 0 ? "warning" : "success"}>
                {projectReport ? `${externalActionCount} actions queued` : "loading project signals"}
              </StatusChip>
              <StatusChip tone="info">{targetLabel}</StatusChip>
            </>
          ) : (
            <StatusChip tone="warning">Select a project target to load overview data</StatusChip>
          )
        }
        actions={
          <Link to={selectionMode === "none" ? "/deploy/builder" : "/deploy/map"} className="btn" style={{ textDecoration: "none" }}>
            {selectionMode === "none" ? "Open Builder" : "Open Deploy Map"}
          </Link>
        }
      >
        {selectionMode === "manager" ? (
          <div className="page-hero-inline-grid">
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Current Objective</p>
              <p style={{ margin: "0.35rem 0 0" }}>{objectivePreview[0]?.goal ?? "No active objective recorded."}</p>
            </div>
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Guide Status</p>
              <p style={{ margin: "0.35rem 0 0" }}>
                {guideState.completed ? "Guided setup completed." : guideState.hidden ? "Guide hidden for now." : "Guide active and ready."}
              </p>
            </div>
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Next Suggested Step</p>
              <p style={{ margin: "0.35rem 0 0" }}>
                {nextGuideStep ? `${nextGuideStep.label}: ${nextGuideStep.description}` : "Open Quick Start to begin the guided path."}
              </p>
            </div>
          </div>
        ) : selectionMode === "external" ? (
          <div className="page-hero-inline-grid">
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Target Repo</p>
              <p style={{ margin: "0.35rem 0 0" }}>{targetLabel}</p>
            </div>
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Harness Signal</p>
              <p style={{ margin: "0.35rem 0 0" }}>
                {projectReport ? `${projectReport.summary.action_total} action(s) and ${projectReport.domain_health.length} domain checks loaded.` : "Loading project harness signal."}
              </p>
            </div>
            <div className="card card-pad page-hero-inline-card">
              <p className="card-head">Next Suggested Step</p>
              <p style={{ margin: "0.35rem 0 0" }}>
                {projectOverviewError
                  ? projectOverviewError
                  : projectReport?.critical_focus[0] ?? "Open Project Status to inspect the selected repo in detail."}
              </p>
            </div>
          </div>
        ) : (
          <div className="page-hero-inline-grid">
            <div className="card card-pad page-hero-inline-card" style={{ gridColumn: "1 / -1" }}>
              <p className="card-head">Select a Target</p>
              <p style={{ margin: "0.35rem 0 0" }}>
                Overview only loads project data after you explicitly target a repo. Use the header switcher to inspect this deployer or another tracked project.
              </p>
            </div>
          </div>
        )}
      </PageHero>

      {selectionMode === "manager" ? (
        <>
          <section className="overview-manager-metric-grid">
            <MagicTile reducedMotion={settings.reducedMotion}>
              <p className="card-head">Docs Indexed</p>
              <p className="metric">{snapshot.summary.docs_total}</p>
              <p className="metric-sub">
                {snapshot.summary.docs_human_owned_context} human-owned context | {snapshot.summary.docs_system_managed} system-managed docs | {snapshot.summary.docs_generated} generated docs
              </p>
              <Link to="/docs?section=engineer_entry&mode=contextual" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                Open Engineer Entry Docs
              </Link>
            </MagicTile>

            <MagicTile reducedMotion={settings.reducedMotion}>
              <p className="card-head">Phase Progress</p>
              <p className="metric">{formatPercent(phaseCompletion)}</p>
              <p className="metric-sub" style={{ marginTop: "-0.15rem" }}>
                complete
              </p>
              <div className="overview-progress-stack">
                <div className="overview-progress-block">
                  <p className="overview-progress-count">{`Phases ${completedPhases}/${snapshot.phases.phase_count}`}</p>
                  <PhaseProgressDots phases={snapshot.phases.phases} />
                </div>
                <div className="overview-progress-block">
                  <p className="overview-progress-count">{`Stages ${snapshot.phases.stage_done_count}/${snapshot.phases.stage_count}`}</p>
                  <StageProgressDots
                    completed={snapshot.phases.stage_done_count}
                    total={snapshot.phases.stage_count}
                    percentLabel={formatPercent(phaseCompletion)}
                  />
                </div>
              </div>
              <Link to="/phases" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                Open Phases
              </Link>
            </MagicTile>

            <MagicTile reducedMotion={settings.reducedMotion}>
              <p className="card-head">Loop Runs</p>
              <p className="metric">{snapshot.loop_state.run_count}</p>
              <p className="metric-sub">Last run: {snapshot.loop_state.last_run_id}</p>
              <Link to="/cycles" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                Open Loop State
              </Link>
            </MagicTile>

            <MagicTile reducedMotion={settings.reducedMotion}>
              <p className="card-head">Capability Gaps</p>
              <p className="metric">{snapshot.capability_gaps.open_count}</p>
              <p className="metric-sub">Open | {snapshot.capability_gaps.in_progress_count} in progress</p>
              <Link to="/cycles" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                Review Gap Status
              </Link>
            </MagicTile>

            <MagicTile reducedMotion={settings.reducedMotion}>
              <p className="card-head">Current Features</p>
              <p className="metric">{snapshot.current_features.implemented_count}</p>
              <p className="metric-sub">implemented | {snapshot.current_features.pending_count} pending</p>
              <Link to="/features" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                Open Features
              </Link>
            </MagicTile>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title" style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
              <span>Project Blueprint</span>
              <TooltipHint text="Project mission, objective focus, and service-coverage status." />
            </h2>
            <p className="section-subtitle">Mission, objectives, and deploy coverage, with drill-ins for catalog targets and implementation state.</p>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginTop: "0.85rem" }}>
              <article className="card card-pad">
                <p className="card-head">Mission</p>
                <p style={{ margin: "0.4rem 0 0" }}>{snapshot.project_overview.mission}</p>
              </article>
              <article className="card card-pad">
                <p className="card-head">Objectives</p>
                <p className="metric" style={{ fontSize: "1.2rem" }}>
                  {snapshot.project_overview.active_objective_count}
                </p>
                <p className="metric-sub">active objective blocks</p>
                <ul style={{ margin: "0.55rem 0 0", paddingLeft: "1rem" }}>
                  {objectivePreview.map((objective) => (
                    <li key={objective.objective_id} className="muted">
                      <span className="mono">{objective.objective_id}</span>: {objective.goal}
                    </li>
                  ))}
                </ul>
              </article>
              <article className="card card-pad">
                <p className="card-head">Service Inventory</p>
                <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginTop: "0.45rem" }}>
                  <StatusPillButton
                    tone="info"
                    ariaLabel="Catalog targets"
                    preferredWidth={420}
                    popoverContent={({ close }) => (
                      <div>
                        <p className="card-head" style={{ marginTop: 0 }}>Catalog Targets</p>
                        <p className="metric-sub" style={{ marginTop: "0.3rem" }}>Services currently represented in the catalog target inventory.</p>
                        <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.8rem" }}>
                          {groupByDomain(serviceRows).map(([domain, rows]) => (
                            <div key={domain}>
                              <strong style={{ textTransform: "capitalize" }}>{domain}</strong>
                              <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.45rem" }}>
                                {rows.map((row) => (
                                  <Link
                                    key={`${domain}-${row.service}`}
                                    to={`/project-topology?status=all&service=${encodeURIComponent(row.service)}`}
                                    className="chip-link"
                                    style={{ textDecoration: "none" }}
                                    onClick={close}
                                  >
                                    {row.service}
                                  </Link>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.85rem" }}>
                          <Link to="/project-topology?status=all" className="btn" style={{ textDecoration: "none" }} onClick={close}>
                            View Full Inventory
                          </Link>
                        </div>
                      </div>
                    )}
                  >
                    {`Catalog Targets ${snapshot.service_inventory.planned_count}`}
                  </StatusPillButton>
                  <StatusPillButton
                    tone="success"
                    ariaLabel="Implemented services"
                    preferredWidth={360}
                    popoverContent={({ close }) => (
                      <div>
                        <p className="card-head" style={{ marginTop: 0 }}>Implemented Services</p>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.65rem" }}>
                          {implementedServices.map((row) => (
                            <Link
                              key={row.service}
                              to={`/project-topology?status=implemented&service=${encodeURIComponent(row.service)}`}
                              className="chip-link"
                              style={{ textDecoration: "none" }}
                              onClick={close}
                            >
                              {row.service}
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                  >
                    {`Implemented ${snapshot.service_inventory.implemented_count}`}
                  </StatusPillButton>
                  <StatusPillButton
                    tone="warning"
                    ariaLabel="Awaiting implementation"
                    preferredWidth={360}
                    popoverContent={({ close }) => (
                      <div>
                        <p className="card-head" style={{ marginTop: 0 }}>Awaiting Implementation</p>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.65rem" }}>
                          {awaitingServices.map((row) => (
                            <Link
                              key={row.service}
                              to={`/project-topology?status=awaiting&service=${encodeURIComponent(row.service)}`}
                              className="chip-link"
                              style={{ textDecoration: "none" }}
                              onClick={close}
                            >
                              {row.service}
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                  >
                    {`Awaiting Implementation ${snapshot.service_inventory.planned_only_count}`}
                  </StatusPillButton>
                </div>
                <div style={{ marginTop: "0.85rem", display: "flex", justifyContent: "flex-start" }}>
                  <Link to="/project-topology?status=all" className="btn" style={{ textDecoration: "none" }}>
                    Open Project Topology
                  </Link>
                </div>
              </article>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.55rem", marginTop: "0.75rem" }}>
              {blueprintDocs.map((doc) => (
                <Link key={doc.id} to={`/docs/${doc.id}`} className="btn" style={{ textDecoration: "none" }}>
                  {doc.title}
                </Link>
              ))}
            </div>
          </section>

          <ArchitectureTree
            title="Architecture Visibility"
            subtitle="Interactive baseline tree of harness foundations, architecture, governance, and tooling surfaces."
            nodes={HARNESS_ARCHITECTURE_TREE}
            existingPaths={existingPaths}
          />

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title">Mission Control</h2>
            <p className="section-subtitle">Current branch, phase readiness, and governance visibility.</p>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.8rem" }}>
              <div className="card card-pad">
                <p className="card-head">Branch</p>
                <p className="metric mono" style={{ fontSize: "1.05rem" }}>
                  {snapshot.git.branch}
                </p>
                <p className="metric-sub mono">{snapshot.git.last_commit}</p>
                <Link to="/changes" className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
                  Open Git Changes
                </Link>
              </div>
              <div className="card card-pad">
                <p className="card-head">Phase Status</p>
                <p className="metric" style={{ fontSize: "1.1rem" }}>
                  {completedPhases}/{snapshot.phases.phase_count}
                </p>
                <p className="metric-sub">completed phases</p>
              </div>
              <div className="card card-pad">
                <p className="card-head">Working Tree</p>
                <p className="metric" style={{ fontSize: "1.1rem" }}>
                  {snapshot.git.dirty ? "Dirty" : "Clean"}
                </p>
                <p className="metric-sub">{snapshot.git.markdown_changed_count} markdown files changed</p>
              </div>
              <div className="card card-pad">
                <p className="card-head">Archive Records</p>
                <p className="metric" style={{ fontSize: "1.1rem" }}>
                  {snapshot.archive_register.row_count}
                </p>
                <p className="metric-sub">{snapshot.archive_register.upgrade_review_count} upgrade reviews archived</p>
              </div>
            </div>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 6" }}>
            <h2 className="section-title">Policy Domains</h2>
            <p className="section-subtitle">Security, interfaces, storage, retrieval, observability, operations.</p>
            <div style={{ display: "grid", gap: "0.6rem", marginTop: "0.75rem" }}>
              {policyTop.map((domain) => {
                const hasRisk = domain.missing_owner_count > 0 || domain.missing_status_count > 0 || domain.stale_review_count > 0;
                const domainPath = `/policies?domain=${encodeURIComponent(domain.domain)}`;
                return (
                  <div key={domain.domain} className="card card-pad" style={{ padding: "0.75rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.4rem", alignItems: "center" }}>
                      <strong style={{ textTransform: "capitalize" }}>{domain.domain}</strong>
                      <Link to={domainPath} className="chip-link" aria-label={`Open ${domain.domain} policy domain`}>
                        {hasRisk ? <StatusChip tone="warning">Attention</StatusChip> : <StatusChip tone="success">Healthy</StatusChip>}
                      </Link>
                    </div>
                    <div className="muted" style={{ marginTop: "0.3rem", fontSize: "0.86rem" }}>
                      {domain.doc_count} docs | stale {domain.stale_review_count} | missing owner {domain.missing_owner_count}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 6" }}>
            <h2 className="section-title">Recent Markdown Changes</h2>
            <p className="section-subtitle">Live view of changed docs on current branch.</p>
            <ul style={{ margin: "0.8rem 0 0", paddingLeft: "1rem" }}>
              {recentChanges.length === 0 ? <li className="muted">No markdown changes detected.</li> : null}
              {recentChanges.map((file) => {
                const doc = getDocByPath(snapshot, file);
                return (
                  <li key={file} style={{ marginBottom: "0.35rem" }}>
                    {doc ? (
                      <Link to={`/docs/${doc.id}`} className="mono" style={{ color: "var(--cyan)" }}>
                        {file}
                      </Link>
                    ) : (
                      <span className="mono">{file}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title">Pinned Entry Points</h2>
            <p className="section-subtitle">Quick launch docs for architecture, loop policy, and phase execution.</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.55rem", marginTop: "0.75rem" }}>
              {keyDocs.map((doc) => (
                <Link key={doc.id} to={`/docs/${doc.id}`} className="btn" style={{ textDecoration: "none" }}>
                  {doc.title}
                </Link>
              ))}
            </div>
          </section>
        </>
      ) : selectionMode === "external" ? (
        <>
          <MagicTile reducedMotion={settings.reducedMotion}>
            <p className="card-head">Project Status</p>
            <p className="metric">
              {projectReport ? projectReport.summary.overall_status : projectOverviewBusy ? "..." : "n/a"}
            </p>
            <p className="metric-sub">
              {projectReport ? `${projectReport.summary.action_total} actions | ${projectReport.summary.critical_count} critical` : "Waiting for project harness data."}
            </p>
            <Link to={`/project-status?target=${encodeURIComponent(activeProject)}`} className="btn" style={{ marginTop: "0.75rem", textDecoration: "none" }}>
              Open Project Status
            </Link>
          </MagicTile>

          <MagicTile reducedMotion={settings.reducedMotion}>
            <p className="card-head">Critical Focus</p>
            <p className="metric">{projectReport ? projectReport.critical_focus.length : 0}</p>
            <p className="metric-sub">
              {projectReport?.critical_focus[0] ?? "No critical focus items loaded yet."}
            </p>
          </MagicTile>

          <MagicTile reducedMotion={settings.reducedMotion}>
            <p className="card-head">Domain Health</p>
            <p className="metric">{projectReport ? `${externalHealthyDomains}/${projectReport.domain_health.length}` : "0/0"}</p>
            <p className="metric-sub">healthy domains</p>
          </MagicTile>

          <MagicTile reducedMotion={settings.reducedMotion}>
            <p className="card-head">Status History</p>
            <p className="metric">{projectHistory?.total_entries ?? 0}</p>
            <p className="metric-sub">retained overview snapshots</p>
          </MagicTile>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title">Target Summary</h2>
            <p className="section-subtitle">Selected project harness signals and current readiness.</p>
            {projectOverviewError ? <p style={{ color: "var(--warning)", marginTop: "0.75rem" }}>{projectOverviewError}</p> : null}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.75rem" }}>
              <StatusChip tone="info">{targetLabel}</StatusChip>
              {projectReport ? (
                <>
                  <StatusChip tone={projectReport.summary.overall_status === "ready" ? "success" : projectReport.summary.overall_status === "attention" ? "warning" : "error"}>
                    {projectReport.summary.overall_status}
                  </StatusChip>
                  <StatusChip tone={projectReport.summary.critical_count > 0 ? "error" : "info"}>
                    {`${projectReport.summary.critical_count} critical`}
                  </StatusChip>
                  <StatusChip tone={projectReport.summary.high_count > 0 ? "warning" : "info"}>
                    {`${projectReport.summary.high_count} high`}
                  </StatusChip>
                </>
              ) : null}
            </div>
            <p className="metric-sub" style={{ marginTop: "0.7rem" }}>
              {projectReport?.target_path ? `path: ${projectReport.target_path}` : "Select Project Status to load the full target path and harness report."}
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
              <Link to={`/project-status?target=${encodeURIComponent(activeProject)}`} className="btn primary" style={{ textDecoration: "none" }}>
                Open Project Status
              </Link>
              <Link to="/deploy/builder" className="btn" style={{ textDecoration: "none" }}>
                Open Builder
              </Link>
            </div>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title">Action Queue</h2>
            <p className="section-subtitle">Highest-priority harness and repo actions for the selected target.</p>
            {projectReport?.actions.length ? (
              <div style={{ display: "grid", gap: "0.65rem", marginTop: "0.8rem" }}>
                {projectReport.actions.slice(0, 8).map((action) => (
                  <article key={action.action_id} className="card card-pad" style={{ padding: "0.8rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", alignItems: "flex-start" }}>
                      <div>
                        <strong>{action.title}</strong>
                        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>{action.description}</p>
                      </div>
                      <StatusChip tone={action.severity === "critical" || action.severity === "high" ? "error" : action.severity === "medium" ? "warning" : "info"}>
                        {action.severity}
                      </StatusChip>
                    </div>
                    <div style={{ marginTop: "0.65rem" }}>
                      <Link to={action.route} className="btn" style={{ textDecoration: "none" }}>
                        Open Route
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ marginTop: "0.8rem" }}>
                {projectOverviewBusy ? "Loading project actions..." : "No action queue is available yet for this target."}
              </p>
            )}
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h2 className="section-title">Domain Health</h2>
            <p className="section-subtitle">Harness baseline and project signal health for the selected repo.</p>
            {projectReport?.domain_health.length ? (
              <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.8rem" }}>
                {projectReport.domain_health.map((domain) => (
                  <article key={domain.domain_id} className="card card-pad">
                    <p className="card-head">{domain.label}</p>
                    <div style={{ marginTop: "0.45rem" }}>
                      <StatusChip tone={domain.status === "healthy" ? "success" : domain.status === "attention" ? "warning" : "error"}>
                        {domain.status}
                      </StatusChip>
                    </div>
                    <p className="metric-sub" style={{ marginTop: "0.5rem" }}>{domain.summary}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ marginTop: "0.8rem" }}>
                {projectOverviewBusy ? "Loading project domain health..." : "No domain-health report is available yet."}
              </p>
            )}
          </section>
        </>
      ) : (
        <section className="card card-pad" style={{ gridColumn: "span 12" }}>
          <h2 className="section-title">Select a Project Target</h2>
          <p className="section-subtitle">Overview stays empty until you explicitly choose which harness repo you want to inspect.</p>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
            <article className="card card-pad">
              <p className="card-head">This Deployer</p>
              <p style={{ margin: "0.4rem 0 0" }}>Use the header switcher and select {OVERVIEW_MANAGER_PROJECT_LABEL} to inspect this repo’s harness and governance state.</p>
            </article>
            <article className="card card-pad">
              <p className="card-head">Tracked Project</p>
              <p style={{ margin: "0.4rem 0 0" }}>Choose a tracked repo from the header switcher to load that project’s harness signals and status summary.</p>
            </article>
            <article className="card card-pad">
              <p className="card-head">Add Project</p>
              <p style={{ margin: "0.4rem 0 0" }}>Open Builder to create, import, or register another project before returning to Overview.</p>
            </article>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.9rem" }}>
            <Link to="/deploy/builder" className="btn primary" style={{ textDecoration: "none" }}>
              Open Builder
            </Link>
            <Link to="/deploy/quick-start" className="btn" style={{ textDecoration: "none" }}>
              Open Quick Start
            </Link>
          </div>
        </section>
      )}

      {operatorActionsSection}
    </div>
  );
}
