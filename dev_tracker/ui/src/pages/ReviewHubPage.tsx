import { useState } from "react";
import { Link } from "react-router-dom";

import { AssistantActionBar } from "../components/AssistantActionBar";
import { notifyAssistantRunStarted } from "../lib/assistant-activity";
import { StatusChip } from "../components/StatusChip";
import { getDocByPath } from "../lib/doc-helpers";
import { docStatusTone, findActivePlan, findActiveUpgradePackage, findLatestAwaitingApproval } from "../lib/governance-highlights";
import { runAssistantAction } from "../lib/loaders";
import { useTracker } from "../lib/tracker-context";

function severityTone(severity: string): "success" | "warning" | "error" | "info" {
  if (severity === "none") {
    return "success";
  }
  if (severity === "high") {
    return "error";
  }
  if (severity === "medium") {
    return "warning";
  }
  return "info";
}

export function ReviewHubPage() {
  const { snapshot, settings, status } = useTracker();
  const [assistantStatus, setAssistantStatus] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);

  if (!snapshot) {
    return <div className="card card-pad">No review data available.</div>;
  }

  const queueById = Object.fromEntries(snapshot.review_queue.queues.map((queue) => [queue.queue_id, queue]));
  const activeUpgradePackage = findActiveUpgradePackage(snapshot);
  const activeUpdatePlan = findActivePlan(snapshot, "docs/exec_plans/updates/active/");
  const latestAwaitingApproval = findLatestAwaitingApproval(snapshot);
  const noPendingQueueWork =
    snapshot.review_queue.zero_state.updates &&
    snapshot.review_queue.zero_state.upgrades &&
    snapshot.review_queue.zero_state.tooling &&
    snapshot.review_queue.zero_state.suggestions;

  const decisionTone =
    snapshot.human_review_summary.next_action === "continue"
      ? "success"
      : snapshot.human_review_summary.next_action === "pause"
        ? "warning"
        : "error";

  const humanReviewDoc = getDocByPath(snapshot, "HUMAN_REVIEW.md");
  const changelogDoc = getDocByPath(snapshot, "Harness/artifacts/control/changelog.md");
  const gateStatsDoc = getDocByPath(snapshot, "Harness/artifacts/control/human_gate_stats.md");
  const techDebtDoc = getDocByPath(snapshot, "docs/exec_plans/tech-debt-tracker.md");
  const releaseTrackerDoc = getDocByPath(snapshot, "Harness/artifacts/control/release_exit_tracker.md");
  const releaseLatestDoc = getDocByPath(snapshot, "public_audit/release_reports_excluded/latest.md");
  const liveAdoptionDoc = getDocByPath(snapshot, "public_audit/release_reports_excluded/live_adoption.md");
  const seedGenerationDoc = getDocByPath(snapshot, "public_audit/release_reports_excluded/seed_generation.md");
  const sandboxMatrixDoc = getDocByPath(snapshot, "public_audit/release_reports_excluded/sandbox_matrix.md");
  const assistantPrompt = [
    "Review the Moradins Harness human review hub summary.",
    "Recommend the next operator decisions in priority order.",
    "Do not propose automatic implementation actions.",
    "",
    `next_action=${snapshot.human_review_summary.next_action}`,
    `pending_total=${snapshot.human_review_summary.pending_total}`,
    `pending_approvals=${snapshot.review_queue.pending_approvals}`,
    `queue_zero_state=${noPendingQueueWork ? "yes" : "no"}`,
  ].join("\n");

  async function onRunAssistant() {
    setAssistantBusy(true);
    setAssistantStatus("");
    const response = await runAssistantAction({
      assistant: settings.preferredAssistant,
      source_mode: "review",
      execution_scope: "manager_repo",
      prompt: assistantPrompt,
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
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap", alignItems: "center" }}>
          <StatusChip tone={decisionTone}>{`Next Action: ${snapshot.human_review_summary.next_action}`}</StatusChip>
          <StatusChip tone={snapshot.human_review_summary.pending_total > 0 ? "warning" : "success"}>
            {`Pending Items ${snapshot.human_review_summary.pending_total}`}
          </StatusChip>
          <StatusChip tone={snapshot.review_queue.pending_approvals > 0 ? "warning" : "success"}>
            {`Pending Approvals ${snapshot.review_queue.pending_approvals}`}
          </StatusChip>
        </div>
        {noPendingQueueWork ? (
          <p style={{ marginTop: "0.7rem", color: "var(--success)" }}>
            No pending updates/upgrades/tooling suggestions.
          </p>
        ) : (
          <p style={{ marginTop: "0.7rem", color: "var(--warning)" }}>
            Pending queue work exists. Review Activity details before continuing.
          </p>
        )}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div className="governance-focus-card-top">
          <div>
            <p className="card-head">Active Review Focus</p>
            <h3 className="governance-focus-title">Keep the active package, the current update cycle, and the human gate in one scan line.</h3>
          </div>
          <StatusChip tone={snapshot.review_queue.pending_approvals > 0 ? "warning" : "success"}>
            {snapshot.review_queue.pending_approvals > 0 ? "review needed" : "review clear"}
          </StatusChip>
        </div>
        <div className="governance-focus-grid" style={{ marginTop: "0.9rem" }}>
          {activeUpgradePackage?.primaryDoc ? (
            <article className="governance-focus-card">
              <div className="governance-focus-card-top">
                <p className="card-head">Upgrade Package</p>
                <StatusChip tone={docStatusTone(activeUpgradePackage.primaryDoc.status)}>{activeUpgradePackage.primaryDoc.status}</StatusChip>
              </div>
              <strong className="governance-focus-card-title">{activeUpgradePackage.primaryDoc.title}</strong>
              <p className="metric-sub">
                {activeUpgradePackage.docs.length} linked docs remain active for the Harness vNext package and should not be mistaken for archive provenance.
              </p>
              <p className="governance-focus-path mono">{activeUpgradePackage.primaryDoc.relative_path}</p>
              <div className="governance-focus-actions">
                <Link to={`/docs/${activeUpgradePackage.primaryDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
                  Open Package
                </Link>
                <Link to="/reviews/exchange" className="btn" style={{ textDecoration: "none" }}>
                  Open Activity
                </Link>
              </div>
            </article>
          ) : null}

          {activeUpdatePlan?.primaryDoc ? (
            <article className="governance-focus-card">
              <div className="governance-focus-card-top">
                <p className="card-head">Active Update Cycle</p>
                <StatusChip tone={docStatusTone(activeUpdatePlan.primaryDoc.status)}>{activeUpdatePlan.primaryDoc.status}</StatusChip>
              </div>
              <strong className="governance-focus-card-title">{activeUpdatePlan.primaryDoc.title}</strong>
              <p className="metric-sub">
                Cycle 040 keeps the proof lane and the governance-route polish in one review slice so operators can confirm durable evidence before broader UI refinement.
              </p>
              <p className="governance-focus-path mono">{activeUpdatePlan.primaryDoc.relative_path}</p>
              <div className="governance-focus-actions">
                <Link to={`/docs/${activeUpdatePlan.primaryDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
                  Open Update
                </Link>
                <Link to="/reviews/changes" className="btn" style={{ textDecoration: "none" }}>
                  Open Changes
                </Link>
              </div>
            </article>
          ) : null}

          <article className="governance-focus-card">
            <div className="governance-focus-card-top">
              <p className="card-head">Pending Human Gate</p>
              <StatusChip tone={latestAwaitingApproval ? "warning" : "success"}>
                {latestAwaitingApproval ? "awaiting approval" : "no gate blockers"}
              </StatusChip>
            </div>
            <strong className="governance-focus-card-title">
              {latestAwaitingApproval ? latestAwaitingApproval.cycle_id : "All current changelog entries are approved."}
            </strong>
            <p className="metric-sub">
              {latestAwaitingApproval ? latestAwaitingApproval.summary : "Review Hub is ready for the next explicitly commissioned cycle."}
            </p>
            <p className="governance-focus-path mono">
              {latestAwaitingApproval ? latestAwaitingApproval.approval_ref : snapshot.human_review_summary.next_action}
            </p>
            <div className="governance-focus-chip-row">
              <StatusChip tone={snapshot.human_review_summary.pending_total > 0 ? "warning" : "success"}>
                {`${snapshot.human_review_summary.pending_total} review items`}
              </StatusChip>
              <StatusChip tone={decisionTone}>{`next ${snapshot.human_review_summary.next_action}`}</StatusChip>
            </div>
            <div className="governance-focus-actions">
              <Link to="/reviews/queue" className="btn" style={{ textDecoration: "none" }}>
                Stay On Queue
              </Link>
              <Link to="/reviews/exchange" className="btn" style={{ textDecoration: "none" }}>
                Open Activity
              </Link>
            </div>
          </article>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Project Review</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Pending</th>
              <th>Severity</th>
              <th>Route</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.human_review_summary.project_review.map((row) => (
              <tr key={row.review_id}>
                <td>{row.label}</td>
                <td>{row.pending_count}</td>
                <td>
                  <StatusChip tone={severityTone(row.severity)}>{row.severity}</StatusChip>
                </td>
                <td>
                  <Link to={row.route} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                    {row.route}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Harness Review</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Pending</th>
              <th>Severity</th>
              <th>Route</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.human_review_summary.harness_review.map((row) => (
              <tr key={row.review_id}>
                <td>{row.label}</td>
                <td>{row.pending_count}</td>
                <td>
                  <StatusChip tone={severityTone(row.severity)}>{row.severity}</StatusChip>
                </td>
                <td>
                  <Link to={row.route} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                    {row.route}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Queue Detail</h3>
        <div style={{ display: "grid", gap: "0.6rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          {(["updates", "upgrades", "tooling", "suggestions"] as const).map((queueId) => {
            const queue = queueById[queueId];
            return (
              <article key={queueId} className="card card-pad">
                <p className="card-head">{queue?.label ?? queueId}</p>
                <p className="metric" style={{ fontSize: "1.2rem" }}>
                  {queue?.actionable_docs ?? 0}
                </p>
                <p className="metric-sub">{`actionable | ${(queue?.implemented_docs ?? 0).toString()} non-actionable in active path`}</p>
                <Link to="/reviews/exchange" className="btn" style={{ marginTop: "0.6rem", textDecoration: "none" }}>
                  Open Activity
                </Link>
              </article>
            );
          })}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Review Artifacts</h3>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {releaseTrackerDoc ? (
            <Link to={`/docs/${releaseTrackerDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Release Exit Tracker
            </Link>
          ) : null}
          {releaseLatestDoc ? (
            <Link to={`/docs/${releaseLatestDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Latest Release Report
            </Link>
          ) : null}
          {humanReviewDoc ? (
            <Link to={`/docs/${humanReviewDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              HUMAN_REVIEW.md
            </Link>
          ) : null}
          {liveAdoptionDoc ? (
            <Link to={`/docs/${liveAdoptionDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Live Adoption Report
            </Link>
          ) : null}
          {seedGenerationDoc ? (
            <Link to={`/docs/${seedGenerationDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Seed Generation Report
            </Link>
          ) : null}
          {sandboxMatrixDoc ? (
            <Link to={`/docs/${sandboxMatrixDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Sandbox Matrix
            </Link>
          ) : null}
          {changelogDoc ? (
            <Link to={`/docs/${changelogDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Changelog
            </Link>
          ) : null}
          {gateStatsDoc ? (
            <Link to={`/docs/${gateStatsDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Human Gate Stats
            </Link>
          ) : null}
          {techDebtDoc ? (
            <Link to={`/docs/${techDebtDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Tech Debt Tracker
            </Link>
          ) : null}
        </div>
        {snapshot.human_review_summary.notes.length > 0 ? (
          <ul style={{ marginTop: "0.7rem", paddingLeft: "1rem" }}>
            {snapshot.human_review_summary.notes.map((note) => (
              <li key={note} className="muted">
                {note}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <AssistantActionBar
        assistant={settings.preferredAssistant}
        sourceMode="review"
        prompt={assistantPrompt}
        disabled={!assistantPrompt.trim()}
        busy={assistantBusy}
        statusText={assistantStatus}
        assistantRuntime={status?.assistant_runtimes?.[settings.preferredAssistant] ?? null}
        executionHostSummary={status?.ui_access?.execution_host_summary}
        browserAccessSummary={status?.ui_access?.browser_access_summary}
        onPreviewPrompt={() => setAssistantStatus(assistantPrompt)}
        onRunAssistant={onRunAssistant}
      />
    </div>
  );
}
