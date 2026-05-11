import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { HarnessFlowVisualizer } from "../components/HarnessFlowVisualizer";
import { PageHero } from "../components/PageHero";
import { StatusChip } from "../components/StatusChip";
import { TemplateFillTree } from "../components/TemplateFillTree";
import { getDocByPath } from "../lib/doc-helpers";
import {
  DEPLOY_MAP_PREVIEW_STORAGE_KEY,
  type DeployMapPreviewV1,
  type DeployWorkflowId,
  WORKFLOW_GRAPH_SPECS,
} from "../lib/deploy-map-model";
import { useTracker } from "../lib/tracker-context";

function readPreview(): DeployMapPreviewV1 | null {
  try {
    const raw = localStorage.getItem(DEPLOY_MAP_PREVIEW_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<DeployMapPreviewV1>;
    if (parsed.version !== "DeployMapPreviewV1" || !Array.isArray(parsed.generated_files)) {
      return null;
    }
    const workflow =
      parsed.workflow === "existing_project" || parsed.workflow === "import_existing_harness"
        ? parsed.workflow
        : "new_project";
    return {
      version: "DeployMapPreviewV1",
      generated_at: String(parsed.generated_at ?? ""),
      workflow,
      generated_files: parsed.generated_files.map((value) => String(value)),
    };
  } catch {
    return null;
  }
}

export function DeployMapPage() {
  const { snapshot } = useTracker();
  const [workflow, setWorkflow] = useState<DeployWorkflowId>("new_project");
  const [preview, setPreview] = useState<DeployMapPreviewV1 | null>(null);

  useEffect(() => {
    const savedPreview = readPreview();
    if (savedPreview) {
      setPreview(savedPreview);
      setWorkflow(savedPreview.workflow);
    }
  }, []);

  const quickStartDoc = snapshot ? getDocByPath(snapshot, "docs/11_ops/quick_start.md") : null;
  const runbookDoc = snapshot ? getDocByPath(snapshot, "docs/11_ops/project_builder_runbook.md") : null;
  const visualRefDoc = snapshot ? getDocByPath(snapshot, "docs/design_docs/project_builder_visual_reference.md") : null;
  const graph = useMemo(() => WORKFLOW_GRAPH_SPECS[workflow], [workflow]);

  return (
    <div className="page-grid">
      <PageHero
        compact
        title="Deploy Map"
        subtitle="Visual explanation of what Moradin deploys, what is prefilled by the payload, and where operator or scan data changes the output."
        eyebrow="Payload Visualizer"
        chips={
          <>
            <StatusChip tone="info">Linux-hosted companion</StatusChip>
            <StatusChip tone="success">Baseline tree always visible</StatusChip>
            <StatusChip tone={preview ? "warning" : "info"}>{preview ? "Last builder output loaded" : "No builder output cached yet"}</StatusChip>
          </>
        }
        actions={
          <>
            <Link className="btn" to="/deploy/quick-start" style={{ textDecoration: "none" }}>
              Quick Start
            </Link>
            <Link className="btn" to="/deploy/readiness" style={{ textDecoration: "none" }}>
              Readiness
            </Link>
            <Link className="btn" to="/deploy/builder" style={{ textDecoration: "none" }}>
              Builder
            </Link>
            <Link className="btn" to="/deploy/status" style={{ textDecoration: "none" }}>
              Verify
            </Link>
          </>
        }
      >
        <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap" }}>
          {(Object.keys(WORKFLOW_GRAPH_SPECS) as DeployWorkflowId[]).map((workflowId) => (
            <button
              key={workflowId}
              type="button"
              className={`chip interactive ${workflow === workflowId ? "success" : "info"}`.trim()}
              onClick={() => setWorkflow(workflowId)}
            >
              {WORKFLOW_GRAPH_SPECS[workflowId].title}
            </button>
          ))}
          {runbookDoc ? (
            <Link className="btn" to={`/docs/${runbookDoc.id}`} style={{ textDecoration: "none" }}>
              Builder Runbook
            </Link>
          ) : null}
          {visualRefDoc ? (
            <Link className="btn" to={`/docs/${visualRefDoc.id}`} style={{ textDecoration: "none" }}>
              Visual Reference
            </Link>
          ) : null}
          {quickStartDoc ? (
            <Link className="btn" to={`/docs/${quickStartDoc.id}`} style={{ textDecoration: "none" }}>
              Raw Quick Start Doc
            </Link>
          ) : null}
        </div>
      </PageHero>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Workflow View</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          {graph.description}
        </p>
      </section>

      <HarnessFlowVisualizer workflow={workflow} subtitle={graph.description} height={preview ? 340 : 320} />

      <TemplateFillTree
        generatedFiles={preview?.generated_files ?? []}
        title="Baseline Harness Tree"
        description={
          preview
            ? `Baseline paths are shown beside the last ${preview.workflow.replaceAll("_", " ")} output captured on ${new Date(preview.generated_at).toLocaleString()}.`
            : "This baseline tree shows what the harness can prefill before any project-specific output exists. Generate or deploy from Builder to cache a live fill result here."
        }
      />
    </div>
  );
}
