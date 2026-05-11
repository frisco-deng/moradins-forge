import { Link } from "react-router-dom";

import { StatusChip } from "../components/StatusChip";
import { GlowingEdgeCard } from "../components/ui";
import { getDocByPath } from "../lib/doc-helpers";
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

function changeTypeTone(type: string): "success" | "warning" | "error" | "info" {
  if (type.includes("implementation")) {
    return "success";
  }
  if (type.includes("upgrade") || type.includes("tooling")) {
    return "warning";
  }
  if (type.includes("governance")) {
    return "info";
  }
  return "info";
}

export function ChangesPage() {
  const { snapshot, settings } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No git change data available.</div>;
  }

  const groupedEntries = Object.entries(snapshot.git.grouped_by_section).sort(([a], [b]) => a.localeCompare(b));
  const patchNotes = [...snapshot.changelog.rows].reverse().slice(0, 6);

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h2 className="section-title">Git Branch and Markdown Changes</h2>
        <p className="section-subtitle">Change tracking for active branch and current working tree.</p>
      </section>

      <section className="card card-pad patch-notes-shell" style={{ gridColumn: "span 12" }}>
        <div className="patch-notes-head">
          <div>
            <p className="card-head">Live Ops</p>
            <h3 style={{ margin: "0.2rem 0 0" }}>Update Notes</h3>
          </div>
          <StatusChip tone={snapshot.changelog.awaiting_human_review_count > 0 ? "warning" : "success"}>
            {snapshot.changelog.awaiting_human_review_count > 0
              ? `${snapshot.changelog.awaiting_human_review_count} Awaiting Review`
              : "All Cycle Approvals Green"}
          </StatusChip>
        </div>
        <p className="section-subtitle" style={{ marginTop: "0.5rem" }}>
          Patch-note view of recent cycle releases, approvals, and impacted artifacts.
        </p>
        <div className="patch-notes-grid">
          {patchNotes.map((entry) => {
            const docsUpdated = entry.docs_updated
              .split(";")
              .map((item) => item.trim())
              .filter(Boolean)
              .slice(0, 4);
            return (
              <GlowingEdgeCard
                key={entry.entry_id}
                as="article"
                disableAnimations={settings.reducedMotion}
                className="patch-note-card patch-note-gec"
                glowStrength={1}
                radiusPx={240}
              >
                <div className="patch-note-top">
                  <span className="mono patch-note-id">{entry.entry_id}</span>
                  <StatusChip tone={approvalTone(entry.approval_status)}>{entry.approval_status}</StatusChip>
                </div>
                <h4 className="patch-note-title">{entry.cycle_id}</h4>
                <p className="patch-note-copy">{entry.summary}</p>
                <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.55rem" }}>
                  <StatusChip tone={changeTypeTone(entry.change_type)}>{entry.change_type}</StatusChip>
                  <StatusChip tone="info">{entry.phase_stage}</StatusChip>
                </div>
                <ul className="patch-note-files">
                  {docsUpdated.length === 0 ? <li className="muted">No docs listed.</li> : null}
                  {docsUpdated.map((item) => (
                    <li key={`${entry.entry_id}-${item}`} className="mono">
                      {item}
                    </li>
                  ))}
                </ul>
              </GlowingEdgeCard>
            );
          })}
        </div>
      </section>

      <GlowingEdgeCard
        as="section"
        className="card card-pad changes-summary-gec"
        style={{ gridColumn: "span 6" }}
        disableAnimations={settings.reducedMotion}
      >
        <p className="card-head">Current Branch</p>
        <p className="metric mono" style={{ fontSize: "1.1rem" }}>
          {snapshot.git.branch}
        </p>
        <p className="metric-sub mono">{snapshot.git.last_commit}</p>
        <div style={{ marginTop: "0.7rem" }}>
          {snapshot.git.dirty ? <StatusChip tone="warning">Working tree has changes</StatusChip> : <StatusChip tone="success">Working tree clean</StatusChip>}
        </div>
      </GlowingEdgeCard>

      <GlowingEdgeCard
        as="section"
        className="card card-pad changes-summary-gec"
        style={{ gridColumn: "span 6" }}
        disableAnimations={settings.reducedMotion}
      >
        <p className="card-head">Markdown Delta</p>
        <p className="metric">{snapshot.git.markdown_changed_count}</p>
        <p className="metric-sub">files changed in current branch state</p>
      </GlowingEdgeCard>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>By Section</h3>
        {groupedEntries.length === 0 ? <p className="muted">No markdown changes detected.</p> : null}
        <div className="changes-section-grid">
          {groupedEntries.map(([section, files]) => (
            <article key={section} className="card card-pad changes-section-card">
              <div className="changes-section-card-head">
                <strong>{section}</strong>
                <span className="muted">{files.length}</span>
              </div>
              <ul className="changes-section-list">
                {files.map((file) => {
                  const doc = getDocByPath(snapshot, file);
                  return (
                    <li key={file} className="changes-section-item">
                      {doc ? (
                        <Link to={`/docs/${doc.id}`} className="mono changes-section-link">
                          {file}
                        </Link>
                      ) : (
                        <span className="mono changes-section-path">{file}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
