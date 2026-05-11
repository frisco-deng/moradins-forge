import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { AssistantActionBar } from "../components/AssistantActionBar";
import { PageHero } from "../components/PageHero";
import { SeededDeployExamplePanel } from "../components/SeededDeployExamplePanel";
import { StatusChip } from "../components/StatusChip";
import { notifyAssistantRunStarted } from "../lib/assistant-activity";
import { isOverviewManagerProject, resolveSelectedProjectLabel, writeOverviewActiveProject } from "../lib/overview-project";
import type { ProjectStatusHistoryResponseV1, ProjectStatusReportV1, RemoteTargetConfigV1 } from "../lib/contracts";
import { loadProjectStatusHistory, loadProjectStatusReport, runAssistantAction } from "../lib/loaders";
import { useTracker } from "../lib/tracker-context";
import { useOverviewActiveProject } from "../lib/use-overview-active-project";

function toneForSeverity(severity: "critical" | "high" | "medium" | "low"): "error" | "warning" | "info" {
  if (severity === "critical" || severity === "high") {
    return "error";
  }
  if (severity === "medium") {
    return "warning";
  }
  return "info";
}

function toneForDomain(status: "healthy" | "attention" | "risk"): "success" | "warning" | "error" {
  if (status === "healthy") {
    return "success";
  }
  if (status === "attention") {
    return "warning";
  }
  return "error";
}

function toneForOverall(status: "critical" | "attention" | "ready"): "error" | "warning" | "success" {
  if (status === "critical") {
    return "error";
  }
  if (status === "attention") {
    return "warning";
  }
  return "success";
}

function toneForAlignmentItemStatus(
  status: "satisfied" | "manual_required" | "missing" | "deferred",
): "success" | "warning" | "error" | "info" {
  if (status === "satisfied") {
    return "success";
  }
  if (status === "manual_required") {
    return "warning";
  }
  if (status === "missing") {
    return "error";
  }
  return "info";
}

function readRemoteTargetParam(rawValue: string | null): RemoteTargetConfigV1 | undefined {
  if (!rawValue) {
    return undefined;
  }
  try {
    return JSON.parse(rawValue) as RemoteTargetConfigV1;
  } catch {
    return undefined;
  }
}

