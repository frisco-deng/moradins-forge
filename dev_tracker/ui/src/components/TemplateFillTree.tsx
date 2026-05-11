import { useMemo } from "react";

import {
  baselineTemplatePaths,
  classifyGeneratedFileSource,
  FILL_SOURCE_META,
  type FillSourceKind,
} from "../lib/deploy-map-model";

interface TemplateFillTreeProps {
  generatedFiles?: string[];
  title?: string;
  description?: string;
}

interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[];
  preview: boolean;
}

function insertTreePath(root: TreeNode, relativePath: string, preview: boolean) {
  const parts = relativePath.split("/").filter(Boolean);
  let cursor = root;
  let currentPath = "";

  for (const part of parts) {
    currentPath = currentPath ? `${currentPath}/${part}` : part;
    let next = cursor.children.find((child) => child.name === part);
    if (!next) {
      next = {
        name: part,
        path: currentPath,
        children: [],
        preview,
      };
      cursor.children.push(next);
      cursor.children.sort((left, right) => left.name.localeCompare(right.name));
    }
    next.preview = next.preview && preview;
    cursor = next;
  }
}

function buildTree(paths: Array<{ path: string; preview: boolean }>): TreeNode {
  const root: TreeNode = {
    name: "/",
    path: "",
    children: [],
    preview: true,
  };

  for (const entry of paths) {
    insertTreePath(root, entry.path.replaceAll("\\", "/"), entry.preview);
  }

  return root;
}

function countLeaves(node: TreeNode): number {
  if (node.children.length === 0) {
    return 1;
  }
  return node.children.reduce((sum, child) => sum + countLeaves(child), 0);
}

function renderTree(node: TreeNode) {
  if (node.children.length === 0) {
    return (
      <li key={node.path} className={`template-fill-leaf mono ${node.preview ? "preview" : ""}`.trim()}>
        <span className="template-fill-entry-name" title={node.path}>
          {node.name}
        </span>
        {node.preview ? <span className="template-fill-badge">(baseline)</span> : null}
      </li>
    );
  }

  return (
    <li key={node.path}>
      <details open={node.path.split("/").length <= 1} className="template-fill-details">
        <summary className="template-fill-summary mono">
          <span className="template-fill-entry-name" title={node.path}>
            {node.name}
          </span>
          <span className="template-fill-count">({countLeaves(node)})</span>
        </summary>
        <ul className="template-fill-children">
          {node.children.map((child) => renderTree(child))}
        </ul>
      </details>
    </li>
  );
}

export function TemplateFillTree({
  generatedFiles = [],
  title = "Payload Fill Tree",
  description = "Baseline Moradin payload paths stay visible before generation. When output exists, the same tree highlights concrete files filled by each source.",
}: TemplateFillTreeProps) {
  const groupedTrees = useMemo(() => {
    const baseline = baselineTemplatePaths();
    const actual = generatedFiles.map((path) => ({
      path,
      sourceKind: classifyGeneratedFileSource(path),
      preview: false,
    }));

    return (Object.keys(FILL_SOURCE_META) as FillSourceKind[]).map((sourceKind) => {
      const paths = [...baseline.filter((entry) => entry.sourceKind === sourceKind), ...actual.filter((entry) => entry.sourceKind === sourceKind)];
      return {
        sourceKind,
        tree: buildTree(paths),
        actualCount: actual.filter((entry) => entry.sourceKind === sourceKind).length,
      };
    });
  }, [generatedFiles]);

  return (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
        {description}
      </p>
      <div className="template-fill-grid">
        {groupedTrees.map(({ sourceKind, tree, actualCount }) => {
          const meta = FILL_SOURCE_META[sourceKind];
          return (
            <article
              key={sourceKind}
              className="card card-pad template-fill-card"
              style={{
                borderColor: meta.accent,
                background: meta.background,
              }}
            >
              <div className="template-fill-card-head">
                <p className="card-head" style={{ marginTop: 0 }}>
                  {meta.label}
                </p>
                <span className="mono template-fill-card-state">
                  {actualCount > 0 ? `${actualCount} concrete` : "baseline only"}
                </span>
              </div>
              <ul className="template-fill-list">
                {tree.children.map((child) => renderTree(child))}
              </ul>
            </article>
          );
        })}
      </div>
    </section>
  );
}
