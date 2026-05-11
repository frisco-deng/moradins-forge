import {
  Background,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";

import { FILL_SOURCE_META, type DeployWorkflowId, WORKFLOW_GRAPH_SPECS } from "../lib/deploy-map-model";

interface HarnessFlowVisualizerProps {
  workflow: DeployWorkflowId;
  title?: string;
  subtitle?: string;
  height?: number;
}

type GraphLayout = "horizontal" | "vertical";

function buildGraph(workflow: DeployWorkflowId, layout: GraphLayout): { nodes: Node[]; edges: Edge[]; description: string } {
  const graph = WORKFLOW_GRAPH_SPECS[workflow];
  const horizontal = layout === "horizontal";
  const nodes: Node[] = graph.steps.map((step, index) => {
    const meta = FILL_SOURCE_META[step.tone];
    return {
      id: step.id,
      position: horizontal ? { x: index * 290, y: 28 } : { x: 40, y: index * 180 },
      sourcePosition: horizontal ? Position.Right : Position.Bottom,
      targetPosition: horizontal ? Position.Left : Position.Top,
      data: {
        label: (
          <div>
            <p style={{ margin: 0, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.7 }}>
              {meta.label}
            </p>
            <strong style={{ display: "block", marginTop: "0.35rem" }}>{step.title}</strong>
            <p style={{ margin: "0.45rem 0 0", fontSize: "0.82rem", lineHeight: 1.45 }}>{step.detail}</p>
          </div>
        ),
      },
      style: {
        width: 230,
        borderRadius: 18,
        border: `1px solid ${meta.accent}`,
        background: meta.background,
        color: "var(--text)",
        padding: "0.35rem",
        boxShadow: "0 12px 30px rgba(0, 0, 0, 0.18)",
      },
      draggable: false,
      selectable: false,
      connectable: false,
    };
  });

  const edges: Edge[] = [];
  for (let index = 0; index < graph.steps.length - 1; index += 1) {
    const step = graph.steps[index];
    const nextStep = graph.steps[index + 1];
    if (!step || !nextStep) {
      continue;
    }
    edges.push({
      id: `${step.id}-${nextStep.id}`,
      source: step.id,
      target: nextStep.id,
      type: "smoothstep",
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "rgba(255,255,255,0.56)",
      },
      style: {
        stroke: "rgba(255,255,255,0.38)",
        strokeWidth: 2,
      },
    });
  }

  return {
    nodes,
    edges,
    description: graph.description,
  };
}

export function HarnessFlowVisualizer({
  workflow,
  title = "Deploy Flow Graph",
  subtitle,
  height = 320,
}: HarnessFlowVisualizerProps) {
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window === "undefined" ? 1200 : window.innerWidth));

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const layout: GraphLayout = viewportWidth < 860 ? "vertical" : "horizontal";
  const graph = useMemo(() => buildGraph(workflow, layout), [layout, workflow]);

  return (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
        {subtitle ?? graph.description}
      </p>
      <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
        {Object.entries(FILL_SOURCE_META).map(([sourceKind, meta]) => (
          <span
            key={sourceKind}
            className="mono"
            style={{
              padding: "0.35rem 0.6rem",
              borderRadius: 999,
              border: `1px solid ${meta.accent}`,
              background: meta.background,
              fontSize: "0.74rem",
            }}
          >
            {meta.label}
          </span>
        ))}
      </div>
      <div style={{ marginTop: "0.9rem", height }}>
        <ReactFlow
          fitView
          fitViewOptions={{ padding: 0.18, minZoom: 0.82, maxZoom: 1 }}
          nodes={graph.nodes}
          edges={graph.edges}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color="rgba(255,255,255,0.12)" />
        </ReactFlow>
      </div>
    </section>
  );
}
