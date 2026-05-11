import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHero } from "../components/PageHero";
import { ScrollSurface } from "../components/ScrollSurface";
import { getDocByPath } from "../lib/doc-helpers";
import { StatusChip } from "../components/StatusChip";
import { useTracker } from "../lib/tracker-context";

function chipTone(status: string): "success" | "warning" | "error" | "info" {
  if (status === "archived" || status === "closed") {
    return "success";
  }
  if (status === "in_progress") {
    return "warning";
  }
  if (status === "rejected") {
    return "error";
  }
  return "info";
}

export function ArchivePage() {
  const { snapshot } = useTracker();
  const [query, setQuery] = useState("");
  const [recordType, setRecordType] = useState("all");
  const [status, setStatus] = useState("all");
  const register = snapshot?.archive_register ?? {
    row_count: 0,
    suggestion_count: 0,
    update_count: 0,
    upgrade_review_count: 0,
    rows: [],
  };
  const archiveDocs = snapshot?.docs.filter((doc) => doc.relative_path.startsWith("docs/archive/")) ?? [];
  const types = Array.from(new Set(register.rows.map((row) => row.record_type))).sort();
  const statuses = Array.from(new Set(register.rows.map((row) => row.status))).sort();

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return register.rows.filter((row) => {
      if (recordType !== "all" && row.record_type !== recordType) {
        return false;
      }
      if (status !== "all" && row.status !== status) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        row.archive_id,
        row.archived_on,
        row.record_type,
        row.source_cycle,
        row.title,
        row.status,
        row.archive_path,
        row.upgrade_review,
        row.notes,
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [query, recordType, register.rows, status]);

  if (!snapshot) {
    return <div className="card card-pad">No archive data available.</div>;
  }

  return (
    <div className="page-grid">
      <PageHero
        title="Archive"
        subtitle="Structured archive records for suggestions, updates, and upgrade-review outcomes."
        eyebrow="Historical Traceability"
        chips={
          <>
            <StatusChip tone="info">{`Archive entries ${register.row_count}`}</StatusChip>
            <StatusChip tone="warning">{`Upgrade reviews ${register.upgrade_review_count}`}</StatusChip>
            <StatusChip tone="success">{`Updates ${register.update_count}`}</StatusChip>
          </>
        }
      />

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "grid", gap: "0.8rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <div className="card card-pad">
            <p className="card-head">Archive Entries</p>
            <p className="metric">{register.row_count}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Suggestions</p>
            <p className="metric">{register.suggestion_count}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Upgrade Reviews</p>
            <p className="metric">{register.upgrade_review_count}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Updates</p>
            <p className="metric">{register.update_count}</p>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div className="archive-filter-grid">
          <input
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search archive id, cycle, title, or notes"
          />

          <select className="select" value={recordType} onChange={(event) => setRecordType(event.target.value)}>
            <option value="all">All record types</option>
            {types.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>

          <select className="select" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">All status</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>

        <p className="muted" style={{ marginTop: "0.75rem" }}>
          Showing {filteredRows.length} of {register.row_count} archive rows
        </p>

        <ScrollSurface className="effects-table-wrap">
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Archive ID</th>
                <th>Type</th>
                <th>Source Cycle</th>
                <th>Title</th>
                <th>Status</th>
                <th>Archive Path</th>
                <th>Upgrade Review</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const doc = getDocByPath(snapshot, row.archive_path);
                return (
                  <tr key={row.archive_id}>
                    <td className="mono">{row.archive_id}</td>
                    <td>{row.record_type}</td>
                    <td className="mono">{row.source_cycle}</td>
                    <td>
                      <div>{row.title}</div>
                      <div className="muted">{row.notes}</div>
                    </td>
                    <td>
                      <StatusChip tone={chipTone(row.status)}>{row.status}</StatusChip>
                    </td>
                    <td className="mono" style={{ fontSize: "0.78rem" }}>
                      {doc ? (
                        <Link to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                          {row.archive_path}
                        </Link>
                      ) : (
                        row.archive_path
                      )}
                    </td>
                    <td>{row.upgrade_review}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Archive Docs</h3>
        <p className="section-subtitle">Direct links to archived records and converted legacy suggestion material.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.75rem" }}>
          {archiveDocs.slice(0, 48).map((doc) => (
            <Link key={doc.id} to={`/docs/${doc.id}`} className="btn" style={{ textDecoration: "none" }}>
              {doc.title}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
