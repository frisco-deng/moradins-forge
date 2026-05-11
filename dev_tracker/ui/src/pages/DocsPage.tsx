import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { StatusChip } from "../components/StatusChip";
import { DOC_CLASSIFICATION_LABELS, labelForDocClassification } from "../lib/doc-classification";
import { sectionLabel } from "../lib/doc-helpers";
import {
  docStatusTone,
  docTrackLabel,
} from "../lib/governance-highlights";
import { useTracker } from "../lib/tracker-context";

interface DocMatchResult {
  docId: string;
  score: number;
  matchedIn: string[];
  snippet: string;
  headingMatch: string;
}

function normalize(input: string) {
  return input.toLowerCase();
}

function compactText(input: string) {
  return input.replace(/\s+/g, " ").trim();
}

function unique(values: string[]) {
  return Array.from(new Set(values));
}

function buildSnippet(rawContent: string, query: string) {
  const compact = compactText(rawContent);
  const normalizedContent = normalize(compact);
  const index = normalizedContent.indexOf(query);

  if (index < 0) {
    return "";
  }

  const radius = 88;
  const start = Math.max(index - radius, 0);
  const end = Math.min(index + query.length + radius, compact.length);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < compact.length ? "..." : "";
  return `${prefix}${compact.slice(start, end)}${suffix}`;
}