export function ProjectStatusPage() {
  const location = useLocation();
  const { settings, status, builderStatus } = useTracker();
  const activeProject = useOverviewActiveProject();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const demoMode = params.get("demo") === "seeded";
  const [targetRepo, setTargetRepo] = useState(() => params.get("target") ?? "");
  const [sessionId, setSessionId] = useState(() => params.get("session") ?? "");
  const [targetMode, setTargetMode] = useState<"local" | "remote_ssh">(() =>
    params.get("target_mode") === "remote_ssh" ? "remote_ssh" : "local",
  );
  const [selectedProfileId, setSelectedProfileId] = useState(() => settings.defaultSshProfileId);
  const [remoteTargetOverride, setRemoteTargetOverride] = useState<RemoteTargetConfigV1 | undefined>(() => readRemoteTargetParam(params.get("remote_target")));
  const [report, setReport] = useState<ProjectStatusReportV1 | null>(null);
  const [history, setHistory] = useState<ProjectStatusHistoryResponseV1 | null>(null);
  const [loading, setLoading] = useState(false);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("");
  const [error, setError] = useState("");

  const selectedProfile =
    remoteTargetOverride ??
    settings.sshProfiles.find((profile) => profile.id === selectedProfileId) ??
    undefined;
  const currentSelectedProjectRepo = (builderStatus?.known_repos ?? []).find((repo) => repo.name === activeProject) ?? null;
  const currentSelectedProjectLabel = currentSelectedProjectRepo?.name ?? resolveSelectedProjectLabel(activeProject);
  const currentSelectedProjectDetail = currentSelectedProjectRepo
    ? currentSelectedProjectRepo.path
    : isOverviewManagerProject(activeProject)
      ? "The manager repo is pinned. Choose a tracked project to verify deploy artifacts."
      : activeProject
        ? "The pinned project is not in the tracked repo list yet."
        : "Choose a project from the header switcher or Projects workspace to reuse it here.";
  const assistantRuntime = status?.assistant_runtimes?.[settings.preferredAssistant] ?? null;

  const assistantPrompt = useMemo(() => {
    if (!report) {
      return "";
    }
    const alignmentState = report.alignment_state;
    return [
      "Review this Moradins Harness project status report.",
      "Return a read-only, prioritized action list for the operator.",
      "",
      `target_repo=${report.target_repo}`,
      `target_mode=${report.target_mode ?? "local"}`,
      `overall_status=${report.summary.overall_status}`,
      `critical=${report.summary.critical_count}`,
      `high=${report.summary.high_count}`,
      `medium=${report.summary.medium_count}`,
      `low=${report.summary.low_count}`,
      `action_total=${report.summary.action_total}`,
      `alignment_overall=${alignmentState?.summary.overall_status ?? "unavailable"}`,
      `alignment_manual_required=${alignmentState?.summary.manual_required_count ?? 0}`,
      `alignment_missing=${alignmentState?.summary.missing_count ?? 0}`,
      `alignment_artifact=${alignmentState ? `Harness/artifacts/control/discovery_sessions/${alignmentState.session_id}/alignment_state.md` : "unset"}`,
      `alignment_next_action=${alignmentState?.next_recommended_action?.next_action ?? "none"}`,
      ...report.critical_focus.map((item) => `critical_focus=${item}`),
    ].join("\n");
  }, [report]);

  async function refreshReport(targetOverride = targetRepo.trim()) {
    const requestedTargetRepo = targetOverride.trim();
    if (!requestedTargetRepo) {
      setError("Target repo is required.");
      return;
    }
    if (targetMode === "remote_ssh" && !selectedProfile) {
      setError("Select an SSH profile for remote status.");
      return;
    }
    setLoading(true);
    setError("");
    const nextReport = await loadProjectStatusReport({
      target_repo: requestedTargetRepo,
      session_id: sessionId.trim() || undefined,
      target_mode: targetMode,
      remote_target: targetMode === "remote_ssh" ? selectedProfile : undefined,
    });
    setLoading(false);
    if (!nextReport) {
      setError("Project status report is unavailable. Verify feature flag and target repo.");
      return;
    }
    setReport(nextReport);
    const historyReport = await loadProjectStatusHistory({
      target_repo: requestedTargetRepo,
      target_mode: targetMode,
      remote_target: targetMode === "remote_ssh" ? selectedProfile : undefined,
      limit: 10,
    });
    setHistory(historyReport);
  }

  useEffect(() => {
    if (demoMode) {
      return;
    }
    if (report || loading) {
      return;
    }
    const initialTarget = targetRepo.trim() || currentSelectedProjectRepo?.name || "";
    if (!initialTarget) {
      return;
    }
    if (!targetRepo.trim()) {
      setTargetRepo(initialTarget);
    }
    void refreshReport(initialTarget);
  }, [currentSelectedProjectRepo?.name, demoMode, loading, report, targetRepo]);

  function applyCurrentSelectedProject() {
    if (!currentSelectedProjectRepo) {
      return;
    }
    setTargetRepo(currentSelectedProjectRepo.name);
    writeOverviewActiveProject(currentSelectedProjectRepo.name);
    void refreshReport(currentSelectedProjectRepo.name);
  }

  async function onRunAssistant() {
    if (!assistantPrompt) {
      return;
    }
    setAssistantBusy(true);
    setAssistantStatus("");
    const response = await runAssistantAction({
      assistant: settings.preferredAssistant,
      source_mode: "project_status",
      execution_scope: targetMode === "remote_ssh" ? "manager_repo" : "local_repo",
      prompt: assistantPrompt,
      session_id: sessionId.trim() || undefined,
      target_repo: targetRepo.trim(),
    });
    setAssistantBusy(false);
    if (!response) {
      setAssistantStatus("Assistant run failed.");
      return;
    }
    notifyAssistantRunStarted(response.run_id);
    setAssistantStatus(
      response.status === "queued" || response.status === "running"
        ? `${response.assistant} started. Follow progress in Assistant Activity.`
        : `${response.assistant} exit=${response.exit_code ?? "pending"} status=${response.status}`,
    );
  }

  return (
    <div className="page-grid">
      {demoMode ? (
        <section style={{ gridColumn: "span 12" }}>
          <SeededDeployExamplePanel surface="status" />
          <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
            Preview mode is read-only. Use it to understand the Verify layout and alignment summary before you load a real project report.
          </p>
        </section>
      ) : null}

      <PageHero
        compact
        title="Verify Deploy"
        subtitle="Confirm the current project report, action queue, and follow-on artifact path after the harness deploy completes."
        eyebrow="Deploy Verification"
        chips={
          <>
            <StatusChip tone={currentSelectedProjectRepo ? "success" : activeProject ? "warning" : "info"}>{`current project ${currentSelectedProjectLabel}`}</StatusChip>
            <StatusChip tone={targetRepo.trim() ? "success" : "warning"}>{targetRepo.trim() ? `target ${targetRepo}` : "target pending"}</StatusChip>
            <StatusChip tone={report ? "success" : "info"}>{report ? "status loaded" : "status pending"}</StatusChip>
          </>
        }
        actions={
          <>
            <Link className="btn primary" to="/deploy/builder" style={{ textDecoration: "none" }}>
              Return To Builder
            </Link>
            <Link className="btn" to="/projects" style={{ textDecoration: "none" }}>
              Open Projects
            </Link>
          </>
        }
      >
        <div className="page-hero-inline-grid">
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Current Selected Project</p>
            <p style={{ margin: "0.35rem 0 0" }}>{currentSelectedProjectLabel}</p>
            <p className="metric-sub mono" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
              {currentSelectedProjectDetail}
            </p>
          </div>
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Suggested Check</p>
            <p style={{ margin: "0.35rem 0 0" }}>Confirm project status, artifact history, and the next manual action before running a prompt.</p>
          </div>
        </div>
      </PageHero>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "grid", gap: "0.6rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label className="field-block">
            <span className="field-label">Project Target</span>
            <input className="input" value={targetRepo} onChange={(event) => setTargetRepo(event.target.value)} placeholder="existing-project" />
          </label>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
          <button className="btn" type="button" onClick={applyCurrentSelectedProject} disabled={demoMode || !currentSelectedProjectRepo || loading}>
            Use Current Selected Project
          </button>
          <button className="btn primary" type="button" disabled={demoMode || loading} onClick={() => void refreshReport()}>
            {loading ? "Refreshing..." : "Refresh Status Report"}
          </button>
        </div>
        <details className="builder-advanced" style={{ marginTop: "0.85rem" }}>
          <summary>Advanced: Session And Remote Options</summary>
          <div className="builder-advanced-grid">
            <label className="field-block">
              <span className="field-label">Session Id</span>
              <input className="input mono" value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="disc_..." />
            </label>
            <label className="field-block">
              <span className="field-label">Deploy Location</span>
              <select className="select" value={targetMode} onChange={(event) => setTargetMode(event.target.value === "remote_ssh" ? "remote_ssh" : "local")}>
                <option value="local">Local</option>
                <option value="remote_ssh">Remote SSH</option>
              </select>
            </label>
            {targetMode === "remote_ssh" ? (
              <label className="field-block">
                <span className="field-label">SSH Profile</span>
                <select className="select" value={selectedProfileId} onChange={(event) => setSelectedProfileId(event.target.value)}>
                  <option value="">No profile selected</option>
                  {settings.sshProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
        </details>
        {error ? <p style={{ color: "var(--error)", marginTop: "0.7rem" }}>{error}</p> : null}
      </section>

      {report ? (
        <>
          {report.alignment_state ? (
            <section className="card card-pad" style={{ gridColumn: "span 12" }}>
              <h3 style={{ marginTop: 0 }}>Alignment Summary</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.55rem" }}>
                <StatusChip tone={toneForOverall(report.alignment_state.summary.overall_status)}>{`overall: ${report.alignment_state.summary.overall_status}`}</StatusChip>
                <StatusChip tone="warning">{`manual ${report.alignment_state.summary.manual_required_count}`}</StatusChip>
                <StatusChip tone="error">{`missing ${report.alignment_state.summary.missing_count}`}</StatusChip>
                <StatusChip tone="info">{`next phase ${report.alignment_state.next_recommended_phase_id}`}</StatusChip>
                <StatusChip tone={report.alignment_state.approval_state === "approved" ? "success" : "warning"}>
                  {`approval ${report.alignment_state.approval_state}`}
                </StatusChip>
              </div>
              <p className="metric-sub" style={{ marginTop: "0.6rem" }}>
                goal: {report.alignment_state.locked_project_goal}
              </p>
              <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                {report.alignment_state.next_recommended_action?.next_action ?? "No blocking alignment action remains."}
              </p>
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.9rem" }}>
                <article className="card card-pad" style={{ padding: "0.8rem" }}>
                  <p className="card-head">Source Breakdown</p>
                  <div style={{ display: "grid", gap: "0.3rem", marginTop: "0.55rem" }}>
                    {Object.entries(report.alignment_state.source_breakdown).map(([key, value]) => (
                      <span key={key} className="metric-sub">{`${key}: ${value}`}</span>
                    ))}
                  </div>
                </article>
                <article className="card card-pad" style={{ padding: "0.8rem" }}>
                  <p className="card-head">Next Reviewed Route</p>
                  <p className="metric-sub" style={{ marginTop: "0.55rem" }}>
                    {report.alignment_state.next_recommended_action ? report.alignment_state.next_recommended_action.route : "/deploy/status"}
                  </p>
                </article>
              </div>
            </section>
          ) : null}

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h3 style={{ marginTop: 0 }}>Summary</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.55rem" }}>
              <StatusChip tone={toneForOverall(report.summary.overall_status)}>{`overall: ${report.summary.overall_status}`}</StatusChip>
              <StatusChip tone="error">{`critical ${report.summary.critical_count}`}</StatusChip>
              <StatusChip tone="warning">{`high ${report.summary.high_count}`}</StatusChip>
              <StatusChip tone="warning">{`medium ${report.summary.medium_count}`}</StatusChip>
              <StatusChip tone="info">{`low ${report.summary.low_count}`}</StatusChip>
              <StatusChip tone="info">{`actions ${report.summary.action_total}`}</StatusChip>
            </div>
            <p className="metric-sub" style={{ marginTop: "0.6rem", marginBottom: 0 }}>
              target: {report.target_repo} | mode: {report.target_mode ?? "local"} | path: {report.target_path ?? "n/a"}
            </p>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h3 style={{ marginTop: 0 }}>Critical Focus</h3>
            {report.critical_focus.length > 0 ? (
              <ul style={{ margin: "0.6rem 0 0", paddingLeft: "1rem" }}>
                {report.critical_focus.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No critical focus items detected.</p>
            )}
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <h3 style={{ marginTop: 0 }}>Action Queue</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Action</th>
                  <th>Description</th>
                  <th>Route</th>
                  <th>Depends On</th>
                </tr>
              </thead>
              <tbody>
                {report.actions.map((action) => (
                  <tr key={action.action_id}>
                    <td>
                      <StatusChip tone={toneForSeverity(action.severity)}>{action.severity}</StatusChip>
                    </td>
                    <td>{action.title}</td>
                    <td>{action.description}</td>
                    <td>
                      <Link to={action.route} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                        {action.route}
                      </Link>
                    </td>
                    <td className="mono">{action.depends_on.length > 0 ? action.depends_on.join(", ") : "none"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {report.alignment_state ? (
            <section className="card card-pad" style={{ gridColumn: "span 12" }}>
              <details className="builder-advanced">
                <summary>{`Alignment Items (${report.alignment_state.items.length})`}</summary>
                <table className="table" style={{ marginTop: "0.9rem" }}>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Severity</th>
                      <th>Item</th>
                      <th>Owner</th>
                      <th>Next Action</th>
                      <th>Route</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.alignment_state.items.map((item) => (
                      <tr key={item.item_id}>
                        <td>
                          <StatusChip tone={toneForAlignmentItemStatus(item.status)}>{item.status}</StatusChip>
                        </td>
                        <td>
                          <StatusChip tone={toneForSeverity(item.severity)}>{item.severity}</StatusChip>
                        </td>
                        <td>{item.label}</td>
                        <td>{item.owner}</td>
                        <td>{item.next_action}</td>
                        <td>
                          <Link to={item.recommended_route} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                            {item.recommended_route}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </section>
          ) : null}

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <details className="builder-advanced">
              <summary>{`Domain Health (${report.domain_health.length})`}</summary>
              <div style={{ display: "grid", gap: "0.6rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.9rem" }}>
                {report.domain_health.map((domain) => (
                  <article key={domain.domain_id} className="card card-pad" style={{ padding: "0.75rem" }}>
                    <p className="card-head">{domain.label}</p>
                    <div style={{ marginTop: "0.35rem" }}>
                      <StatusChip tone={toneForDomain(domain.status)}>{domain.status}</StatusChip>
                    </div>
                    <p className="metric-sub" style={{ marginTop: "0.45rem" }}>
                      {domain.summary}
                    </p>
                  </article>
                ))}
              </div>
            </details>
          </section>

          <section className="card card-pad" style={{ gridColumn: "span 12" }}>
            <details className="builder-advanced">
              <summary>{`History (${history?.entries.length ?? 0})`}</summary>
              {history && history.entries.length > 0 ? (
                <table className="table" style={{ marginTop: "0.9rem" }}>
                  <thead>
                    <tr>
                      <th>Generated</th>
                      <th>Overall</th>
                      <th>Critical</th>
                      <th>High</th>
                      <th>Actions</th>
                      <th>Trend (C/H)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.entries.map((entry) => (
                      <tr key={entry.history_id}>
                        <td className="mono">{entry.generated_at}</td>
                        <td>
                          <StatusChip tone={toneForOverall(entry.overall_status)}>{entry.overall_status}</StatusChip>
                        </td>
                        <td>{entry.critical_count}</td>
                        <td>{entry.high_count}</td>
                        <td>{entry.action_total}</td>
                        <td className="mono">
                          {entry.trend.critical_delta >= 0 ? "+" : ""}
                          {entry.trend.critical_delta}/{entry.trend.high_delta >= 0 ? "+" : ""}
                          {entry.trend.high_delta}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
                  No history entries yet. Refresh report to write the first snapshot.
                </p>
              )}
            </details>
          </section>

          <AssistantActionBar
            assistant={settings.preferredAssistant}
            sourceMode="project_status"
            prompt={assistantPrompt}
            disabled={demoMode || !assistantPrompt.trim()}
            busy={assistantBusy}
            statusText={assistantStatus}
            assistantRuntime={assistantRuntime}
            executionHostSummary={status?.ui_access?.execution_host_summary}
            browserAccessSummary={status?.ui_access?.browser_access_summary}
            onPreviewPrompt={() => setAssistantStatus(assistantPrompt)}
            onRunAssistant={onRunAssistant}
          />
        </>
      ) : null}
    </div>
  );
}
