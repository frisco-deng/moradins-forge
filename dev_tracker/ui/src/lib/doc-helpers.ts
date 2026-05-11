import type { DocRecordV1, TrackerSnapshotVLatest } from "./contracts";
import { resolveRelatedPath } from "./loaders";

export function mapDocsByPath(snapshot: TrackerSnapshotVLatest): Map<string, DocRecordV1> {
  const map = new Map<string, DocRecordV1>();
  for (const doc of snapshot.docs) {
    map.set(doc.relative_path, doc);
  }
  return map;
}

export function getDocByPath(snapshot: TrackerSnapshotVLatest, relativePath: string): DocRecordV1 | null {
  return snapshot.docs.find((doc) => doc.relative_path === relativePath) ?? null;
}

export function resolveRelatedDocs(snapshot: TrackerSnapshotVLatest, doc: DocRecordV1): DocRecordV1[] {
  const byPath = mapDocsByPath(snapshot);
  const related = [] as DocRecordV1[];

  for (const entry of doc.related_docs) {
    const resolved = resolveRelatedPath(doc.relative_path, entry);
    if (!resolved) {
      continue;
    }

    const match = byPath.get(resolved);
    if (match) {
      related.push(match);
    }
  }

  return related;
}

export function sectionLabel(section: string): string {
  if (section === "root") {
    return "Root";
  }
  if (section === "99_generated") {
    return "Generated";
  }
  if (section === "artifacts") {
    return "Harness Artifacts";
  }
  if (section === "exec_plans") {
    return "Exec Plans";
  }
  if (section === "design_docs") {
    return "Design Docs";
  }
  if (section === "product_specs") {
    return "Product Specs";
  }
  if (section === "entrypoint_guide") {
    return "Entrypoint Guide";
  }
  if (section === "skills") {
    return "Skills";
  }
  return section.replace(/^\d+_/, "").replaceAll("_", " ");
}
