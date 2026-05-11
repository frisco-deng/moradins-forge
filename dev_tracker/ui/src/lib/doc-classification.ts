import type { DocClassificationV1, DocRecordV1, TrackerSummaryV1, TrackerSummaryV2 } from "./contracts";

export const DOC_CLASSIFICATION_LABELS: Record<DocClassificationV1, string> = {
  human_owned_context: "Human-Owned Context",
  system_managed: "System-Managed",
  generated: "Generated",
};

function isGeneratedDocLike(record: Pick<DocRecordV1, "relative_path" | "status" | "content">): boolean {
  const normalizedStatus = String(record.status ?? "").trim().toLowerCase();
  if (normalizedStatus.startsWith("generated")) {
    return true;
  }
  return /(^|\n)generated:\s*true\s*$/m.test(record.content);
}

export function classifyDocRecord(record: Pick<DocRecordV1, "relative_path" | "status" | "content">): DocClassificationV1 {
  const relativePath = String(record.relative_path ?? "").trim();
  if (
    relativePath === "docs/00_overview/engineer_entrypoint.md" ||
    (relativePath.startsWith("docs/engineer_entry/") && relativePath !== "docs/engineer_entry/index.md")
  ) {
    return "human_owned_context";
  }
  if (isGeneratedDocLike(record)) {
    return "generated";
  }
  return "system_managed";
}

export function labelForDocClassification(classification: DocClassificationV1): string {
  return DOC_CLASSIFICATION_LABELS[classification];
}

export function deriveSummaryV2FromDocs(
  docs: DocRecordV1[],
  fallbackSummary?: Partial<TrackerSummaryV1 | TrackerSummaryV2>,
): TrackerSummaryV2 {
  const docsInRepo = docs.filter(
    (record) => {
      const relativePath = String(record.relative_path ?? "").trim();
      return relativePath.startsWith("docs/") && !relativePath.includes("docs/archive/");
    },
  );

  if (docsInRepo.length === 0 && fallbackSummary) {
    const docsTotal = Number(fallbackSummary.docs_total ?? 0);
    const docsGenerated = Number(fallbackSummary.docs_generated ?? 0);
    const docsHumanOwnedContext =
      "docs_human_owned_context" in fallbackSummary
        ? Number(fallbackSummary.docs_human_owned_context ?? 0)
        : Number((fallbackSummary as TrackerSummaryV1).docs_non_generated ?? 0);
    const docsSystemManaged = Math.max(docsTotal - docsGenerated - docsHumanOwnedContext, 0);

    return {
      docs_total: docsTotal,
      docs_human_owned_context: docsHumanOwnedContext,
      docs_system_managed: docsSystemManaged,
      docs_generated: docsGenerated,
      phase_count: Number(fallbackSummary.phase_count ?? 0),
      stage_count: Number(fallbackSummary.stage_count ?? 0),
      stage_done_count: Number(fallbackSummary.stage_done_count ?? 0),
      loop_run_count: Number(fallbackSummary.loop_run_count ?? 0),
      open_gap_count: Number(fallbackSummary.open_gap_count ?? 0),
      changelog_entry_count: Number(fallbackSummary.changelog_entry_count ?? 0),
      awaiting_human_review_count: Number(fallbackSummary.awaiting_human_review_count ?? 0),
      implemented_feature_count: Number(fallbackSummary.implemented_feature_count ?? 0),
      active_guidance_count: Number(fallbackSummary.active_guidance_count ?? 0),
      estimated_cycles_remaining: Number(fallbackSummary.estimated_cycles_remaining ?? 0),
      estimated_loops_remaining: Number(fallbackSummary.estimated_loops_remaining ?? 0),
      archive_entry_count: Number(fallbackSummary.archive_entry_count ?? 0),
      markdown_changed_count: Number(fallbackSummary.markdown_changed_count ?? 0),
      compatibility_mode: String(fallbackSummary.compatibility_mode ?? ""),
    };
  }

  const classifiedDocs = docsInRepo.map((record) => record.classification ?? classifyDocRecord(record));
  const docsHumanOwnedContext = classifiedDocs.filter((classification) => classification === "human_owned_context").length;
  const docsGenerated = classifiedDocs.filter((classification) => classification === "generated").length;
  const docsSystemManaged = classifiedDocs.filter((classification) => classification === "system_managed").length;

  return {
    docs_total: docsInRepo.length,
    docs_human_owned_context: docsHumanOwnedContext,
    docs_system_managed: docsSystemManaged,
    docs_generated: docsGenerated,
    phase_count: Number(fallbackSummary?.phase_count ?? 0),
    stage_count: Number(fallbackSummary?.stage_count ?? 0),
    stage_done_count: Number(fallbackSummary?.stage_done_count ?? 0),
    loop_run_count: Number(fallbackSummary?.loop_run_count ?? 0),
    open_gap_count: Number(fallbackSummary?.open_gap_count ?? 0),
    changelog_entry_count: Number(fallbackSummary?.changelog_entry_count ?? 0),
    awaiting_human_review_count: Number(fallbackSummary?.awaiting_human_review_count ?? 0),
    implemented_feature_count: Number(fallbackSummary?.implemented_feature_count ?? 0),
    active_guidance_count: Number(fallbackSummary?.active_guidance_count ?? 0),
    estimated_cycles_remaining: Number(fallbackSummary?.estimated_cycles_remaining ?? 0),
    estimated_loops_remaining: Number(fallbackSummary?.estimated_loops_remaining ?? 0),
    archive_entry_count: Number(fallbackSummary?.archive_entry_count ?? 0),
    markdown_changed_count: Number(fallbackSummary?.markdown_changed_count ?? 0),
    compatibility_mode: String(fallbackSummary?.compatibility_mode ?? ""),
  };
}
