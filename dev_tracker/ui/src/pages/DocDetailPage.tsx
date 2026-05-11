import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Link, useParams } from "react-router-dom";

import { labelForDocClassification } from "../lib/doc-classification";
import { resolveRelatedDocs } from "../lib/doc-helpers";
import { useTracker } from "../lib/tracker-context";

export function DocDetailPage() {
  const { docId } = useParams();
  const { snapshot } = useTracker();

  if (!snapshot || !docId) {
    return <div className="card card-pad">Document not found.</div>;
  }

  const docs = snapshot.docs
    .filter(
      (entry) =>
        entry.relative_path.startsWith("docs/") ||
        entry.relative_path.startsWith("skills/") ||
        (entry.relative_path.endsWith(".md") && !entry.relative_path.includes("/")),
    )
    .sort((a, b) => a.relative_path.localeCompare(b.relative_path));

  const index = docs.findIndex((entry) => entry.id === docId);
  const doc = index >= 0 ? docs[index] : null;

  const related = useMemo(() => {
    if (!doc) {
      return [];
    }
    return resolveRelatedDocs(snapshot, doc);
  }, [doc, snapshot]);

  if (!doc) {
    return (
      <div className="card card-pad">
        <p>Document id `{docId}` does not exist in snapshot.</p>
        <Link className="btn" to="/docs" style={{ textDecoration: "none" }}>
          Back to docs
        </Link>
      </div>
    );
  }

  const previousDoc = index > 0 ? docs[index - 1] : null;
  const nextDoc = index + 1 < docs.length ? docs[index + 1] : null;

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.65rem", flexWrap: "wrap" }}>
          <div>
            <h2 className="section-title" style={{ marginBottom: "0.2rem" }}>
              {doc.title}
            </h2>
            <p className="mono muted" style={{ margin: 0 }}>
              {doc.relative_path}
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
            <Link to="/docs" className="btn" style={{ textDecoration: "none" }}>
              Docs Index
            </Link>
            {previousDoc ? (
              <Link to={`/docs/${previousDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
                Previous
              </Link>
            ) : null}
            {nextDoc ? (
              <Link to={`/docs/${nextDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
                Next
              </Link>
            ) : null}
          </div>
        </div>

        <div style={{ marginTop: "0.8rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "0.55rem" }}>
          <div className="card card-pad" style={{ padding: "0.65rem" }}>
            <p className="card-head">Status</p>
            <p style={{ margin: "0.25rem 0 0" }}>{doc.status || "--"}</p>
          </div>
          <div className="card card-pad" style={{ padding: "0.65rem" }}>
            <p className="card-head">Owner</p>
            <p style={{ margin: "0.25rem 0 0" }}>{doc.owner || "--"}</p>
          </div>
          <div className="card card-pad" style={{ padding: "0.65rem" }}>
            <p className="card-head">Classification</p>
            <p style={{ margin: "0.25rem 0 0" }}>{labelForDocClassification(doc.classification ?? "system_managed")}</p>
          </div>
          <div className="card card-pad" style={{ padding: "0.65rem" }}>
            <p className="card-head">Checklist</p>
            <p style={{ margin: "0.25rem 0 0" }}>
              {doc.checklist_done}/{doc.checklist_total}
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.65rem" }}>
            <p className="card-head">Last Reviewed</p>
            <p style={{ margin: "0.25rem 0 0" }}>{doc.last_reviewed || "--"}</p>
          </div>
        </div>

        {related.length > 0 ? (
          <div style={{ marginTop: "0.8rem" }}>
            <p className="card-head" style={{ marginBottom: "0.4rem" }}>
              Related Docs
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
              {related.map((entry) => (
                <Link key={entry.id} to={`/docs/${entry.id}`} className="btn" style={{ textDecoration: "none" }}>
                  {entry.title}
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="card card-pad markdown" style={{ gridColumn: "span 12" }}>
        <article>
          <ReactMarkdown>{doc.content}</ReactMarkdown>
        </article>
      </section>
    </div>
  );
}
