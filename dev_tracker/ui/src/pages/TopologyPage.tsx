import { Link } from "react-router-dom";

import { MagicTile } from "../components/MagicTile";
import { StatusChip } from "../components/StatusChip";
import { useTracker } from "../lib/tracker-context";

export function TopologyPage() {
  const { snapshot, settings } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No combined topology data available.</div>;
  }

  const latestObjective = snapshot.project_overview.active_objectives[0] ?? null;
  const latestFlow = snapshot.harness_help.flows[0] ?? null;

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Combined Routing View</p>
        <p className="metric" style={{ fontSize: "1.2rem" }}>
          Project + Harness Topology
        </p>
        <p className="metric-sub">
          Use this combined surface to connect project service ownership, harness routing, approvals, and loop behavior without jumping between
          separate architecture reports first.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <StatusChip tone="info">{`Namespaces ${snapshot.topology.namespaces.length}`}</StatusChip>
          <StatusChip tone="info">{`Boundaries ${snapshot.topology.boundaries.length}`}</StatusChip>
          <StatusChip tone="success">{`Flows ${snapshot.harness_help.flows.length}`}</StatusChip>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.95rem" }}>
          <Link className="btn" to="/project-topology">
            Project Topology
          </Link>
          <Link className="btn" to="/harness-topology">
            Harness Topology
          </Link>
        </div>
      </section>

      <MagicTile reducedMotion={settings.reducedMotion}>
        <p className="card-head">Project Context</p>
        <p style={{ margin: "0.45rem 0 0", fontWeight: 700 }}>{snapshot.project_overview.mission}</p>
        <p className="muted" style={{ margin: "0.45rem 0 0" }}>
          {latestObjective ? latestObjective.goal : "No active objective recorded."}
        </p>
      </MagicTile>

      <MagicTile reducedMotion={settings.reducedMotion}>
        <p className="card-head">Harness Flow</p>
        <p style={{ margin: "0.45rem 0 0", fontWeight: 700 }}>{latestFlow?.title ?? "No harness flow recorded."}</p>
        <p className="muted" style={{ margin: "0.45rem 0 0" }}>
          {latestFlow?.trigger ?? "No trigger data available."}
        </p>
      </MagicTile>

      <MagicTile reducedMotion={settings.reducedMotion}>
        <p className="card-head">Approvals</p>
        <p style={{ margin: "0.45rem 0 0", fontWeight: 700 }}>{snapshot.review_queue.pending_approvals}</p>
        <p className="muted" style={{ margin: "0.45rem 0 0" }}>
          Pending human-gate approvals connected to routing and change execution.
        </p>
      </MagicTile>

      <MagicTile reducedMotion={settings.reducedMotion}>
        <p className="card-head">Policy Domains</p>
        <p style={{ margin: "0.45rem 0 0", fontWeight: 700 }}>{snapshot.policies.domains.length}</p>
        <p className="muted" style={{ margin: "0.45rem 0 0" }}>
          Governance areas available for policy and checklist routing.
        </p>
      </MagicTile>
    </div>
  );
}

