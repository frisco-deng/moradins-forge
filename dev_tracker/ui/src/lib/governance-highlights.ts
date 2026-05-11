import type { ChangelogEntryV1, DocRecordV1, TrackerSnapshotVLatest } from "./contracts";

const CLOSED_DOC_STATUSES = new Set([
  "implemented",
  "implemented-review",
  "closed",
  "archived",
  "completed",
  "rejected",
  "cancelled",
  "superseded",
  "done",
]);

export interface HighlightDocGroup {
  key: string;
  docs: DocRecordV1[];
  primaryDoc: DocRecordV1 | null;
}

function normalizeDocStatus(status: string | undefined) {
  return (status ?? "").trim().toLowerCase();
}

function compareDocs(a: DocRecordV1, b: DocRecordV1) {
  const reviewCompare = (b.last_reviewed ?? "").localeCompare(a.last_reviewed ?? "");
  if (reviewCompare !== 0) {
    return reviewCompare;
  }
  return b.relative_path.localeCompare(a.relative_path);
}

function actionableDocsForPrefix(snapshot: TrackerSnapshotVLatest, prefix: string, includeIndexes = false) {
  return snapshot.docs
    .filter((doc) => doc.relative_path.startsWith(prefix))
    .filter((doc) => (includeIndexes ? true : !doc.relative_path.endsWith("/index.md")))
    .filter((doc) => !CLOSED_DOC_STATUSES.has(normalizeDocStatus(doc.status)))
    .sort(compareDocs);
}

function primaryDocForGroup(docs: DocRecordV1[]) {
  return (
    docs.find((doc) => doc.relative_path.split("/").at(-1)?.startsWith("plan_")) ??
    docs.find((doc) => doc.relative_path.endsWith("/index.md")) ??
    docs[0] ??
    null
  );
}

function workstreamKey(doc: DocRecordV1) {
  const haystack = `${doc.relative_path} ${doc.title}`.toLowerCase();
  const hupMatch = haystack.match(/hup\d{4}/);
  if (hupMatch) {
    return hupMatch[0];
  }
  const cycleMatch = haystack.match(/cycle[_-]\d{3}/);
  if (cycleMatch) {
    return cycleMatch[0];
  }
  return doc.relative_path.split("/").at(-1)?.replace(/\.md$/, "") ?? doc.id;
}

function latestGroup(groups: Map<string, DocRecordV1[]>) {
  const ranked = Array.from(groups.entries())
    .map(([key, docs]) => ({
      key,
      docs: docs.sort(compareDocs),
      primaryDoc: primaryDocForGroup(docs),
    }))
    .sort((a, b) => {
      if (b.docs.length !== a.docs.length) {
        return b.docs.length - a.docs.length;
      }
      if (a.primaryDoc && b.primaryDoc) {
        return compareDocs(a.primaryDoc, b.primaryDoc);
      }
      return 0;
    });
  return ranked[0] ?? null;
}

export function findActiveUpgradePackage(snapshot: TrackerSnapshotVLatest): HighlightDocGroup | null {
  const docs = actionableDocsForPrefix(snapshot, "docs/exec_plans/upgrades/active/");
  if (docs.length === 0) {
    return null;
  }
  const groups = new Map<string, DocRecordV1[]>();
  for (const doc of docs) {
    const key = workstreamKey(doc);
    const existing = groups.get(key) ?? [];
    existing.push(doc);
    groups.set(key, existing);
  }
  const match = latestGroup(groups);
  return match ? { key: match.key, docs: match.docs, primaryDoc: match.primaryDoc } : null;
}

export function findActivePlan(snapshot: TrackerSnapshotVLatest, prefix: string): HighlightDocGroup | null {
  const docs = actionableDocsForPrefix(snapshot, prefix);
  if (docs.length === 0) {
    return null;
  }
  return {
    key: prefix,
    docs,
    primaryDoc: primaryDocForGroup(docs),
  };
}

export function findLatestArchiveSet(snapshot: TrackerSnapshotVLatest, prefix: string): HighlightDocGroup | null {
  const docs = snapshot.docs.filter((doc) => doc.relative_path.startsWith(prefix)).sort(compareDocs);
  if (docs.length === 0) {
    return null;
  }

  const groups = new Map<string, DocRecordV1[]>();
  for (const doc of docs) {
    const pathParts = doc.relative_path.split("/");
    const key = pathParts.length > 3 ? (pathParts[3] ?? doc.relative_path) : doc.relative_path;
    const existing = groups.get(key) ?? [];
    existing.push(doc);
    groups.set(key, existing);
  }

  const match = latestGroup(groups);
  return match ? { key: match.key, docs: match.docs, primaryDoc: match.primaryDoc } : null;
}

export function findLatestAwaitingApproval(snapshot: TrackerSnapshotVLatest): ChangelogEntryV1 | null {
  return (
    [...snapshot.changelog.rows]
      .filter((entry) => entry.approval_status === "awaiting_human_review")
      .sort((a, b) => {
        const dateCompare = b.date.localeCompare(a.date);
        if (dateCompare !== 0) {
          return dateCompare;
        }
        return b.cycle_id.localeCompare(a.cycle_id);
      })[0] ?? null
  );
}

export function docStatusTone(status: string): "success" | "warning" | "error" | "info" {
  const normalized = normalizeDocStatus(status);
  if (["approved", "approved-plan", "active", "implemented-review"].includes(normalized)) {
    return "success";
  }
  if (["rejected", "blocked", "error"].includes(normalized)) {
    return "error";
  }
  if (["archived", "completed", "closed", "implemented", "done"].includes(normalized)) {
    return "info";
  }
  return "warning";
}

export function docTrackLabel(doc: DocRecordV1) {
  if (doc.relative_path.startsWith("docs/exec_plans/updates/active/")) {
    return "active update";
  }
  if (doc.relative_path.startsWith("docs/exec_plans/upgrades/active/")) {
    return "active upgrade";
  }
  if (doc.relative_path.startsWith("docs/exec_plans/commissioning/active/")) {
    return "active commissioning";
  }
  if (doc.relative_path.startsWith("docs/archive/integration/")) {
    return "archived provenance";
  }
  if (doc.relative_path.startsWith("docs/archive/")) {
    return "archive";
  }
  if (normalizeDocStatus(doc.status) === "archived") {
    return "archived";
  }
  return "";
}
