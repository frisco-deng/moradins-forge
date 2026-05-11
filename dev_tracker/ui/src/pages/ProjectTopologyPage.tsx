import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { MagicTile } from "../components/MagicTile";
import { PageHero } from "../components/PageHero";
import { RoutingSurfacesCard } from "../components/RoutingSurfacesCard";
import { StatusChip } from "../components/StatusChip";
import { StatusPillButton } from "../components/StatusPillButton";
import { TooltipHint } from "../components/TooltipHint";
import { useTracker } from "../lib/tracker-context";

function inventoryTone(status: string): "success" | "warning" | "info" {
  if (status === "implemented") {
    return "success";
  }
  if (status === "planned_only") {
    return "warning";
  }
  return "info";
}

type TopologyStatusFilter = "all" | "implemented" | "awaiting";

export function ProjectTopologyPage() {
  const { snapshot, settings } = useTracker();
  const [searchParams, setSearchParams] = useSearchParams();
  const inventoryRows = snapshot?.service_inventory.rows ?? [];

  const statusFilter = ((searchParams.get("status") ?? "all").toLowerCase() === "implemented"
    ? "implemented"
    : (searchParams.get("status") ?? "all").toLowerCase() === "awaiting"
      ? "awaiting"
      : "all") as TopologyStatusFilter;
  const serviceFilter = (searchParams.get("service") ?? "").trim();

  const filteredInventoryRows = useMemo(() => {
    return inventoryRows.filter((row) => {
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "implemented" && row.status === "implemented") ||
        (statusFilter === "awaiting" && row.status === "planned_only");
      const matchesService = !serviceFilter || row.service === serviceFilter;
      return matchesStatus && matchesService;
    });
  }, [inventoryRows, serviceFilter, statusFilter]);

  if (!snapshot) {
    return <div className="card card-pad">No project topology data available.</div>;
  }

  function setFilter(nextStatus: TopologyStatusFilter, nextService = serviceFilter) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("status", nextStatus);
    if (nextService) {
      nextParams.set("service", nextService);
    } else {
      nextParams.delete("service");
    }
    setSearchParams(nextParams, { replace: true });
  }

  return (
    <div className="page-grid">
      <PageHero
        title="Project Topology"
        subtitle="Project-facing topology for mission, objective alignment, and service ownership boundaries."
        eyebrow="Delivery Architecture"
        chips={
          <>
            <StatusChip tone="info">{`Catalog targets ${snapshot.service_inventory.planned_count}`}</StatusChip>
            <StatusChip tone="success">{`Implemented ${snapshot.service_inventory.implemented_count}`}</StatusChip>
            <StatusChip tone="warning">{`Awaiting implementation ${snapshot.service_inventory.planned_only_count}`}</StatusChip>
          </>
        }
      >
        <div className="page-hero-inline-grid">
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Mission</p>
            <p style={{ margin: "0.35rem 0 0" }}>{snapshot.project_overview.mission}</p>
          </div>
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Phase Status Summary</p>
            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
              <StatusChip tone="success">{`Completed ${snapshot.project_overview.phase_status_summary.completed}`}</StatusChip>
              <StatusChip tone="warning">{`Pending ${snapshot.project_overview.phase_status_summary.pending}`}</StatusChip>
              <StatusChip tone="info">{`Other ${snapshot.project_overview.phase_status_summary.other}`}</StatusChip>
            </div>
          </div>
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Active Filter</p>
            <p style={{ margin: "0.35rem 0 0" }}>
              {serviceFilter ? `${statusFilter} / ${serviceFilter}` : statusFilter}
            </p>
          </div>
        </div>
      </PageHero>

      <RoutingSurfacesCard
        links={[
          { to: "/cycles", label: "Loop Processes: Gate State" },
          { to: "/reviews/exchange", label: "Activity: Approval and Routing" },
          { to: "/help", label: "Help: Harness Process Guides" },
          { to: "/harness-topology", label: "Harness Topology" },
        ]}
        subtitle="Project-to-harness cross-links for loop process state and approval routing."
      />

      {snapshot.topology.namespaces.map((namespace) => (
        <MagicTile key={namespace.namespace} reducedMotion={settings.reducedMotion}>
          <p className="card-head">{namespace.namespace}</p>
          <p style={{ margin: "0.4rem 0", fontWeight: 600 }}>{namespace.intent}</p>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            {namespace.containers_services}
          </p>
        </MagicTile>
      ))}

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.8rem", flexWrap: "wrap", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
              <span>Service Inventory</span>
              <TooltipHint text="Filter the topology by current implementation state or jump directly to a single service." />
            </h3>
            <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              Filterable execution view of catalog targets versus implemented runtime surfaces.
            </p>
          </div>
          {serviceFilter ? (
            <button className="btn subtle" type="button" onClick={() => setFilter(statusFilter, "")}>
              Clear Service Filter
            </button>
          ) : null}
        </div>

        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
          <StatusPillButton tone={statusFilter === "all" ? "info" : "info"} onClick={() => setFilter("all")}>
            All Services
          </StatusPillButton>
          <StatusPillButton tone="success" onClick={() => setFilter("implemented")}>
            Implemented
          </StatusPillButton>
          <StatusPillButton tone="warning" onClick={() => setFilter("awaiting")}>
            Awaiting Implementation
          </StatusPillButton>
          <StatusChip tone="info">{`${filteredInventoryRows.length} filtered rows`}</StatusChip>
          {serviceFilter ? <StatusChip tone="warning">{`Service ${serviceFilter}`}</StatusChip> : null}
        </div>

        <div className="effects-table-wrap scroll-surface" style={{ marginTop: "0.8rem" }}>
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Domain</th>
                <th>Phase Target</th>
                <th>Implementation Surface</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredInventoryRows.map((row) => (
                <tr key={`${row.service}-${row.implementation_surface || "planned"}-${row.phase_target}`}>
                  <td>
                    <button
                      type="button"
                      className="chip-link mono"
                      onClick={() => setFilter(statusFilter, row.service)}
                      style={{ padding: 0, background: "transparent", border: 0 }}
                    >
                      {row.service}
                    </button>
                  </td>
                  <td>{row.domain}</td>
                  <td>{row.phase_target}</td>
                  <td className="mono">{row.implementation_surface || "--"}</td>
                  <td>
                    <StatusChip tone={inventoryTone(row.status)}>{row.status === "planned_only" ? "awaiting implementation" : row.status}</StatusChip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Boundary Matrix</h3>
        <div className="effects-table-wrap scroll-surface">
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Primary Role</th>
                <th>Owns</th>
                <th>Does Not Own</th>
                <th>Contracts</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.topology.boundaries.map((boundary) => (
                <tr key={boundary.service}>
                  <td className="mono">{boundary.service}</td>
                  <td>{boundary.primary_role}</td>
                  <td>{boundary.owns}</td>
                  <td>{boundary.does_not_own}</td>
                  <td className="mono">{boundary.key_contracts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {[
            "docs/00_overview/architecture.md",
            "docs/00_overview/implementation_phases.md",
            "docs/00_overview/service_catalog.md",
            "docs/03_architecture/container_topology.md",
            "docs/03_architecture/service_boundaries.md",
            "docs/04_services/index.md",
          ].map((path) => {
            const doc = snapshot.docs.find((entry) => entry.relative_path === path);
            if (!doc) {
              return null;
            }

            return (
              <Link key={path} to={`/docs/${doc.id}`} className="btn" style={{ textDecoration: "none" }}>
                {doc.title}
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
