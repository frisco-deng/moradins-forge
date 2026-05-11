import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { PageHero } from "../components/PageHero";
import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import { StatusPillButton } from "../components/StatusPillButton";
import { TooltipHint } from "../components/TooltipHint";
import { useTracker } from "../lib/tracker-context";

function isStale(lastReviewed: string) {
  if (!lastReviewed) {
    return true;
  }

  const timestamp = Date.parse(lastReviewed);
  if (Number.isNaN(timestamp)) {
    return true;
  }

  const ageMs = Date.now() - timestamp;
  const staleMs = 180 * 24 * 60 * 60 * 1000;
  return ageMs > staleMs;
}

function buildFrontmatterDraft(doc: { title: string; status: string; owner: string }) {
  const today = new Date().toISOString().slice(0, 10);
  const title = doc.title || "TODO title";
  const status = doc.status || "draft";
  const owner = doc.owner || "TODO-owner";
  return [
    "---",
    `title: "${title}"`,
    `status: ${status}`,
    `owner: ${owner}`,
    `last_reviewed: ${today}`,
    "source_refs: []",
    "related_docs: []",
    "---",
    "",
  ].join("\n");
}

export function PoliciesPage() {
  const { snapshot } = useTracker();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedDomain, setSelectedDomain] = useState<string>("");
  const [frontmatterDrafts, setFrontmatterDrafts] = useState<Record<string, string>>({});
  const attentionSectionRef = useRef<HTMLElement | null>(null);
  const domains = snapshot?.policies.domains ?? [];
  const docs = snapshot?.docs ?? [];
  const activeDomain = selectedDomain || (domains[0]?.domain ?? "");

  useEffect(() => {
    const domainParam = searchParams.get("domain");
    if (!domainParam) {
      return;
    }

    const match = domains.find((entry) => entry.domain.toLowerCase() === domainParam.toLowerCase());
    if (match && match.domain !== selectedDomain) {
      setSelectedDomain(match.domain);
    }
  }, [domains, searchParams, selectedDomain]);

  const activeDocs = useMemo(() => {
    if (!activeDomain) {
      return [];
    }

    const domain = domains.find((entry) => entry.domain === activeDomain);
    if (!domain) {
      return [];
    }

    const idSet = new Set(domain.doc_ids);
    return docs.filter((doc) => idSet.has(doc.id));
  }, [activeDomain, docs, domains]);

  const attentionDocs = useMemo(
    () =>
      activeDocs.filter(
        (doc) => !doc.owner || !doc.status || !doc.has_frontmatter || isStale(doc.last_reviewed),
      ),
    [activeDocs],
  );

  function setDomain(domainName: string) {
    setSelectedDomain(domainName);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("domain", domainName);
    setSearchParams(nextParams, { replace: true });
  }

  function onReviewDomain(domainName: string) {
    setDomain(domainName);
    requestAnimationFrame(() => {
      const sectionNode = attentionSectionRef.current;
      if (sectionNode && typeof sectionNode.scrollIntoView === "function") {
        sectionNode.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  if (!snapshot) {
    return <div className="card card-pad">No policy data available.</div>;
  }

  return (
    <div className="page-grid">
      <PageHero
        title="Policies"
        subtitle="Domain health from harness docs: security, interfaces, architecture, observability, operations, and governance."
        eyebrow="Governance Coverage"
        chips={
          <>
            <StatusChip tone="success">{`${domains.length} domains`}</StatusChip>
            <StatusChip tone="warning">{`${attentionDocs.length} docs need attention`}</StatusChip>
          </>
        }
      >
        <div className="card card-pad" style={{ padding: "0.8rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <strong>Review by domain</strong>
            <TooltipHint text="Use the domain status pill itself as the route driver into the detailed review surface." />
          </div>
        </div>
      </PageHero>

      {domains.map((domain) => {
        const riskCount = domain.missing_owner_count + domain.missing_status_count + domain.stale_review_count;
        const tone = riskCount === 0 ? "success" : riskCount < 3 ? "warning" : "error";

        return (
          <article
            key={domain.domain}
            className={`card card-pad policy-domain-card ${activeDomain === domain.domain ? "active" : ""}`}
            style={{ gridColumn: "span 3", textAlign: "left" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.45rem" }}>
              <strong style={{ textTransform: "capitalize" }}>{domain.domain}</strong>
              <StatusPillButton tone={tone} onClick={() => onReviewDomain(domain.domain)}>
                {riskCount === 0 ? "Healthy" : "Review"}
              </StatusPillButton>
            </div>
            <p className="muted" style={{ margin: "0.45rem 0 0", fontSize: "0.85rem" }}>
              {domain.doc_count} docs | stale {domain.stale_review_count} | missing owner {domain.missing_owner_count}
            </p>
          </article>
        );
      })}

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0, textTransform: "capitalize" }}>{activeDomain} docs</h3>
        <ScrollSurface className="effects-table-wrap">
        <table className="table effects-table">
          <thead>
            <tr>
              <th>Doc</th>
              <th>Section</th>
              <th>Status</th>
              <th>Owner</th>
              <th>Last Reviewed</th>
            </tr>
          </thead>
          <tbody>
            {activeDocs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <Link to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                    {doc.title}
                  </Link>
                  <div className="muted mono" style={{ fontSize: "0.78rem" }}>
                    {doc.relative_path}
                  </div>
                </td>
                <td>{doc.section}</td>
                <td>{doc.status || "--"}</td>
                <td>{doc.owner || "--"}</td>
                <td>{doc.last_reviewed || "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </ScrollSurface>
      </section>

      <section ref={attentionSectionRef} className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Docs Needing Attention</h3>
        <p className="section-subtitle">
          Review focus for missing metadata, stale ownership/review fields, and frontmatter gaps.
        </p>
        <ScrollSurface className="policy-attention-grid" style={{ maxHeight: "420px", marginTop: "0.75rem", paddingRight: "0.2rem" }}>
          {attentionDocs.length === 0 ? <p className="muted" style={{ margin: 0 }}>No docs need immediate attention in this domain.</p> : null}
          {attentionDocs.map((doc) => (
            <article key={doc.id} className="card card-pad" style={{ padding: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
                <Link to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                  {doc.title}
                </Link>
                {!doc.has_frontmatter ? <StatusChip tone="warning">Missing frontmatter</StatusChip> : null}
              </div>
              <p className="mono muted" style={{ marginTop: "0.35rem" }}>
                {doc.relative_path}
              </p>

              {!doc.has_frontmatter ? (
                <div className="policy-frontmatter-helper">
                  <label className="field-label">Frontmatter Draft</label>
                  <textarea
                    className="input"
                    value={frontmatterDrafts[doc.id] ?? ""}
                    onChange={(event) =>
                      setFrontmatterDrafts((previous) => ({
                        ...previous,
                        [doc.id]: event.target.value,
                      }))
                    }
                    placeholder={buildFrontmatterDraft(doc)}
                  />
                  <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                    <button
                      className="btn"
                      type="button"
                      onClick={() =>
                        setFrontmatterDrafts((previous) => ({
                          ...previous,
                          [doc.id]: buildFrontmatterDraft(doc),
                        }))
                      }
                    >
                      Generate Draft
                    </button>
                    <button
                      className="btn"
                      type="button"
                      onClick={() => {
                        const value = frontmatterDrafts[doc.id] ?? buildFrontmatterDraft(doc);
                        if (navigator.clipboard?.writeText) {
                          void navigator.clipboard.writeText(value);
                        }
                      }}
                    >
                      Copy Draft
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </ScrollSurface>
      </section>
    </div>
  );
}
