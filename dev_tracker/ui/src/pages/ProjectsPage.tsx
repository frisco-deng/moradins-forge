import { useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { AttentionChip } from "../components/AttentionChip";
import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import { encodeProjectRouteId, OVERVIEW_MANAGER_PROJECT_ID, writeOverviewActiveProject } from "../lib/overview-project";
import { useTracker } from "../lib/tracker-context";
import { deriveProjectsWorkspaceModel } from "../lib/workspace-models";

function setProjectRoute(navigate: ReturnType<typeof useNavigate>, projectId: string, route = "overview") {
  writeOverviewActiveProject(projectId);
  void navigate(`/project/${encodeProjectRouteId(projectId)}/${route}`);
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const { snapshot, builderStatus } = useTracker();
  const [searchParams, setSearchParams] = useSearchParams();

  if (!snapshot) {
    return <div className="card card-pad">Project portfolio is unavailable until the tracker snapshot loads.</div>;
  }

  const selectedProject = searchParams.get("project") ?? "";
  const query = searchParams.get("q") ?? "";
  const statusFilter = searchParams.get("status") ?? "all";
  const model = deriveProjectsWorkspaceModel({ snapshot, builderStatus, selectedProject });
  const attentionItems = model.rows
    .filter((row) => row.health.tone === "warning")
    .map((row) => ({
      label: row.label,
      to: row.scope === "manager" ? "/project/manager/overview" : `/project/${encodeProjectRouteId(row.id)}/overview`,
      detail: row.health.label,
    }));

  const visibleRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return model.rows.filter((row) => {
      if (statusFilter === "attention" && row.health.tone !== "warning") {
        return false;
      }
      if (statusFilter === "stable" && row.health.tone !== "success") {
        return false;
      }
      if (statusFilter === "tracked" && row.scope !== "tracked") {
        return false;
      }
      if (statusFilter === "manager" && row.scope !== "manager") {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      return `${row.label} ${row.path} ${row.connection} ${row.lastActivity}`.toLowerCase().includes(normalizedQuery);
    });
  }, [model.rows, query, statusFilter]);

  const selectedRow =
    visibleRows.find((row) => row.id === selectedProject) ??
    model.rows.find((row) => row.id === selectedProject) ??
    visibleRows[0] ??
    model.rows[0] ??
    null;

  const updateFilters = (next: Record<string, string>) => {
    const updated = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (!value) {
        updated.delete(key);
      } else {
        updated.set(key, value);
      }
    }
    setSearchParams(updated, { replace: true });
  };

  return (
    <div className="page-grid">
      <section className="card card-pad workspace-header-card compact" style={{ gridColumn: "span 12" }}>
        <div className="workspace-header-copy">
          <div>
            <p className="card-head">Portfolio</p>
            <h2 className="workspace-header-title">Tracked Projects</h2>
            <p className="workspace-header-description">
              View the manager repo and tracked downstream repos as one portfolio, then open, deploy, validate, or compare them without
              leaving the control plane.
            </p>
          </div>
          <div className="workspace-header-actions">
            <Link className="btn primary" to="/deploy/builder">
              Add or Import Project
            </Link>
            <Link className="btn" to="/payload">
              Moradin Payload
            </Link>
          </div>
        </div>
        <div className="workspace-header-chips">
          <StatusChip tone="info">{`${model.totalProjects} total workspaces`}</StatusChip>
          <StatusChip tone="info">{`${model.trackedProjects} tracked repos`}</StatusChip>
          {model.attentionProjects > 0 ? (
            <AttentionChip
              label={`${model.attentionProjects} need attention`}
              summary="These workspaces still have unresolved review, deploy, or drift signals."
              items={attentionItems}
            />
          ) : (
            <StatusChip tone="success">No attention needed</StatusChip>
          )}
        </div>
        <div className="projects-toolbar projects-filters">
          <input
            className="projects-search"
            type="search"
            value={query}
            onChange={(event) => updateFilters({ q: event.target.value })}
            placeholder="Search by repo name, path, or last activity"
            aria-label="Search tracked projects"
          />
          <select
            className="select projects-filter-select"
            aria-label="Filter project health"
            value={statusFilter}
            onChange={(event) => updateFilters({ status: event.target.value })}
          >
            <option value="all">All workspaces</option>
            <option value="attention">Needs attention</option>
            <option value="stable">Stable</option>
            <option value="tracked">Tracked repos</option>
            <option value="manager">Manager repo</option>
          </select>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <p className="card-head">Portfolio Explorer</p>
        <ScrollSurface className="effects-table-wrap" style={{ marginTop: "0.8rem" }}>
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Scope</th>
                <th>Path</th>
                <th>Connection</th>
                <th>Harness</th>
                <th>Drift</th>
                <th>Health</th>
                <th>Last Activity</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr
                  key={row.id}
                  className={`portfolio-row ${selectedRow?.id === row.id ? "active" : ""}`.trim()}
                  onClick={() => updateFilters({ project: row.id })}
                >
                  <td>
                    <button type="button" className="table-link-button" onClick={() => updateFilters({ project: row.id })}>
                      {row.label}
                    </button>
                  </td>
                  <td>{row.scope === "manager" ? "Manager" : "Tracked"}</td>
                  <td className="mono">{row.path}</td>
                  <td>{row.connection}</td>
                  <td>{row.harnessVersion}</td>
                  <td>
                    <StatusChip tone={row.templateDrift.tone}>{row.templateDrift.label}</StatusChip>
                  </td>
                  <td>
                    <StatusChip tone={row.health.tone}>{row.health.label}</StatusChip>
                  </td>
                  <td>{row.lastActivity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Selected Workspace</p>
        {selectedRow ? (
          <div className="projects-detail">
            <div>
              <p className="metric" style={{ fontSize: "1.2rem" }}>
                {selectedRow.label}
              </p>
              <p className="metric-sub mono">{selectedRow.path}</p>
            </div>
            <div className="projects-card-chips">
              <StatusChip tone={selectedRow.scope === "manager" ? "info" : "success"}>
                {selectedRow.scope === "manager" ? "Manager repo" : "Tracked repo"}
              </StatusChip>
              {selectedRow.health.tone === "warning" ? (
                <AttentionChip
                  label={selectedRow.health.label}
                  summary={`${selectedRow.label} requires operator attention before it is considered stable.`}
                  items={[
                    {
                      label: `Open ${selectedRow.label}`,
                      to: selectedRow.scope === "manager" ? "/project/manager/overview" : `/project/${encodeProjectRouteId(selectedRow.id)}/overview`,
                      detail: "Open the workspace and inspect the affected status.",
                    },
                  ]}
                />
              ) : (
                <StatusChip tone={selectedRow.health.tone}>{selectedRow.health.label}</StatusChip>
              )}
            </div>
            <div className="projects-detail-list">
              <div>
                <strong>Connection</strong>
                <small>{selectedRow.connection}</small>
              </div>
              <div>
                <strong>Harness version</strong>
                <small>{selectedRow.harnessVersion}</small>
              </div>
              <div>
                <strong>Payload drift</strong>
                <small>{selectedRow.templateDrift.label}</small>
              </div>
              <div>
                <strong>Docs indexed</strong>
                <small>{selectedRow.docsIndexed}</small>
              </div>
              <div>
                <strong>Pending approvals</strong>
                <small>{selectedRow.pendingApprovals}</small>
              </div>
              <div>
                <strong>Last activity</strong>
                <small>{selectedRow.lastActivity}</small>
              </div>
            </div>
            <div className="projects-card-actions">
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  const targetProject = selectedRow.scope === "manager" ? OVERVIEW_MANAGER_PROJECT_ID : selectedRow.id;
                  setProjectRoute(navigate, targetProject);
                }}
              >
                Open Workspace
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  const targetProject = selectedRow.scope === "manager" ? OVERVIEW_MANAGER_PROJECT_ID : selectedRow.id;
                  setProjectRoute(navigate, targetProject, "operations/status");
                }}
              >
                Validate
              </button>
              <Link className="btn" to="/deploy/builder">
                Deploy
              </Link>
              <Link className="btn" to="/payload">
                Compare Payload
              </Link>
            </div>
          </div>
        ) : (
          <div className="projects-detail">
            <p className="metric" style={{ fontSize: "1.1rem" }}>
              No workspace matches the current filter
            </p>
            <p className="metric-sub">Clear the search or filter to reopen the manager repo or one of the tracked projects.</p>
          </div>
        )}
      </section>
    </div>
  );
}