export function DocsPage() {
  const { snapshot, loading } = useTracker();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [section, setSection] = useState(() => searchParams.get("section") ?? "all");
  const [status, setStatus] = useState(() => searchParams.get("status") ?? "all");
  const [owner, setOwner] = useState(() => searchParams.get("owner") ?? "all");
  const [classification, setClassification] = useState(() => searchParams.get("classification") ?? "all");
  const [searchMode, setSearchMode] = useState<"metadata" | "contextual">(
    () => (searchParams.get("mode") === "metadata" ? "metadata" : "contextual"),
  );
  const deferredQuery = useDeferredValue(query);
  const docs = (snapshot?.docs ?? []).filter(
    (doc) =>
      doc.relative_path.startsWith("docs/") ||
      doc.relative_path.startsWith("Harness/") ||
      doc.relative_path.startsWith("skills/") ||
      (doc.relative_path.endsWith(".md") && !doc.relative_path.includes("/")),
  );
  const sections = Array.from(new Set(docs.map((doc) => doc.section))).sort();
  const statuses = Array.from(new Set(docs.map((doc) => doc.status || "(none)"))).sort();
  const owners = Array.from(new Set(docs.map((doc) => doc.owner || "(none)"))).sort();
  const classifications = Object.keys(DOC_CLASSIFICATION_LABELS);

  function applyFocusFilter(next: {
    query?: string;
    section?: string;
    classification?: string;
    searchMode?: "metadata" | "contextual";
  }) {
    setQuery(next.query ?? "");
    setSection(next.section ?? "all");
    setClassification(next.classification ?? "all");
    setSearchMode(next.searchMode ?? "contextual");
    setStatus("all");
    setOwner("all");
  }

  const filtered = useMemo(() => {
    const normalizedQuery = normalize(deferredQuery.trim());
    const hasQuery = normalizedQuery.length > 0;

    return docs
      .filter((doc) => {
        if (section !== "all" && doc.section !== section) {
          return false;
        }
        if (status !== "all") {
          const nextStatus = doc.status || "(none)";
          if (nextStatus !== status) {
            return false;
          }
        }
        if (owner !== "all") {
          const nextOwner = doc.owner || "(none)";
          if (nextOwner !== owner) {
            return false;
          }
        }
        if (classification !== "all" && doc.classification !== classification) {
          return false;
        }
        return true;
      })
      .map((doc) => {
        const metadataText = `${doc.title} ${doc.relative_path} ${doc.status} ${doc.owner} ${doc.section}`;
        const metadataMatch = hasQuery ? normalize(metadataText).includes(normalizedQuery) : false;

        let headingMatch = "";
        if (hasQuery && searchMode === "contextual") {
          for (const heading of doc.headings) {
            if (normalize(heading.text).includes(normalizedQuery)) {
              headingMatch = heading.text;
              break;
            }
          }
        }

        const snippet = searchMode === "contextual" && hasQuery ? buildSnippet(doc.content, normalizedQuery) : "";
        const contentMatch = snippet.length > 0;
        const hasAnyMatch = !hasQuery || metadataMatch || headingMatch.length > 0 || contentMatch;

        if (hasQuery && !hasAnyMatch) {
          return null;
        }

        const matchTags: string[] = [];
        let score = 0;

        if (hasQuery && metadataMatch) {
          matchTags.push("metadata");
          score += 12;
        }
        if (hasQuery && headingMatch) {
          matchTags.push("heading");
          score += 8;
        }
        if (hasQuery && contentMatch) {
          matchTags.push("content");
          score += 6;
        }

        const match: DocMatchResult = {
          docId: doc.id,
          score,
          matchedIn: unique(matchTags),
          snippet,
          headingMatch,
        };

        return {
          doc,
          match,
        };
      })
      .filter((item): item is { doc: (typeof docs)[number]; match: DocMatchResult } => item !== null)
      .sort((a, b) => {
        if (b.match.score !== a.match.score) {
          return b.match.score - a.match.score;
        }
        return a.doc.relative_path.localeCompare(b.doc.relative_path);
      });
  }, [classification, deferredQuery, docs, owner, section, searchMode, status]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (query.trim()) {
      next.set("q", query.trim());
    }
    if (section !== "all") {
      next.set("section", section);
    }
    if (status !== "all") {
      next.set("status", status);
    }
    if (owner !== "all") {
      next.set("owner", owner);
    }
    if (classification !== "all") {
      next.set("classification", classification);
    }
    if (searchMode !== "contextual") {
      next.set("mode", searchMode);
    }
    setSearchParams(next, { replace: true });
  }, [classification, owner, query, searchMode, section, setSearchParams, status]);

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
    return <div className="card card-pad">No docs index available.</div>;
  }

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h2 className="section-title">Docs Explorer</h2>
        <p className="section-subtitle">Search first, then narrow by section, status, owner, and classification only when needed.</p>

        <div className="docs-filter-grid">
          <input
            className="input"
            placeholder={searchMode === "contextual" ? "Search title/path/headings/content" : "Search title/path/metadata"}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />

          <select className="select" value={searchMode} onChange={(event) => setSearchMode(event.target.value as "metadata" | "contextual")}>
            <option value="contextual">Contextual</option>
            <option value="metadata">Metadata Only</option>
          </select>

          <select className="select" value={section} onChange={(event) => setSection(event.target.value)}>
            <option value="all">All sections</option>
            {sections.map((value) => (
              <option key={value} value={value}>
                {sectionLabel(value)}
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

          <select className="select" value={owner} onChange={(event) => setOwner(event.target.value)}>
            <option value="all">All owners</option>
            {owners.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>

          <select className="select" value={classification} onChange={(event) => setClassification(event.target.value)}>
            <option value="all">All classifications</option>
            {classifications.map((value) => (
              <option key={value} value={value}>
                {DOC_CLASSIFICATION_LABELS[value as keyof typeof DOC_CLASSIFICATION_LABELS]}
              </option>
            ))}
          </select>
        </div>

        <div className="docs-quick-filter-row">
          <button type="button" className="btn" onClick={() => applyFocusFilter({ classification: "human_owned_context" })}>
            Human-owned context
          </button>
          <button type="button" className="btn" onClick={() => applyFocusFilter({ classification: "generated" })}>
            Generated docs
          </button>
          <button type="button" className="btn" onClick={() => applyFocusFilter({ section: "exec_plans", searchMode: "metadata" })}>
            Exec plans
          </button>
          <button type="button" className="btn" onClick={() => applyFocusFilter({})}>
            Reset filters
          </button>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="muted" style={{ marginTop: 0 }}>
          Showing {filtered.length} of {docs.length} docs
          {deferredQuery.trim() ? ` | query: "${deferredQuery.trim()}"` : ""}
        </p>

        <div style={{ overflow: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Path</th>
                <th>Section</th>
                <th>Classification</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Match</th>
                <th>Context</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(({ doc, match }) => (
                <tr key={doc.id}>
                  <td>
                    <Link to={`/docs/${doc.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                      {doc.title}
                    </Link>
                  </td>
                  <td className="mono" style={{ fontSize: "0.78rem" }}>
                    <div>{doc.relative_path}</div>
                    {docTrackLabel(doc) ? <span className="docs-track-chip">{docTrackLabel(doc)}</span> : null}
                  </td>
                  <td>{sectionLabel(doc.section)}</td>
                  <td>
                    <span className="docs-track-chip">{labelForDocClassification(doc.classification ?? "system_managed")}</span>
                  </td>
                  <td>{doc.status ? <StatusChip tone={docStatusTone(doc.status)}>{doc.status}</StatusChip> : "--"}</td>
                  <td>{doc.owner || "--"}</td>
                  <td>
                    {query.trim() ? (
                      <div className="docs-match-badges">
                        {match.matchedIn.length === 0 ? <span className="docs-match-chip">none</span> : null}
                        {match.matchedIn.map((tag) => (
                          <span key={tag} className="docs-match-chip">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="muted">--</span>
                    )}
                  </td>
                  <td>
                    {match.headingMatch ? <div className="docs-match-heading">Heading: {match.headingMatch}</div> : null}
                    {match.snippet ? <div className="docs-match-snippet">{match.snippet}</div> : <span className="muted">--</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
