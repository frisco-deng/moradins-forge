import type { ArchitectureStatus, ArchitectureTreeNode } from "../lib/architecture-tree";
import { resolveArchitectureStatus } from "../lib/architecture-tree";
import { TooltipHint } from "./TooltipHint";

interface ArchitectureTreeProps {
  title: string;
  subtitle: string;
  nodes: ArchitectureTreeNode[];
  existingPaths: Set<string>;
  statusByPath?: Record<string, ArchitectureStatus>;
  defaultOpenNodeId?: string;
}

function statusLabel(status: ArchitectureStatus) {
  if (status === "pass") {
    return "Present";
  }
  if (status === "missing") {
    return "Missing";
  }
  return "Unchecked";
}

function statusTone(status: ArchitectureStatus) {
  if (status === "pass") {
    return "success";
  }
  if (status === "missing") {
    return "error";
  }
  return "info";
}

export function ArchitectureTree({
  title,
  subtitle,
  nodes,
  existingPaths,
  statusByPath = {},
  defaultOpenNodeId = "",
}: ArchitectureTreeProps) {
  return (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
        <span>{title}</span>
        <TooltipHint text="Tree view of base harness architecture surfaces with present/missing indicators." />
      </h3>
      <p className="section-subtitle">{subtitle}</p>
      <div className="architecture-tree">
        {nodes.map((node) => (
          <details
            key={node.id}
            className="architecture-node"
            open={defaultOpenNodeId ? defaultOpenNodeId === node.id : node === nodes[0]}
          >
            <summary>
              <div>
                <strong>{node.label}</strong>
                <p className="muted">{node.description}</p>
              </div>
            </summary>
            <ul>
              {node.entries.map((entry) => {
                const status = resolveArchitectureStatus(existingPaths, entry, statusByPath[entry.path]);
                return (
                  <li key={entry.id} className="architecture-entry">
                    <div>
                      <p>{entry.label}</p>
                      <p className="muted">{entry.description}</p>
                      <p className="mono architecture-path">{entry.path}</p>
                    </div>
                    <span className={`chip ${statusTone(status)}`}>{statusLabel(status)}</span>
                  </li>
                );
              })}
            </ul>
          </details>
        ))}
      </div>
    </section>
  );
}
