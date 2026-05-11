import { ClipboardCheck, RefreshCw, TerminalSquare } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import type {
  MoradinInstallRequestV1,
  MoradinReadinessCheckV1,
  MoradinRepoRegistryV1,
  MoradinToolingReadinessV1,
} from "../lib/contracts";
import {
  createMoradinInstallRequest,
  loadMoradinReadiness,
  loadMoradinRepoRegistry,
} from "../lib/loaders";

function readinessTone(status: string, required: boolean) {
  if (status === "present") {
    return "success" as const;
  }
  if (status === "manual") {
    return "info" as const;
  }
  return required ? ("error" as const) : ("warning" as const);
}

function overallTone(status: MoradinToolingReadinessV1["summary"]["overall_status"]) {
  if (status === "ready") {
    return "success" as const;
  }
  if (status === "action_required") {
    return "error" as const;
  }
  return "warning" as const;
}

function statusLabel(check: MoradinReadinessCheckV1) {
  if (check.status === "present") {
    return "present";
  }
  if (check.status === "manual") {
    return "manual";
  }
  return check.required ? "missing required" : "missing optional";
}

export function ReadinessPage() {
  const [readiness, setReadiness] = useState<MoradinToolingReadinessV1 | null>(null);
  const [registry, setRegistry] = useState<MoradinRepoRegistryV1 | null>(null);
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);
  const [installRequest, setInstallRequest] = useState<MoradinInstallRequestV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingRequest, setCreatingRequest] = useState(false);

  const missingChecks = useMemo(
    () => readiness?.groups.flatMap((group) => group.checks).filter((check) => check.status === "missing") ?? [],
    [readiness],
  );

  async function refresh() {
    setLoading(true);
    const [nextReadiness, nextRegistry] = await Promise.all([loadMoradinReadiness(), loadMoradinRepoRegistry()]);
    setReadiness(nextReadiness);
    setRegistry(nextRegistry);
    setSelectedToolIds(
      nextReadiness?.groups
        .flatMap((group) => group.checks)
        .filter((check) => check.status === "missing")
        .map((check) => check.tool_id) ?? [],
    );
    setLoading(false);
  }

  useEffect(() => {
    void refresh();
  }, []);

  function toggleTool(toolId: string) {
    setSelectedToolIds((current) =>
      current.includes(toolId) ? current.filter((id) => id !== toolId) : [...current, toolId],
    );
  }

  async function requestInstalls() {
    setCreatingRequest(true);
    const request = await createMoradinInstallRequest({
      tool_ids: selectedToolIds,
      assistant_mode: "manual_handoff",
      operator_note: "Generated from Deploy Readiness.",
    });
    setInstallRequest(request);
    setCreatingRequest(false);
  }

  if (loading && !readiness) {
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

  if (!readiness) {
    return (
      <div className="page-grid">
        <section className="card card-pad" style={{ gridColumn: "span 12" }}>
          <p className="card-head">Readiness</p>
          <p className="metric-sub">Readiness data is unavailable. Confirm the control API is running.</p>
          <button className="btn" type="button" onClick={refresh}>
            <RefreshCw size={15} />
            Refresh
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="page-grid">
      <section className="card card-pad workspace-header-card compact" style={{ gridColumn: "span 12" }}>
        <div className="workspace-header-copy">
          <div>
            <p className="workspace-header-description accent">Readiness</p>
          </div>
          <div className="workspace-header-actions">
            <button className="btn" type="button" onClick={refresh} disabled={loading}>
              <RefreshCw size={15} />
              Refresh
            </button>
            <Link className="workspace-header-pill-link primary" to="/deploy/map">
              Open Deploy Map
            </Link>
            <Link className="workspace-header-pill-link" to="/deploy/builder">
              Open Builder
            </Link>
          </div>
        </div>
        <div className="workspace-header-chips">
          <StatusChip tone={overallTone(readiness.summary.overall_status)}>
            {readiness.summary.overall_status.replaceAll("_", " ")}
          </StatusChip>
          <StatusChip tone={readiness.summary.required_missing_count > 0 ? "error" : "success"}>
            {`${readiness.summary.required_missing_count} required missing`}
          </StatusChip>
          <StatusChip tone="info">{`${readiness.payload_manifest.include_count} payload paths`}</StatusChip>
          <StatusChip tone="info">{readiness.payload_manifest.sidecar_default_dir}</StatusChip>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Tooling Summary</p>
        <p className="metric">{readiness.summary.present_count}</p>
        <p className="metric-sub">{`${readiness.summary.total} checks · ${readiness.summary.optional_missing_count} optional gaps`}</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Install Requests</p>
        <p className="metric">{missingChecks.length}</p>
        <p className="metric-sub">Request-only artifacts under {readiness.artifact_roots.install_requests}.</p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Repo Registry</p>
        <p className="metric">{registry?.summary.total_repos ?? 0}</p>
        <p className="metric-sub">{`${registry?.summary.moradin_sidecar_count ?? 0} repos with Moradin sidecars`}</p>
      </section>

      <section style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
          <div>
            <p className="card-head">Missing Tools</p>
            <p className="metric-sub" style={{ margin: "0.35rem 0 0" }}>
              Checked items stay selected until an install request artifact is created.
            </p>
          </div>
          <button className="btn primary" type="button" onClick={requestInstalls} disabled={creatingRequest || selectedToolIds.length === 0}>
            <ClipboardCheck size={15} />
            Create Install Request
          </button>
        </div>
        <div className="guide-callout-grid" style={{ marginTop: "0.9rem" }}>
          {missingChecks.length === 0 ? (
            <article className="guide-callout-card">
              <ClipboardCheck size={20} />
              <strong>No missing tools</strong>
              <p>All command-based readiness checks passed or are manual handoff modes.</p>
            </article>
          ) : (
            missingChecks.map((check) => (
              <article className="guide-callout-card" key={check.tool_id}>
                <label style={{ display: "flex", gap: "0.55rem", alignItems: "flex-start" }}>
                  <input
                    type="checkbox"
                    checked={selectedToolIds.includes(check.tool_id)}
                    onChange={() => toggleTool(check.tool_id)}
                    aria-label={`Select ${check.label}`}
                  />
                  <span>
                    <strong>{check.label}</strong>
                    <span style={{ display: "block", marginTop: "0.35rem" }}>
                      <StatusChip tone={readinessTone(check.status, check.required)}>{statusLabel(check)}</StatusChip>
                    </span>
                  </span>
                </label>
                {check.install_commands.map((command) => (
                  <code className="mono" key={command} style={{ display: "block", marginTop: "0.65rem", whiteSpace: "normal" }}>
                    {command}
                  </code>
                ))}
              </article>
            ))
          )}
        </div>
        {installRequest ? (
          <div style={{ borderTop: "1px solid var(--border-subtle)", marginTop: "0.9rem", paddingTop: "0.9rem" }}>
            <p className="card-head">Latest Request</p>
            <p className="metric-sub" style={{ marginBottom: "0.65rem" }}>{installRequest.safety}</p>
            <div className="projects-detail-list">
              <div>
                <strong>Request</strong>
                <small>{installRequest.request_id}</small>
              </div>
              <div>
                <strong>Markdown</strong>
                <small>{installRequest.artifact_paths.markdown}</small>
              </div>
              <div>
                <strong>JSON</strong>
                <small>{installRequest.artifact_paths.json}</small>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section style={{ gridColumn: "span 12" }}>
        <p className="card-head">Tool Checks</p>
        <div className="template-section-grid" style={{ marginTop: "0.8rem" }}>
          {readiness.groups.map((group) => (
            <article className="card card-pad" key={group.group_id}>
              <p className="card-head">{group.label}</p>
              <p className="metric-sub">{`${group.summary.present_count}/${group.summary.total} present`}</p>
              <div className="projects-detail-list" style={{ marginTop: "0.75rem" }}>
                {group.checks.map((check) => (
                  <div key={check.tool_id}>
                    <strong>{check.label}</strong>
                    <small>{check.version || check.detail}</small>
                    <StatusChip tone={readinessTone(check.status, check.required)}>{statusLabel(check)}</StatusChip>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", gap: "0.55rem", alignItems: "center" }}>
          <TerminalSquare size={18} />
          <p className="card-head" style={{ margin: 0 }}>Repo Registry</p>
        </div>
        <ScrollSurface className="effects-table-wrap" style={{ marginTop: "0.8rem" }}>
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Repo</th>
                <th>Scope</th>
                <th>Sidecar</th>
                <th>Adapters</th>
                <th>Reusable Status</th>
                <th>Advice</th>
              </tr>
            </thead>
            <tbody>
              {(registry?.repositories ?? []).map((repo) => (
                <tr key={repo.repo_id}>
                  <td>{repo.name}</td>
                  <td>{repo.scope}</td>
                  <td>{repo.moradin_sidecar_present ? "yes" : "no"}</td>
                  <td>{repo.adapter_surfaces.repo_brief_target ? "repo-brief" : "missing"}</td>
                  <td>{repo.artifact_reuse.latest_status_report || "none"}</td>
                  <td>{repo.rerun_advice}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollSurface>
      </section>
    </div>
  );
}
