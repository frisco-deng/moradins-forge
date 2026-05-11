import { Link } from "react-router-dom";

import { SEEDED_DEPLOY_EXAMPLE } from "../lib/seeded-deploy-example";
import { StatusChip } from "./StatusChip";

interface SeededDeployExamplePanelProps {
  surface: "quick-start" | "builder" | "status";
}

export function SeededDeployExamplePanel({ surface }: SeededDeployExamplePanelProps) {
  const showVerifySummary = surface !== "builder";
  const showPhaseSummary = surface !== "status";

  return (
    <section className="card card-pad seeded-example-panel">
      <div className="seeded-example-head">
        <div>
          <p className="card-head">Deploy Example</p>
          <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Preview-only walkthrough for a seeded existing-project deployment.</h3>
          <p className="metric-sub" style={{ margin: 0 }}>
            This example is deterministic and read-only. It shows what the Builder and Verify pages should look like after a guarded sidecar deploy without triggering any execution.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
          <StatusChip tone="info">{SEEDED_DEPLOY_EXAMPLE.workflow}</StatusChip>
          <StatusChip tone="warning">preview only</StatusChip>
        </div>
      </div>

      <div className="seeded-example-grid">
        <article className="seeded-example-card">
          <strong>{SEEDED_DEPLOY_EXAMPLE.repoName}</strong>
          <p className="metric-sub">{SEEDED_DEPLOY_EXAMPLE.goal}</p>
          <p className="metric-sub" style={{ marginBottom: 0 }}>
            Constraints: {SEEDED_DEPLOY_EXAMPLE.constraints}
          </p>
        </article>
        <article className="seeded-example-card">
          <strong>Selected output</strong>
          <p className="metric-sub mono" style={{ marginBottom: 0 }}>
            {SEEDED_DEPLOY_EXAMPLE.sidecarPath}
          </p>
        </article>
      </div>

      {showPhaseSummary ? (
        <article className="seeded-example-card" style={{ marginTop: "0.85rem" }}>
          <strong>Builder preview</strong>
          <p className="metric-sub" style={{ marginBottom: 0 }}>
            {SEEDED_DEPLOY_EXAMPLE.phaseSummary}
          </p>
        </article>
      ) : null}

      {showVerifySummary ? (
        <article className="seeded-example-card" style={{ marginTop: "0.85rem" }}>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginBottom: "0.55rem" }}>
            <StatusChip tone="warning">{`overall ${SEEDED_DEPLOY_EXAMPLE.verifySummary.overall}`}</StatusChip>
            <StatusChip tone="warning">{`manual ${SEEDED_DEPLOY_EXAMPLE.verifySummary.manualRequired}`}</StatusChip>
            <StatusChip tone="error">{`missing ${SEEDED_DEPLOY_EXAMPLE.verifySummary.missing}`}</StatusChip>
          </div>
          <strong>Verify preview</strong>
          <p className="metric-sub" style={{ marginBottom: 0 }}>
            {SEEDED_DEPLOY_EXAMPLE.verifySummary.nextAction}
          </p>
        </article>
      ) : null}

      <div className="seeded-example-grid" style={{ marginTop: "0.85rem" }}>
        <article className="seeded-example-card">
          <strong>Expected artifacts</strong>
          <ul style={{ margin: "0.55rem 0 0", paddingLeft: "1rem" }}>
            {SEEDED_DEPLOY_EXAMPLE.artifacts.map((artifact) => (
              <li key={artifact}>{artifact}</li>
            ))}
          </ul>
        </article>
        <article className="seeded-example-card">
          <strong>Critical gaps</strong>
          <ul style={{ margin: "0.55rem 0 0", paddingLeft: "1rem" }}>
            {SEEDED_DEPLOY_EXAMPLE.criticalGaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </article>
      </div>

      {surface === "quick-start" ? (
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.9rem" }}>
          <Link className="btn" to="/deploy/builder?demo=seeded" style={{ textDecoration: "none" }}>
            Preview Builder Example
          </Link>
          <Link className="btn" to="/deploy/status?demo=seeded" style={{ textDecoration: "none" }}>
            Preview Verify Example
          </Link>
        </div>
      ) : null}
    </section>
  );
}
