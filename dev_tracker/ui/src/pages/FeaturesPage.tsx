import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHero } from "../components/PageHero";
import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import { StatusPillButton } from "../components/StatusPillButton";
import { useTracker } from "../lib/tracker-context";

function statusTone(status: string): "success" | "warning" | "error" | "info" {
  if (status === "implemented") {
    return "success";
  }
  if (status === "pending") {
    return "warning";
  }
  if (status === "blocked") {
    return "error";
  }
  return "info";
}

function reviewKind(relativePath: string): "update" | "upgrade" | "tooling" | "other" {
  if (relativePath.includes("update_review_")) {
    return "update";
  }
  if (relativePath.includes("upgrade_review_")) {
    return "upgrade";
  }
  if (relativePath.includes("tooling_review_")) {
    return "tooling";
  }
  return "other";
}

function reviewTone(kind: string): "success" | "warning" | "error" | "info" {
  if (kind === "update") {
    return "info";
  }
  if (kind === "upgrade") {
    return "warning";
  }
  if (kind === "tooling") {
    return "success";
  }
  return "info";
}

export function FeaturesPage() {
  const { snapshot } = useTracker();
  const [featureQuery, setFeatureQuery] = useState("");
  const [featureStatusFilter, setFeatureStatusFilter] = useState("all");
  const docs = snapshot?.docs ?? [];
  const featureRows = snapshot?.current_features.rows ?? [];

  const implementedCount = snapshot?.current_features.implemented_count ?? 0;
  const pendingCount = snapshot?.current_features.pending_count ?? 0;
  const totalFeatureRows = featureRows.length;
  const completionRatio = totalFeatureRows === 0 ? 0 : implementedCount / totalFeatureRows;

  const reviewDocs = useMemo(() => {
    const candidates = docs
      .filter(
        (doc) =>
          doc.relative_path.startsWith("docs/exec_plans/updates/completed/") ||
          doc.relative_path.startsWith("docs/exec_plans/upgrades/completed/") ||
          doc.relative_path.startsWith("docs/exec_plans/tooling/completed/"),
      )
      .filter(
        (doc) =>
          doc.relative_path.includes("update_review_") ||
          doc.relative_path.includes("upgrade_review_") ||
          doc.relative_path.includes("tooling_review_"),
      )
      .sort((a, b) => a.relative_path.localeCompare(b.relative_path));

    const byFileName = new Map<string, (typeof candidates)[number] & { kind: "update" | "upgrade" | "tooling" | "other" }>();
    for (const doc of candidates) {
      const key = doc.relative_path.split("/").at(-1) ?? doc.relative_path;
      if (byFileName.has(key)) {
        continue;
      }
      byFileName.set(key, {
        ...doc,
        kind: reviewKind(doc.relative_path),
      });
    }
    return Array.from(byFileName.values());
  }, [docs]);

  const updateReviewCount = reviewDocs.filter((doc) => doc.kind === "update").length;
  const upgradeReviewCount = reviewDocs.filter((doc) => doc.kind === "upgrade").length;
  const toolingReviewCount = reviewDocs.filter((doc) => doc.kind === "tooling").length;

  const filteredFeatures = useMemo(() => {
    const query = featureQuery.trim().toLowerCase();
    return featureRows.filter((row) => {
      const matchesStatus = featureStatusFilter === "all" || row.status === featureStatusFilter;
      if (!matchesStatus) {
        return false;
      }
      if (!query) {
        return true;
      }
      const corpus = [row.feature_id, row.capability, row.source_phase_stage, row.owner, row.evidence_link].join(" ").toLowerCase();
      return corpus.includes(query);
    });
  }, [featureQuery, featureRows, featureStatusFilter]);

  const stageRollup = useMemo(() => {
    const counts = new Map<string, { implemented: number; pending: number }>();
    for (const row of featureRows) {
      const bucket = counts.get(row.source_phase_stage) ?? { implemented: 0, pending: 0 };
      if (row.status === "implemented") {
        bucket.implemented += 1;
      } else {
        bucket.pending += 1;
      }
      counts.set(row.source_phase_stage, bucket);
    }
    return Array.from(counts.entries()).map(([sourcePhaseStage, bucket]) => ({
      sourcePhaseStage,
      ...bucket,
      total: bucket.implemented + bucket.pending,
    }));
  }, [featureRows]);

  if (!snapshot) {
    return <div className="card card-pad">No tracker snapshot available.</div>;
  }

  return (
    <div className="page-grid">
      <PageHero
        title="Features"
        subtitle="Consolidated view of feature implementation plus update, upgrade, and tooling review evidence."
        eyebrow="Delivery Snapshot"
        chips={
          <>
            <StatusChip tone="success">{`Implemented ${implementedCount}`}</StatusChip>
            <StatusChip tone="warning">{`Pending ${pendingCount}`}</StatusChip>
            <StatusChip tone="info">{`Reviews ${reviewDocs.length}`}</StatusChip>
          </>
        }
      />

      <section className="card card-pad" style={{ gridColumn: "span 3" }}>
        <p className="card-head">Implemented Features</p>
        <p className="metric">{implementedCount}</p>
        <p className="metric-sub">of {totalFeatureRows} tracked rows</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 3" }}>
        <p className="card-head">Pending Features</p>
        <p className="metric">{pendingCount}</p>
        <p className="metric-sub">awaiting phase execution</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 3" }}>
        <p className="card-head">Implementation Ratio</p>
        <p className="metric">{Math.round(completionRatio * 100)}%</p>
        <p className="metric-sub">implemented vs total</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 3" }}>
        <p className="card-head">Review Artifacts</p>
        <p className="metric">{reviewDocs.length}</p>
        <p className="metric-sub">update, upgrade, tooling reports</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Update and Upgrade Review Coverage</h3>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
          <StatusPillButton
            tone="info"
            preferredWidth={360}
            popoverContent={() => (
              <div>
                <p className="card-head" style={{ marginTop: 0 }}>Update Reviews</p>
                <div style={{ display: "grid", gap: "0.45rem", marginTop: "0.7rem" }}>
                  {reviewDocs.filter((doc) => doc.kind === "update").map((doc) => (
                    <Link key={doc.id} to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                      {doc.title}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          >
            {`Update Reviews ${updateReviewCount}`}
          </StatusPillButton>
          <StatusPillButton
            tone="warning"
            preferredWidth={360}
            popoverContent={() => (
              <div>
                <p className="card-head" style={{ marginTop: 0 }}>Upgrade Reviews</p>
                <div style={{ display: "grid", gap: "0.45rem", marginTop: "0.7rem" }}>
                  {reviewDocs.filter((doc) => doc.kind === "upgrade").map((doc) => (
                    <Link key={doc.id} to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                      {doc.title}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          >
            {`Upgrade Reviews ${upgradeReviewCount}`}
          </StatusPillButton>
          <StatusPillButton
            tone="success"
            preferredWidth={360}
            popoverContent={() => (
              <div>
                <p className="card-head" style={{ marginTop: 0 }}>Tooling Reviews</p>
                <div style={{ display: "grid", gap: "0.45rem", marginTop: "0.7rem" }}>
                  {reviewDocs.filter((doc) => doc.kind === "tooling").map((doc) => (
                    <Link key={doc.id} to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                      {doc.title}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          >
            {`Tooling Reviews ${toolingReviewCount}`}
          </StatusPillButton>
        </div>
        <ScrollSurface className="effects-table-wrap" style={{ marginTop: "0.75rem" }}>
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Review Type</th>
                <th>Title</th>
                <th>Status</th>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {reviewDocs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="effects-empty">
                    No review artifacts found.
                  </td>
                </tr>
              ) : null}
              {reviewDocs.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <StatusChip tone={reviewTone(doc.kind)}>{doc.kind}</StatusChip>
                  </td>
                  <td>
                    <Link to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                      {doc.title}
                    </Link>
                  </td>
                  <td>{doc.status || "--"}</td>
                  <td className="mono">{doc.relative_path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Feature Inventory</h3>
        <div className="effects-filter-row">
          <input
            className="input effects-filter-input"
            value={featureQuery}
            onChange={(event) => setFeatureQuery(event.target.value)}
            placeholder="Search feature id, capability, owner, source stage"
          />
          <select
            className="select effects-filter-select"
            value={featureStatusFilter}
            onChange={(event) => setFeatureStatusFilter(event.target.value)}
          >
            <option value="all">all statuses</option>
            <option value="implemented">implemented</option>
            <option value="pending">pending</option>
          </select>
        </div>
        <ScrollSurface className="effects-table-wrap">
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Phase/Stage</th>
                <th>Owner</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredFeatures.length === 0 ? (
                <tr>
                  <td colSpan={4} className="effects-empty">
                    No feature rows match current filter.
                  </td>
                </tr>
              ) : null}
              {filteredFeatures.map((row) => (
                <tr key={row.feature_id}>
                  <td>
                    <div className="mono">{row.feature_id}</div>
                    <div className="muted">{row.capability}</div>
                  </td>
                  <td className="mono">{row.source_phase_stage}</td>
                  <td>{row.owner}</td>
                  <td>
                    <StatusChip tone={statusTone(row.status)}>{row.status}</StatusChip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Phase and Stage Rollup</h3>
        <div className="effects-table-wrap">
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Phase/Stage</th>
                <th>Implemented</th>
                <th>Pending</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {stageRollup.length === 0 ? (
                <tr>
                  <td colSpan={4} className="effects-empty">
                    No phase/stage rollup rows yet.
                  </td>
                </tr>
              ) : null}
              {stageRollup.map((item) => (
                <tr key={item.sourcePhaseStage}>
                  <td className="mono">{item.sourcePhaseStage}</td>
                  <td>{item.implemented}</td>
                  <td>{item.pending}</td>
                  <td>{item.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
