import { useMemo, useState } from "react";

import type { TrackerSnapshotVLatest } from "../lib/contracts";
import { GlowingEdgeCard } from "./GlowingEdgeCard";
import { StatusChip } from "./StatusChip";

interface Props {
  snapshot: TrackerSnapshotVLatest;
  mode: "dark" | "light";
}

export function ExchangeNodeCard({ snapshot, mode }: Props) {
  const latestGate = snapshot.human_gate_stats?.latest;
  const latestChanges = snapshot.changelog.rows.slice(0, 3);
  const archivedSuggestions = snapshot.archive_register.suggestion_count;
  const updateNotes = snapshot.archive_register.update_count;
  const upgradeReviews = snapshot.archive_register.upgrade_review_count;
  const queueById = Object.fromEntries((snapshot.review_queue?.queues ?? []).map((queue) => [queue.queue_id, queue]));
  const queuedSuggestions =
    queueById.suggestions?.actionable_docs ??
    snapshot.docs.filter(
      (doc) =>
        doc.relative_path.startsWith("docs/exec_plans/implementation/active/sug_") &&
        !doc.relative_path.endsWith("/index.md"),
    ).length;
  const queuedUpdates =
    queueById.updates?.actionable_docs ??
    snapshot.docs.filter(
      (doc) =>
        doc.relative_path.startsWith("docs/exec_plans/updates/active/") &&
        !doc.relative_path.endsWith("/index.md"),
    ).length;
  const queuedUpgrades =
    queueById.upgrades?.actionable_docs ??
    snapshot.docs.filter(
      (doc) =>
        doc.relative_path.startsWith("docs/exec_plans/upgrades/active/") &&
        !doc.relative_path.endsWith("/index.md"),
    ).length;
  const queuedTooling = queueById.tooling?.actionable_docs ?? 0;
  const cycleRemaining = latestGate?.estimated_cycles_remaining ?? snapshot.summary.estimated_cycles_remaining;
  const loopRemaining = latestGate?.estimated_loops_remaining ?? snapshot.summary.estimated_loops_remaining;
  const pendingApprovals = snapshot.review_queue?.pending_approvals ?? snapshot.changelog.awaiting_human_review_count;
  const pendingFeatures = snapshot.current_features.pending_count;
  const openGaps = snapshot.capability_gaps.open_count;
  const noPendingQueueWork =
    queuedUpdates === 0 && queuedUpgrades === 0 && queuedSuggestions === 0 && queuedTooling === 0;
  const [reviewChecks, setReviewChecks] = useState<Record<string, boolean>>({});

  const queueChecklist = useMemo(
    () => [
      { id: "updates", label: `Update notes queue reviewed (${queuedUpdates} queued)` },
      { id: "upgrades", label: `Upgrade review queue reviewed (${queuedUpgrades} queued)` },
      { id: "suggestions", label: `Suggestions queue reviewed (${queuedSuggestions} queued)` },
      { id: "tooling", label: `Tooling queue reviewed (${queuedTooling} queued)` },
      { id: "approvals", label: `Human approvals reviewed (${pendingApprovals} pending)` },
    ],
    [pendingApprovals, queuedSuggestions, queuedTooling, queuedUpdates, queuedUpgrades],
  );

  return (
    <GlowingEdgeCard mode={mode} className="exchange-glow-card card">
      <div className="exchange-glow-inner">
        <header className="exchange-glow-header">
          <h3>Review Queue &amp; Release Insights</h3>
          <StatusChip tone={pendingApprovals > 0 ? "warning" : "success"}>
            {pendingApprovals > 0 ? `${pendingApprovals} awaiting approval` : "cycle gate ready"}
          </StatusChip>
        </header>

        <div className="exchange-glow-columns">
          <section>
            <p className="card-head">Update Notes</p>
            <p className="metric">{updateNotes}</p>
            <p className="metric-sub">archive update records</p>
          </section>
          <section>
            <p className="card-head">Upgrade Reviews</p>
            <p className="metric">{upgradeReviews}</p>
            <p className="metric-sub">review outcomes tracked</p>
          </section>
          <section>
            <p className="card-head">Suggestions Archived</p>
            <p className="metric">{archivedSuggestions}</p>
            <p className="metric-sub">suggestion records</p>
          </section>
          <section>
            <p className="card-head">Suggestions Queued</p>
            <p className="metric">{queuedSuggestions}</p>
            <p className="metric-sub">active pipeline suggestions</p>
          </section>
          <section>
            <p className="card-head">Update Queue</p>
            <p className="metric">{queuedUpdates}</p>
            <p className="metric-sub">active update plans</p>
          </section>
          <section>
            <p className="card-head">Upgrade Queue</p>
            <p className="metric">{queuedUpgrades}</p>
            <p className="metric-sub">active upgrade plans</p>
          </section>
        </div>

        <div className="exchange-review-queue">
          {noPendingQueueWork ? (
            <p style={{ margin: "0 0 0.55rem", color: "var(--success)" }}>
              No pending updates/upgrades/tooling suggestions.
            </p>
          ) : null}
          {queueChecklist.map((item) => (
            <div key={item.id} className="exchange-review-item">
              <label>
                <input
                  type="checkbox"
                  checked={Boolean(reviewChecks[item.id])}
                  onChange={(event) =>
                    setReviewChecks((previous) => ({
                      ...previous,
                      [item.id]: event.target.checked,
                    }))
                  }
                />
                <span>{item.label}</span>
              </label>
            </div>
          ))}
        </div>

        <div className="exchange-glow-list">
          <p className="card-head">Latest Changelog Entries</p>
          <ul>
            {latestChanges.length === 0 ? <li className="muted">No changelog entries available.</li> : null}
            {latestChanges.map((entry) => (
              <li key={entry.entry_id}>
                <span className="mono">{entry.cycle_id}</span>
                <span>{entry.summary}</span>
              </li>
            ))}
          </ul>
        </div>

        <footer className="exchange-glow-footer">
          <span className="mono">Pending features: {pendingFeatures}</span>
          <span className="mono">Open capability gaps: {openGaps}</span>
          <span className="mono">Cycles remaining: {cycleRemaining}</span>
          <span className="mono">Loops remaining: {loopRemaining}</span>
          <span className="mono">Branch: {snapshot.git.branch}</span>
        </footer>
      </div>
    </GlowingEdgeCard>
  );
}
