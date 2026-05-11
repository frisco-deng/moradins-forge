import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { StatusChip } from "../components/StatusChip";
import {
  docStatusTone,
  findActivePlan,
  findActiveUpgradePackage,
  findLatestAwaitingApproval,
} from "../lib/governance-highlights";
import { useTracker } from "../lib/tracker-context";

function approvalTone(status: string): "success" | "warning" | "error" | "info" {
  if (status === "approved") {
    return "success";
  }
  if (status === "awaiting_human_review") {
    return "warning";
  }
  if (status === "rejected") {
    return "error";
  }
  return "info";
}

function matchesQuery(query: string, values: string[]) {
  if (!query.trim()) {
    return true;
  }
  const normalized = query.trim().toLowerCase();
  return values.some((value) => value.toLowerCase().includes(normalized));
}

export function ExchangePage() {
  const { snapshot, loading } = useTracker();
  const [query, setQuery] = useState("");
  const [approvalFilter, setApprovalFilter] = useState("all");
  const changelogRows = snapshot?.changelog?.rows ?? [];
  const filteredRows = useMemo(
    () =>
      changelogRows.filter((entry) => {
        const matchesApproval = approvalFilter === "all" || entry.approval_status === approvalFilter;
        const matchesText = matchesQuery(query, [
          entry.entry_id,
          entry.cycle_id,
          entry.summary,
          entry.change_type,
          entry.approval_ref,
          entry.approval_status,
          entry.docs_updated,
        ]);
        return matchesApproval && matchesText;
      }),
    [approvalFilter, changelogRows, query],
  );

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
    return <div className="card card-pad">No tracker snapshot available.</div>;
  }

  const pendingApprovals = snapshot.review_queue?.pending_approvals ?? 0;
  const pendingReviewItems = snapshot.review_queue?.pending_total ?? 0;
  const workingTreeDirty = snapshot.git?.dirty ?? false;
  const activeUpgradePackage = findActiveUpgradePackage(snapshot);
  const activeUpdatePlan = findActivePlan(snapshot, "docs/exec_plans/updates/active/");
  const activeCommissioningPlan = findActivePlan(snapshot, "docs/exec_plans/commissioning/active/");
  const latestAwaitingApproval = findLatestAwaitingApproval(snapshot);

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div className="activity-hero">
          <div>
            <p className="card-head">Activity</p>
            <h2 className="section-title" style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>
              Rolling change feed for the work that actually moved.
            </h2>
            <p className="section-subtitle" style={{ marginBottom: 0 }}>
              Keep the queue in `/reviews/queue`. Use Activity to scan recent changes, current governed work, and the latest gate without wading through every governance table.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
            <StatusChip tone={pendingApprovals > 0 ? "warning" : "success"}>
              {`${pendingApprovals} pending approvals`}
            </StatusChip>
            <StatusChip tone={pendingReviewItems > 0 ? "warning" : "success"}>
              {`${pendingReviewItems} queued review items`}
            </StatusChip>
            <StatusChip tone={workingTreeDirty ? "warning" : "success"}>
              {workingTreeDirty ? "working tree dirty" : "working tree clean"}
            </StatusChip>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Current Governed Work</p>
        <div className="activity-summary-list" style={{ marginTop: "0.85rem" }}>
          {activeUpdatePlan?.primaryDoc ? (
            <article className="activity-summary-card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", alignItems: "start" }}>
                <strong>{activeUpdatePlan.primaryDoc.title}</strong>
                <StatusChip tone={docStatusTone(activeUpdatePlan.primaryDoc.status)}>{activeUpdatePlan.primaryDoc.status}</StatusChip>
              </div>
              <p className="metric-sub mono">{activeUpdatePlan.primaryDoc.relative_path}</p>
              <Link className="btn" to={`/docs/${activeUpdatePlan.primaryDoc.id}`} style={{ textDecoration: "none" }}>
                Open update
              </Link>
            </article>
          ) : null}

          {activeUpgradePackage?.primaryDoc ? (
            <article className="activity-summary-card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", alignItems: "start" }}>
                <strong>{activeUpgradePackage.primaryDoc.title}</strong>
                <StatusChip tone={docStatusTone(activeUpgradePackage.primaryDoc.status)}>{activeUpgradePackage.primaryDoc.status}</StatusChip>
              </div>
              <p className="metric-sub mono">{activeUpgradePackage.primaryDoc.relative_path}</p>
              <Link className="btn" to={`/docs/${activeUpgradePackage.primaryDoc.id}`} style={{ textDecoration: "none" }}>
                Open upgrade
              </Link>
            </article>
          ) : null}

          {activeCommissioningPlan?.primaryDoc ? (
            <article className="activity-summary-card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", alignItems: "start" }}>
                <strong>{activeCommissioningPlan.primaryDoc.title}</strong>
                <StatusChip tone={docStatusTone(activeCommissioningPlan.primaryDoc.status)}>{activeCommissioningPlan.primaryDoc.status}</StatusChip>
              </div>
              <p className="metric-sub mono">{activeCommissioningPlan.primaryDoc.relative_path}</p>
              <Link className="btn" to={`/docs/${activeCommissioningPlan.primaryDoc.id}`} style={{ textDecoration: "none" }}>
                Open commissioning
              </Link>
            </article>
          ) : null}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <div className="quick-start-guide-head">
          <div>
            <p className="card-head">Rolling Change Feed</p>
            <p className="metric-sub" style={{ margin: "0.35rem 0 0" }}>
              Search recent cycle activity by summary, cycle, approval ref, or doc touchpoint.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <Link className="btn" to="/reviews/queue" style={{ textDecoration: "none" }}>
              Open Review Queue
            </Link>
            {latestAwaitingApproval ? (
              <StatusChip tone="warning">{`latest gate ${latestAwaitingApproval.cycle_id}`}</StatusChip>
            ) : (
              <StatusChip tone="success">no gate blockers</StatusChip>
            )}
          </div>
        </div>

        <div className="docs-filter-grid" style={{ marginTop: "0.9rem" }}>
          <input
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search cycle, summary, change type, approval ref"
          />
          <select className="select" value={approvalFilter} onChange={(event) => setApprovalFilter(event.target.value)}>
            <option value="all">All approvals</option>
            <option value="approved">Approved</option>
            <option value="awaiting_human_review">Awaiting review</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        <div className="activity-feed" style={{ marginTop: "0.9rem" }}>
          {filteredRows.length === 0 ? (
            <p className="metric-sub" style={{ margin: 0 }}>
              No change-log rows match the current filter.
            </p>
          ) : null}
          {filteredRows.map((entry) => (
            <article key={entry.entry_id} className="activity-feed-card">
              <div className="activity-feed-top">
                <div>
                  <p className="card-head">{entry.cycle_id}</p>
                  <strong>{entry.summary}</strong>
                </div>
                <StatusChip tone={approvalTone(entry.approval_status)}>{entry.approval_status}</StatusChip>
              </div>
              <p className="metric-sub" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
                {entry.change_type} · {entry.phase_stage} · {entry.date || "date not recorded"}
              </p>
              <p className="metric-sub mono" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                {entry.docs_updated || "No docs recorded"} · {entry.approval_ref || "No approval ref"}
              </p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
