import { Activity, Clock3, ExternalLink, FileText, LoaderCircle, TerminalSquare, XCircle } from "lucide-react";

import { StatusChip } from "./StatusChip";
import type { AssistantRunResponseV1, AssistantRunSummaryV1 } from "../lib/contracts";

function formatRunTime(value: string | undefined): string {
  if (!value) {
    return "n/a";
  }
  try {
    return new Date(value).toLocaleTimeString();
  } catch {
    return value;
  }
}

function formatDuration(durationMs: number | undefined): string {
  if (!Number.isFinite(durationMs ?? NaN) || !durationMs) {
    return "in progress";
  }
  if ((durationMs ?? 0) < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(1)} s`;
}

function toneForRunStatus(status: string): "success" | "warning" | "error" | "info" {
  if (status === "pass") {
    return "success";
  }
  if (status === "fail") {
    return "error";
  }
  if (status === "queued" || status === "running") {
    return "warning";
  }
  return "info";
}

interface AssistantActivityDrawerProps {
  open: boolean;
  loading: boolean;
  runs: AssistantRunSummaryV1[];
  selectedRunId: string;
  selectedRun: AssistantRunResponseV1 | null;
  onClose: () => void;
  onSelectRun: (runId: string) => void;
}

export function AssistantActivityDrawer({
  open,
  loading,
  runs,
  selectedRunId,
  selectedRun,
  onClose,
  onSelectRun,
}: AssistantActivityDrawerProps) {
  const displayedSummary = runs.find((run) => run.run_id === selectedRunId) ?? runs[0] ?? null;
  const displayedRun = selectedRun && selectedRun.run_id === (displayedSummary?.run_id ?? selectedRunId) ? selectedRun : null;
  const displayed = displayedRun ?? displayedSummary;

  return (
    <>
      <button
        type="button"
        className={`assistant-activity-overlay ${open ? "open" : ""}`.trim()}
        aria-label="Close assistant activity"
        onClick={onClose}
      />
      <aside className={`assistant-activity-drawer ${open ? "open" : ""}`.trim()} aria-hidden={!open}>
        <div className="assistant-activity-header">
          <div>
            <p className="card-head" style={{ marginTop: 0 }}>Assistant Activity</p>
            <h2 style={{ margin: "0.2rem 0 0", fontSize: "1.15rem" }}>Observe CLI progress without opening a terminal</h2>
          </div>
          <button type="button" className="icon-btn" aria-label="Close assistant activity" onClick={onClose}>
            <XCircle size={18} />
          </button>
        </div>

        <div className="assistant-activity-body">
          <section className="assistant-activity-panel">
            <div className="assistant-activity-panel-head">
              <div>
                <p className="card-head" style={{ marginTop: 0 }}>Current Run</p>
                <p className="metric-sub" style={{ margin: "0.35rem 0 0" }}>
                  The CLI runs on the Linux host that launched this harness. Full artifacts are written under
                  {" "}
                  <span className="mono">Harness/artifacts/control/assistant_runs</span>.
                </p>
              </div>
              <span className="assistant-activity-panel-icon" aria-hidden="true">
                {loading ? <LoaderCircle className="assistant-spin" size={18} /> : <Activity size={18} />}
              </span>
            </div>

            {displayed ? (
              <div style={{ display: "grid", gap: "0.85rem" }}>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <StatusChip tone={toneForRunStatus(displayed.status)}>
                    {displayed.status === "running" ? "Running" : displayed.status}
                  </StatusChip>
                  {displayed.needs_operator_input ? <StatusChip tone="warning">Question waiting</StatusChip> : null}
                  <StatusChip tone="info">{displayed.stage.replaceAll("_", " ")}</StatusChip>
                  <StatusChip tone="info">{displayed.assistant === "claude_code" ? "Claude Code" : "Codex CLI"}</StatusChip>
                </div>
                <div className="assistant-activity-stats">
                  <div>
                    <span className="metric-sub">Started</span>
                    <strong>{formatRunTime(displayed.started_at)}</strong>
                  </div>
                  <div>
                    <span className="metric-sub">Duration</span>
                    <strong>{formatDuration(displayed.duration_ms)}</strong>
                  </div>
                  <div>
                    <span className="metric-sub">Scope</span>
                    <strong>{displayed.target_repo || "manager repo"}</strong>
                  </div>
                </div>
                <div className="assistant-activity-callout">
                  <TerminalSquare size={16} />
                  <div>
                    <strong>{displayed.detail || "Run state available."}</strong>
                    <p className="metric-sub" style={{ margin: "0.2rem 0 0" }}>
                      Source: {displayed.source_mode.replaceAll("_", " ")}
                    </p>
                    {displayed.execution_context ? (
                      <p className="metric-sub" style={{ margin: "0.2rem 0 0" }}>
                        Pinned repo: {displayed.execution_context.target_label} | cwd {displayed.execution_context.working_directory}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="assistant-activity-actions">
                  <a className="btn" href={displayed.artifact_paths.json} target="_blank" rel="noreferrer">
                    <FileText size={14} />
                    <span>Run JSON</span>
                  </a>
                  <a className="btn" href={displayed.artifact_paths.markdown} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} />
                    <span>Run Markdown</span>
                  </a>
                </div>
                <div className="assistant-activity-log-grid">
                  <section>
                    <p className="card-head">Stdout Tail</p>
                    <pre className="assistant-activity-log">
                      {displayedRun ? displayedRun.stdout_tail || displayedRun.stdout || "No stdout yet." : "Select a run to load live/stdout detail."}
                    </pre>
                  </section>
                  <section>
                    <p className="card-head">Stderr Tail</p>
                    <pre className="assistant-activity-log">
                      {displayedRun ? displayedRun.stderr_tail || displayedRun.stderr || "No stderr." : "Select a run to load live/stderr detail."}
                    </pre>
                  </section>
                </div>
              </div>
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                No assistant activity has been recorded yet.
              </p>
            )}
          </section>

          <section className="assistant-activity-panel">
            <div className="assistant-activity-panel-head">
              <div>
                <p className="card-head" style={{ marginTop: 0 }}>Recent Runs</p>
                <p className="metric-sub" style={{ margin: "0.35rem 0 0" }}>
                  Use this list to reopen the latest CLI attempt, inspect artifacts, or confirm which repo it targeted.
                </p>
              </div>
              <Clock3 size={16} />
            </div>
            {runs.length ? (
              <div className="assistant-activity-run-list">
                {runs.map((run) => (
                  <button
                    key={run.run_id}
                    type="button"
                    className={`assistant-activity-run-row ${run.run_id === (displayed?.run_id ?? selectedRunId) ? "active" : ""}`.trim()}
                    onClick={() => onSelectRun(run.run_id)}
                  >
                    <div>
                      <strong>{run.target_repo || "manager repo"}</strong>
                      <p className="metric-sub" style={{ margin: "0.25rem 0 0" }}>
                        {run.assistant === "claude_code" ? "Claude Code" : "Codex CLI"} | {run.source_mode.replaceAll("_", " ")}
                      </p>
                    </div>
                    <div style={{ display: "grid", justifyItems: "end", gap: "0.35rem" }}>
                      <StatusChip tone={toneForRunStatus(run.status)}>{run.status}</StatusChip>
                      <span className="metric-sub">{formatRunTime(run.started_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ margin: 0 }}>No persisted runs yet.</p>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
