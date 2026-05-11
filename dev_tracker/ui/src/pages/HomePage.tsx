import { Link } from "react-router-dom";

import { AttentionChip } from "../components/AttentionChip";
import { StatusChip } from "../components/StatusChip";
import { docStatusTone, findActivePlan, findActiveUpgradePackage, findLatestAwaitingApproval } from "../lib/governance-highlights";
import {
  encodeProjectRouteId,
  isOverviewManagerProject,
  OVERVIEW_MANAGER_PROJECT_ID,
  resolveSelectedProjectLabel,
} from "../lib/overview-project";
import { useTracker } from "../lib/tracker-context";
import { useOverviewActiveProject } from "../lib/use-overview-active-project";
import { deriveManagerWorkspaceModel, deriveProjectsWorkspaceModel } from "../lib/workspace-models";

function formatLastOperation(timestamp: string) {
  if (!timestamp) {
    return "No recent operation";
  }
  const value = new Date(timestamp);
  return Number.isNaN(value.getTime()) ? timestamp : value.toLocaleString();
}

export function HomePage() {
  const { snapshot, status, builderStatus, templateStudio, loading } = useTracker();
  const activeProject = useOverviewActiveProject();

  if (loading && !snapshot) {
    return (
      <div className="page-grid">
        <section className="card card-pad route-skeleton-card" style={{ gridColumn: "span 12" }}>
          <div className="route-skeleton-line wide" />
          <div className="route-skeleton-line medium" />
          <div className="route-skeleton-grid">
            <div className="route-skeleton-block" />
            <div className="route-skeleton-block" />
            <div className="route-skeleton-block" />
          </div>
        </section>
      </div>
    );
  }

  if (!snapshot) {
    return <div className="card card-pad">No snapshot data found. Run sync and refresh.</div>;
  }

  const model = deriveManagerWorkspaceModel({ snapshot, status, builderStatus, templateStudio });
  const projectModel = deriveProjectsWorkspaceModel({ snapshot, builderStatus, selectedProject: OVERVIEW_MANAGER_PROJECT_ID });
  const latestOperation = model.recentOperations[0] ?? null;
  const queueById = new Map(model.reviewQueues.map((queue) => [queue.id, queue]));
  const activeUpgradePackage = findActiveUpgradePackage(snapshot);
  const activeUpdatePlan = findActivePlan(snapshot, "docs/exec_plans/updates/active/");
  const activeUpdateDoc = activeUpdatePlan?.primaryDoc ?? null;
  const activeCommissioningPlan = findActivePlan(snapshot, "docs/exec_plans/commissioning/active/");
  const latestAwaitingApproval = findLatestAwaitingApproval(snapshot);
  const updateQueue = queueById.get("updates");
  const upgradeQueue = queueById.get("upgrades");
  const toolingQueue = queueById.get("tooling");
  const currentProjectRepo = (builderStatus?.known_repos ?? []).find((repo) => repo.name === activeProject) ?? null;
  const hasPinnedProject = Boolean(currentProjectRepo);
  const currentProjectLabel = currentProjectRepo?.name ?? resolveSelectedProjectLabel(activeProject);
  const currentProjectDetail = currentProjectRepo
    ? currentProjectRepo.path
    : isOverviewManagerProject(activeProject)
      ? snapshot.repo_root
      : activeProject
        ? "This pinned project is not in the tracked repo list yet."
        : "Choose a project from the header switcher or Projects workspace to pin the deploy target.";
  const attentionItems = projectModel.rows
    .filter((row) => row.health.tone === "warning")
    .map((row) => ({
      label: row.label,
      to: row.scope === "manager" ? "/project/manager/overview" : `/project/${encodeProjectRouteId(row.id)}/overview`,
      detail: row.health.label,
    }));

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div className="home-hero-head">
          <div>
            <p className="card-head">Launchpad</p>
            <h2 className="workspace-header-title" style={{ marginBottom: "0.35rem" }}>
              {hasPinnedProject ? "Continue the current diagnostics path without digging through governance screens." : "Start from a clean Forge support path when no project is selected."}
            </h2>
            <p className="workspace-header-description" style={{ marginBottom: 0 }}>
              {hasPinnedProject
                ? "Keep the selected repo visible, move directly into Builder or Verify, and leave the heavier governance surfaces lower on the page."
                : "Choose a project, open readiness diagnostics, or inspect the latest proof/status before you dive into manager details."}
            </p>
          </div>
          <div className="workspace-header-chips" style={{ marginTop: 0 }}>
            <StatusChip tone={currentProjectRepo ? "success" : activeProject ? "warning" : "info"}>{`current project ${currentProjectLabel}`}</StatusChip>
            <StatusChip tone={model.templateStatus.tone}>{model.templateStatus.label}</StatusChip>
            <StatusChip tone={model.dryRunStatus.tone}>{model.dryRunStatus.label}</StatusChip>
          </div>
        </div>
        <div className="home-launch-grid">
          <article className="home-launch-card">
            <strong>{hasPinnedProject ? "Continue With Current Project" : "Choose Project"}</strong>
            <p className="metric-sub" style={{ marginBottom: 0 }}>
              {hasPinnedProject
                ? `${currentProjectLabel} is pinned and ready for Builder or Verify.`
                : "Pin the target repo first so Builder and Verify inherit the same project context."}
            </p>
            <Link className="btn primary" to={hasPinnedProject ? "/deploy/builder" : "/projects"} style={{ marginTop: "0.85rem" }}>
              {hasPinnedProject ? "Open Builder" : "Open Projects"}
            </Link>
          </article>
          <article className="home-launch-card">
            <strong>Forge Diagnostics</strong>
            <p className="metric-sub" style={{ marginBottom: 0 }}>
              Review readiness, preview a safe example, and move into Deploy Map before execution.
            </p>
            <Link className="btn" to="/deploy/quick-start" style={{ marginTop: "0.85rem" }}>
              Open Diagnostics
            </Link>
          </article>
          <article className="home-launch-card">
            <strong>Latest Proof And Status</strong>
            <p className="metric-sub" style={{ marginBottom: 0 }}>
              Inspect the latest deterministic proof results and the current review gate before changing anything.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
              <Link className="btn" to="/deploy/status">
                Open Verify
              </Link>
              <Link className="btn" to="/reviews/queue">
                Open Review Queue
              </Link>
            </div>
          </article>
        </div>
        {!hasPinnedProject ? (
          <div className="home-zero-state-banner">
            <span className="shell-badge">No project pinned</span>
            <p className="metric-sub" style={{ margin: 0 }}>
              Home now stays focused on first action. Governance summaries, active work, and archive context sit below the operator path instead of leading the page.
            </p>
          </div>
        ) : null}
        {model.attentionProjectCount > 0 ? (
          <div style={{ marginTop: "0.9rem" }}>
            <AttentionChip
              label={`${model.attentionProjectCount} projects need attention`}
              summary="One or more managed workspaces still need review before they are considered stable."
              items={attentionItems}
            />
          </div>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <p className="card-head">Primary Route</p>
        <div style={{ display: "grid", gap: "0.85rem", marginTop: "0.8rem" }}>
          {[
            ["1", "Target repo", currentProjectRepo ? `Reuse ${currentProjectRepo.name} from the pinned project switcher or choose another tracked repo.` : "Choose the repo or sidecar target before prompts or deploy actions."],
            ["2", "Project context", "Capture goal, users, constraints, deployment target, and extra context in one place."],
            ["3", "Deploy harness", "Generate or deploy the harness, then review the resulting artifacts and fill tree."],
            ["4", "Build phases", "Create the phase plan and follow-on prompt bundle from the deployed context."],
            ["5", "Run phase prompt", "Pick Bootstrap Hydration, Build Project Phases, Implement Phase 1, or Run All Phases explicitly."],
          ].map(([step, title, detail]) => (
            <div key={step} style={{ display: "grid", gridTemplateColumns: "2rem minmax(0, 1fr)", gap: "0.75rem", alignItems: "start" }}>
              <span className="shell-badge" style={{ justifyContent: "center" }}>
                {step}
              </span>
              <div>
                <strong style={{ display: "block" }}>{title}</strong>
                <p className="metric-sub" style={{ marginTop: "0.25rem", marginBottom: 0 }}>
                  {detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Current Target</p>
        <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.8rem" }}>
          <div style={{ display: "grid", gap: "0.35rem" }}>
            <span className="metric-sub">Pinned project</span>
            <strong>{currentProjectLabel}</strong>
            <span className="metric-sub mono">{currentProjectDetail}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
            <span className="metric-sub">Tracked repos</span>
            <strong>{model.trackedProjectCount}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
            <span className="metric-sub">Pending approvals</span>
            <strong>{model.pendingApprovals}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
            <span className="metric-sub">Payload version</span>
            <strong>{model.templateVersion}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
            <span className="metric-sub">Open gaps</span>
            <strong>{model.openGaps}</strong>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <Link className="btn" to={currentProjectRepo ? "/deploy/builder" : "/projects"}>
              {currentProjectRepo ? "Use Current Project" : "Select A Project"}
            </Link>
            <Link className="btn" to="/payload">
              Moradin Payload
            </Link>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div className="governance-focus-head">
          <div>
            <p className="card-head">Current Active Work</p>
            <h3 className="governance-focus-title">Find the current package, gate, and next operator route without digging through tables.</h3>
          </div>
            <div className="governance-focus-actions">
              <Link className="btn" to="/docs">
                Open Docs
              </Link>
              <Link className="btn" to="/reviews/queue">
                Open Review Queue
              </Link>
              <Link className="btn" to="/reviews/exchange">
                Open Activity
              </Link>
            </div>
        </div>
        <div className="governance-focus-grid" style={{ marginTop: "0.9rem" }}>
          {activeUpgradePackage?.primaryDoc ? (
            <article className="governance-focus-card">
              <div className="governance-focus-card-top">
                <p className="card-head">Active Upgrade Package</p>
                <StatusChip tone={docStatusTone(activeUpgradePackage.primaryDoc.status)}>{activeUpgradePackage.primaryDoc.status}</StatusChip>
              </div>
              <strong className="governance-focus-card-title">{activeUpgradePackage.primaryDoc.title}</strong>
              <p className="metric-sub">
                {activeUpgradePackage.docs.length} governed docs remain active for the Harness vNext upgrade path.
              </p>
              <p className="governance-focus-path mono">{activeUpgradePackage.primaryDoc.relative_path}</p>
              <div className="governance-focus-chip-row">
                <StatusChip tone={model.pendingApprovals > 0 ? "warning" : "success"}>{`${model.pendingApprovals} pending approvals`}</StatusChip>
                <StatusChip tone="info">{`${upgradeQueue?.actionableDocs ?? 0} upgrade queue items`}</StatusChip>
              </div>
              <div className="governance-focus-actions">
                <Link className="btn" to={`/docs/${activeUpgradePackage.primaryDoc.id}`}>
                  Open Package
                </Link>
                <Link className="btn" to="/reviews/exchange">
                  Open Activity
                </Link>
              </div>
            </article>
          ) : null}

          {activeUpdateDoc ? (
            <article className="governance-focus-card">
              <div className="governance-focus-card-top">
                <p className="card-head">Active Update Cycle</p>
                <StatusChip tone={docStatusTone(activeUpdateDoc.status)}>{activeUpdateDoc.status}</StatusChip>
              </div>
              <strong className="governance-focus-card-title">{activeUpdateDoc.title}</strong>
              <p className="metric-sub">
                Current UI/usability follow-through stays separate from the HUP-0014 package and uses the existing control model.
              </p>
              <p className="governance-focus-path mono">{activeUpdateDoc.relative_path}</p>
              <div className="governance-focus-chip-row">
                <StatusChip tone="info">{`${activeUpdatePlan?.docs.length ?? 0} active update docs`}</StatusChip>
                <StatusChip tone="warning">{`${updateQueue?.actionableDocs ?? 0} update queue items`}</StatusChip>
              </div>
              <div className="governance-focus-actions">
                <Link className="btn" to={`/docs/${activeUpdateDoc.id}`}>
                  Open Update
                </Link>
                <Link
                  className="btn"
                  to={`/docs?section=exec_plans&q=${encodeURIComponent(activeUpdateDoc.title)}`}
                >
                  Filter Docs
                </Link>
              </div>
            </article>
          ) : null}

          {activeCommissioningPlan?.primaryDoc ? (
            <article className="governance-focus-card">
              <div className="governance-focus-card-top">
                <p className="card-head">Active Commissioning Plan</p>
                <StatusChip tone={docStatusTone(activeCommissioningPlan.primaryDoc.status)}>{activeCommissioningPlan.primaryDoc.status}</StatusChip>
              </div>
              <strong className="governance-focus-card-title">{activeCommissioningPlan.primaryDoc.title}</strong>
              <p className="metric-sub">
                Commissioning remains a parallel truth surface so operators can see release-track work beside the vNext planning package.
              </p>
              <p className="governance-focus-path mono">{activeCommissioningPlan.primaryDoc.relative_path}</p>
              <div className="governance-focus-chip-row">
                <StatusChip tone="info">{`${activeCommissioningPlan.docs.length} active commissioning docs`}</StatusChip>
                <StatusChip tone={model.openGaps > 0 ? "warning" : "success"}>{`${model.openGaps} open capability gaps`}</StatusChip>
              </div>
              <div className="governance-focus-actions">
                <Link className="btn" to={`/docs/${activeCommissioningPlan.primaryDoc.id}`}>
                  Open Commissioning
                </Link>
                <Link className="btn" to="/reviews/changes">
                  Open Changes
                </Link>
              </div>
            </article>
          ) : null}

          <article className="governance-focus-card">
            <div className="governance-focus-card-top">
              <p className="card-head">Human Review Gate</p>
              <StatusChip tone={latestAwaitingApproval ? "warning" : "success"}>
                {latestAwaitingApproval ? "awaiting review" : "gate ready"}
              </StatusChip>
            </div>
            <strong className="governance-focus-card-title">
              {latestAwaitingApproval ? latestAwaitingApproval.cycle_id : "All current cycles are approved."}
            </strong>
            <p className="metric-sub">
              {latestAwaitingApproval
                ? latestAwaitingApproval.summary
                : "No pending approval is blocking the next governed cycle."}
            </p>
            <p className="governance-focus-path mono">
              {latestAwaitingApproval ? latestAwaitingApproval.approval_ref : snapshot.human_review_summary.next_action}
            </p>
            <div className="governance-focus-chip-row">
              <StatusChip tone={snapshot.human_review_summary.pending_total > 0 ? "warning" : "success"}>
                {`${snapshot.human_review_summary.pending_total} review items`}
              </StatusChip>
              <StatusChip tone={snapshot.human_review_summary.next_action === "continue" ? "success" : "warning"}>
                {`next action ${snapshot.human_review_summary.next_action}`}
              </StatusChip>
            </div>
            <div className="governance-focus-actions">
              <Link className="btn" to="/reviews/queue">
                Open Gate
              </Link>
              <Link className="btn" to="/reviews/exchange">
                Open Activity
              </Link>
            </div>
          </article>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <details>
          <summary>Manager Status And Queues</summary>
          <div style={{ display: "grid", gap: "0.9rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginTop: "0.9rem" }}>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Current Objective</p>
              <p className="metric" style={{ fontSize: "1.15rem" }}>
                {model.currentObjective}
              </p>
              <p className="metric-sub">In scope: {model.currentObjectiveScope}</p>
            </article>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Next Recommended Action</p>
              <p className="metric" style={{ fontSize: "1.1rem" }}>
                {model.nextAction}
              </p>
              <p className="metric-sub">{model.nextActionDetail}</p>
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
                <StatusChip tone={snapshot.review_queue.pending_total > 0 ? "warning" : "success"}>{`${snapshot.review_queue.pending_total} review items`}</StatusChip>
                <StatusChip tone={snapshot.current_features.pending_count > 0 ? "warning" : "success"}>{`${snapshot.current_features.pending_count} pending features`}</StatusChip>
                <StatusChip tone={snapshot.git.dirty ? "warning" : "info"}>{snapshot.git.dirty ? "Working tree dirty" : "Working tree clean"}</StatusChip>
              </div>
            </article>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Update Queue</p>
              <p className="metric">{updateQueue?.actionableDocs ?? 0}</p>
              <p className="metric-sub">Actionable update artifacts ready for review or execution.</p>
            </article>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Upgrade Queue</p>
              <p className="metric">{upgradeQueue?.actionableDocs ?? 0}</p>
              <p className="metric-sub">Upgrade candidates waiting for the next controlled cycle.</p>
            </article>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Tooling Queue</p>
              <p className="metric">{toolingQueue?.actionableDocs ?? 0}</p>
              <p className="metric-sub">Tooling and token-economy improvements waiting for controlled rollout.</p>
            </article>
            <article className="card card-pad" style={{ padding: "0.9rem" }}>
              <p className="card-head">Runtime And Host</p>
              <p className="metric-sub">{model.runtime.host}</p>
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.65rem" }}>
                <StatusChip tone="info">{`Mode: ${model.runtime.mode}`}</StatusChip>
                <StatusChip tone={model.runtime.ssh === "guarded" ? "success" : "warning"}>{`SSH: ${model.runtime.ssh}`}</StatusChip>
                <StatusChip tone={model.runtime.codex === "available" ? "success" : "warning"}>{`Codex: ${model.runtime.codex}`}</StatusChip>
                <StatusChip tone={model.runtime.claude === "available" ? "success" : "warning"}>{`Claude: ${model.runtime.claude}`}</StatusChip>
              </div>
            </article>
          </div>
        </details>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <details>
          <summary>Recent Manager Activity</summary>
          <div style={{ marginTop: "0.9rem" }}>
            {latestOperation ? (
              <div style={{ display: "grid", gap: "0.5rem" }}>
                <p className="metric" style={{ fontSize: "1.15rem" }}>
                  {latestOperation.action}
                </p>
                <p className="metric-sub">
                  {latestOperation.detail} | {formatLastOperation(latestOperation.timestamp)}
                </p>
                <p className="metric-sub mono">{latestOperation.destination_path}</p>
              </div>
            ) : (
              <p className="metric-sub" style={{ marginTop: 0 }}>
                No recent builder activity was recorded yet.
              </p>
            )}
          </div>
        </details>
      </section>
    </div>
  );
}
