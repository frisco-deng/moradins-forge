import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  buildHarnessHelp,
  buildProjectOverview,
  buildPolicySummaries,
  buildServiceInventory,
  collectImplementedSurfaces,
  collectGitState,
  countCheckboxes,
  countWords,
  docIdFromPath,
  evaluateDocumentationReviewStatus,
  extractHeadings,
  getSectionFromRelativePath,
  normalizePath,
  parseArchiveRegister,
  parseCapabilityGaps,
  parseChangelog,
  parseCurrentFeatures,
  parseCurrentGuidance,
  parseFrontMatter,
  parseHumanGateStats,
  parseImplementationPhases,
  parseLoopProcesses,
  parseLoopState,
  parseServiceCatalog,
  parseTopology,
  walkMarkdownFiles,
} from "./lib/snapshot-lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const docsRoot = path.join(repoRoot, "docs");
const harnessRoot = path.join(repoRoot, "Harness");
const templateRoot = path.join(repoRoot, ".harness_template");
const skillsRoot = path.join(repoRoot, "skills");
const generatedRoot = path.join(uiRoot, "public", "generated");
const COMPATIBILITY_MODE = "canonical_only";
const NON_ACTIONABLE_DOC_STATUSES = new Set([
  "implemented",
  "closed",
  "archived",
  "completed",
  "rejected",
  "cancelled",
  "superseded",
  "done",
]);

function isGeneratedDocRecord(record) {
  const normalizedStatus = String(record.status ?? "").trim().toLowerCase();
  if (normalizedStatus.startsWith("generated")) {
    return true;
  }
  return /(^|\n)generated:\s*true\s*$/m.test(record.content);
}

function classifyDocRecord(record) {
  const relativePath = String(record.relative_path ?? "").trim();
  if (
    relativePath === "docs/00_overview/engineer_entrypoint.md" ||
    (relativePath.startsWith("docs/engineer_entry/") && relativePath !== "docs/engineer_entry/index.md")
  ) {
    return "human_owned_context";
  }
  if (isGeneratedDocRecord(record)) {
    return "generated";
  }
  return "system_managed";
}

async function main() {
  await fs.mkdir(generatedRoot, { recursive: true });

  const docsFiles = await walkMarkdownFiles(docsRoot);
  const harnessFiles = await walkMarkdownFiles(harnessRoot);
  const skillsFiles = await walkMarkdownFiles(skillsRoot);
  const extraFiles = [
    path.join(repoRoot, "AGENTS.md"),
    path.join(repoRoot, "HUMAN_REVIEW.md"),
    path.join(repoRoot, "README.md"),
    ...skillsFiles,
  ];

  const records = [];
  for (const fullPath of [...docsFiles, ...harnessFiles, ...extraFiles]) {
    const relativePath = normalizePath(path.relative(repoRoot, fullPath));
    const raw = await fs.readFile(fullPath, "utf8");
    const { frontMatter, body } = parseFrontMatter(raw);
    const headings = extractHeadings(body);
    const checklist = countCheckboxes(body);
    const section = getSectionFromRelativePath(relativePath);
    const fallbackTitle = headings[0]?.text || path.basename(relativePath, ".md");

    records.push({
      version: "DocRecordV1",
      id: docIdFromPath(relativePath),
      relative_path: relativePath,
      section,
      title: String(frontMatter.title ?? fallbackTitle),
      status: String(frontMatter.status ?? ""),
      owner: String(frontMatter.owner ?? ""),
      last_reviewed: String(frontMatter.last_reviewed ?? ""),
      related_docs: Array.isArray(frontMatter.related_docs) ? frontMatter.related_docs : [],
      source_refs: Array.isArray(frontMatter.source_refs) ? frontMatter.source_refs : [],
      heading_count: headings.length,
      headings,
      checklist_total: checklist.total,
      checklist_done: checklist.done,
      word_count: countWords(body),
      has_frontmatter: Object.keys(frontMatter).length > 0,
      classification: "system_managed",
      content: raw,
    });
  }

  records.sort((a, b) => a.relative_path.localeCompare(b.relative_path));
  for (const record of records) {
    record.classification = classifyDocRecord(record);
  }

  const implementationPhasesDoc = getOptionalRecordByPaths(records, ["docs/00_overview/implementation_phases.md"]);
  const loopStateDoc = getRecordByPath(records, "Harness/artifacts/control/loop_state.md");
  const capabilityDoc = getRecordByPath(records, "Harness/artifacts/control/capability_gap_register.md");
  const changelogDoc = getRecordByPath(records, "Harness/artifacts/control/changelog.md");
  const currentFeaturesDoc = getRecordByPath(records, "Harness/artifacts/control/current_features.md");
  const currentGuidanceDoc = getRecordByPath(records, "Harness/artifacts/control/current_guidance.md");
  const loopProcessesDoc = getRecordByPath(records, "Harness/artifacts/control/loop_processes.md");
  const humanGateStatsDoc = getRecordByPath(records, "Harness/artifacts/control/human_gate_stats.md");
  const archiveRegisterDoc = getRecordByPath(records, "Harness/artifacts/control/archive_register.md");
  const topologyDoc = getOptionalRecordByPaths(records, ["docs/03_architecture/container_topology.md"]);
  const boundariesDoc = getOptionalRecordByPaths(records, ["docs/03_architecture/service_boundaries.md"]);
  const serviceCatalogDoc = getOptionalRecordByPaths(records, ["docs/00_overview/service_catalog.md"]);
  const architectureDoc = getOptionalRecordByPaths(records, ["docs/00_overview/architecture.md"]);
  const engineerEntrypointDoc = getOptionalRecordByPaths(records, ["docs/00_overview/engineer_entrypoint.md"]);
  const codexRunLoopDoc = getRecordByPath(records, "docs/11_ops/codex_run_loop.md");
  const updateRoutineDoc = getOptionalRecordByPaths(records, ["docs/entrypoint_guide/update_cycle_routine.md"]);
  const upgradeRoutineDoc = getOptionalRecordByPaths(records, ["docs/entrypoint_guide/upgrade_cycle_routine.md"]);
  const toolingPipelineDoc = getRecordByPath(records, "docs/11_ops/tooling_pipeline.md");
  const changeTrackingDoc = getRecordByPath(records, "docs/11_ops/change_tracking_system.md");
  const gitWorkflowDoc = getOptionalRecordByPaths(records, ["docs/11_ops/git_workflow_gitlab.md"]);
  const docStyleDoc = getOptionalRecordByPaths(records, ["docs/13_style_guides/doc_style.md"]);
  const capabilityUpdatesDoc = getRecordByPath(records, "docs/exec_plans/updates/active/index.md");
  const capabilityUpgradesDoc = getRecordByPath(records, "docs/exec_plans/upgrades/active/index.md");
  const capabilityToolingDoc = getRecordByPath(records, "docs/exec_plans/tooling/active/index.md");
  const capabilityGovernanceDoc = getRecordByPath(records, "docs/exec_plans/implementation/active/index.md");
  const capabilityIntegrationsDoc = getRecordByPath(records, "docs/exec_plans/tooling/active/index.md");
  const capabilitySuggestionsDoc = getRecordByPath(records, "docs/exec_plans/implementation/active/index.md");
  const agentsDoc = getRecordByPath(records, "AGENTS.md");
  const repoSkillRegistryDoc = getRecordByPaths(records, [
    "Harness/artifacts/reports/repo_skill_registry.md",
  ]);
  const documentationReviewStatusDoc = getOptionalRecordByPaths(records, ["Harness/artifacts/control/documentation_review_status.md"]);
  const compatibilityWindowStatusDoc = getOptionalRecordByPaths(records, ["Harness/artifacts/control/compatibility_window_status.md"]);
  const readmeDoc = getRecordByPath(records, "README.md");
  const humanReviewDoc = getOptionalRecordByPaths(records, ["HUMAN_REVIEW.md"]);

  const phases = parseImplementationPhases(implementationPhasesDoc?.content ?? "");
  const loopState = parseLoopState(loopStateDoc.content);
  const capabilityGaps = parseCapabilityGaps(capabilityDoc.content);
  const changelog = parseChangelog(changelogDoc.content);
  const currentFeatures = parseCurrentFeatures(currentFeaturesDoc.content);
  const currentGuidance = parseCurrentGuidance(currentGuidanceDoc.content);
  const loopProcesses = parseLoopProcesses(loopProcessesDoc.content);
  const humanGateStats = parseHumanGateStats(humanGateStatsDoc.content);
  const archiveRegister = parseArchiveRegister(archiveRegisterDoc.content);
  const topology = parseTopology(topologyDoc?.content ?? "", boundariesDoc?.content ?? "");
  const serviceCatalog = parseServiceCatalog(serviceCatalogDoc?.content ?? "");
  const implementedSurfaces = await collectImplementedSurfaces(repoRoot);
  const serviceInventory = buildServiceInventory(serviceCatalog, implementedSurfaces);
  const projectOverview = buildProjectOverview({
    readmeMarkdown: readmeDoc.content,
    architectureMarkdown: architectureDoc?.content ?? "",
    engineerEntrypointMarkdown: engineerEntrypointDoc?.content ?? "",
    phases,
  });
  const harnessHelp = buildHarnessHelp({
    codexRunLoopMarkdown: codexRunLoopDoc.content,
    updateRoutineMarkdown: updateRoutineDoc?.content ?? "",
    upgradeRoutineMarkdown: upgradeRoutineDoc?.content ?? "",
    toolingPipelineMarkdown: toolingPipelineDoc.content,
    changeTrackingMarkdown: changeTrackingDoc.content,
    agentsMarkdown: agentsDoc.content,
    gitWorkflowMarkdown: gitWorkflowDoc?.content ?? "",
    docStyleMarkdown: docStyleDoc?.content ?? "",
    readmeMarkdown: readmeDoc.content,
    capabilityUpdatesMarkdown: capabilityUpdatesDoc.content,
    capabilityUpgradesMarkdown: capabilityUpgradesDoc.content,
    capabilityToolingMarkdown: capabilityToolingDoc.content,
    capabilityGovernanceMarkdown: capabilityGovernanceDoc.content,
    capabilityIntegrationsMarkdown: capabilityIntegrationsDoc.content,
    capabilitySuggestionsMarkdown: capabilitySuggestionsDoc.content,
    repoSkillRegistryMarkdown: repoSkillRegistryDoc.content,
    compatibilityWindowStatusMarkdown: compatibilityWindowStatusDoc?.content ?? "",
  });
  const gitState = collectGitState(repoRoot);
  const policies = buildPolicySummaries(records);
  const qaSignals = collectQaSignals(documentationReviewStatusDoc?.content ?? "");
  const reviewQueue = buildReviewQueue({ records, changelog, humanGateStats });
  const routeContextCoverage = await buildRouteContextCoverage({ uiRoot });
  const humanReviewSummary = buildHumanReviewSummary({
    reviewQueue,
    changelog,
    currentFeatures,
    capabilityGaps,
    records,
    humanReviewMarkdown: humanReviewDoc?.content ?? "",
  });

  const docsInRepo = records.filter(
    (record) => record.relative_path.startsWith("docs/") && !record.relative_path.includes("docs/archive/"),
  );
  const docsHumanOwnedContext = docsInRepo.filter((record) => record.classification === "human_owned_context");
  const docsGenerated = docsInRepo.filter((record) => record.classification === "generated");
  const docsSystemManaged = docsInRepo.filter((record) => record.classification === "system_managed");

  const snapshot = {
    version: "TrackerSnapshotV6",
    generated_at: new Date().toISOString(),
    repo_root: repoRoot,
    summary: {
      docs_total: docsInRepo.length,
      docs_human_owned_context: docsHumanOwnedContext.length,
      docs_system_managed: docsSystemManaged.length,
      docs_generated: docsGenerated.length,
      phase_count: phases.phase_count,
      stage_count: phases.stage_count,
      stage_done_count: phases.stage_done_count,
      loop_run_count: loopState.run_count,
      open_gap_count: capabilityGaps.open_count,
      changelog_entry_count: changelog.entry_count,
      awaiting_human_review_count: changelog.awaiting_human_review_count,
      implemented_feature_count: currentFeatures.implemented_count,
      active_guidance_count: currentGuidance.active_count,
      estimated_cycles_remaining: humanGateStats.latest_estimated_cycles_remaining,
      estimated_loops_remaining: humanGateStats.latest_estimated_loops_remaining,
      archive_entry_count: archiveRegister.row_count,
      markdown_changed_count: gitState.markdown_changed_count,
      compatibility_mode: COMPATIBILITY_MODE,
    },
    phases: {
      version: "PhaseBoardV1",
      ...phases,
    },
    loop_state: {
      version: "LoopStateV1",
      ...loopState,
    },
    capability_gaps: {
      version: "CapabilityGapV1",
      ...capabilityGaps,
    },
    changelog: {
      version: "ChangelogV1",
      ...changelog,
    },
    current_features: {
      version: "CurrentFeaturesV1",
      ...currentFeatures,
    },
    current_guidance: {
      version: "CurrentGuidanceV1",
      ...currentGuidance,
    },
    loop_processes: {
      version: "LoopProcessesV1",
      ...loopProcesses,
    },
    human_gate_stats: {
      version: "HumanGateStatsV1",
      ...humanGateStats,
    },
    archive_register: {
      version: "ArchiveRegisterV1",
      ...archiveRegister,
    },
    policies: {
      version: "PolicyDomainSummaryV1",
      domains: policies,
    },
    topology: {
      version: "TopologySnapshotV1",
      ...topology,
    },
    project_overview: {
      version: "ProjectOverviewV1",
      ...projectOverview,
    },
    service_inventory: {
      version: "ServiceInventoryV1",
      ...serviceInventory,
    },
    harness_help: {
      version: "HarnessHelpV1",
      ...harnessHelp,
    },
    review_queue: reviewQueue,
    route_context_coverage: routeContextCoverage,
    human_review_summary: humanReviewSummary,
    qa_signals: qaSignals,
    git: gitState,
    docs: records,
  };
  const contextPack = buildContextPack({
    generatedAt: snapshot.generated_at,
    serviceInventory: snapshot.service_inventory,
    routeContextCoverage,
    currentGuidance: snapshot.current_guidance,
    records,
  });
  const templateStudio = await buildTemplateStudio({
    generatedAt: snapshot.generated_at,
    repoRoot,
    templateRoot,
  });

  await Promise.all([
    fs.writeFile(path.join(generatedRoot, "tracker_snapshot_v1.json"), `${JSON.stringify(snapshot, null, 2)}\n`, "utf8"),
    fs.writeFile(path.join(generatedRoot, "git_state_v1.json"), `${JSON.stringify(gitState, null, 2)}\n`, "utf8"),
    fs.writeFile(path.join(generatedRoot, "qa_signals_v1.json"), `${JSON.stringify(qaSignals, null, 2)}\n`, "utf8"),
    fs.writeFile(path.join(generatedRoot, "context_pack_v1.json"), `${JSON.stringify(contextPack, null, 2)}\n`, "utf8"),
    fs.writeFile(path.join(generatedRoot, "template_studio_v1.json"), `${JSON.stringify(templateStudio, null, 2)}\n`, "utf8"),
    fs.writeFile(
      path.join(generatedRoot, "runtime_status.json"),
      `${JSON.stringify(
        {
          generated_at: snapshot.generated_at,
          docs_indexed: docsInRepo.length,
          markdown_changed_count: gitState.markdown_changed_count,
          branch: gitState.branch,
          engineer_entry_guard_status: qaSignals.engineer_entry_guard.status,
          branch_hygiene_status: qaSignals.branch_hygiene.status,
          documentation_review_status: qaSignals.documentation_review?.status ?? "fail",
          compatibility_window_slot: harnessHelp.compatibility_window?.current_slot ?? "",
        },
        null,
        2,
      )}\n`,
      "utf8",
    ),
  ]);

  process.stdout.write(
    `[sync-docs] generated tracker_snapshot_v1.json with ${docsInRepo.length} docs (${docsHumanOwnedContext.length} human-owned context, ${docsSystemManaged.length} system-managed, ${docsGenerated.length} generated)\n`,
  );
}

function buildContextPack({ generatedAt, serviceInventory, routeContextCoverage, currentGuidance, records }) {
  const keyAnchorPaths = [
    "AGENTS.md",
    "docs/00_overview/engineer_entrypoint.md",
    "docs/11_ops/project_builder_runbook.md",
    "docs/design_docs/project_builder_control_api.md",
    "docs/product_specs/project_builder_ui.md",
    "docs/03_architecture/container_topology.md",
  ];
  const keyDocAnchors = keyAnchorPaths
    .map((relativePath) => records.find((record) => record.relative_path === relativePath))
    .filter(Boolean)
    .map((record) => ({
      title: record.title,
      path: record.relative_path,
      headings: record.headings.slice(0, 3).map((heading) => ({
        level: heading.level,
        text: heading.text,
      })),
    }));

  return {
    version: "ContextPackV1",
    generated_at: generatedAt,
    template_manifest: {
      harness_seed_version: "mh004-seed-v1",
      seed_groups: [
        {
          group_id: "foundations",
          paths: ["AGENTS.md", "README.md", "docs/00_overview", "docs/03_architecture"],
        },
        {
          group_id: "governance",
          paths: ["docs/11_ops", "docs/15_checklists", "Harness/artifacts/control"],
        },
        {
          group_id: "builder",
          paths: ["dev_tracker/ui/src", "dev_tracker/ui/scripts", "tests/scripts", "tests/contracts"],
        },
      ],
    },
    service_inventory_summary: {
      planned_count: serviceInventory.planned_count,
      implemented_count: serviceInventory.implemented_count,
      planned_only_count: serviceInventory.planned_only_count,
      top_rows: serviceInventory.rows.slice(0, 12).map((row) => ({
        service: row.service,
        domain: row.domain,
        phase_target: row.phase_target,
        status: row.status,
      })),
    },
    route_inventory_summary: {
      router_route_count: routeContextCoverage.router_route_count,
      context_route_count: routeContextCoverage.context_route_count,
      coverage_percent: routeContextCoverage.coverage_percent,
      key_routes: routeContextCoverage.rows
        .filter((row) => row.router_present)
        .slice(0, 16)
        .map((row) => ({
          route: row.route,
          status: row.status,
        })),
    },
    active_guidance: currentGuidance.rows.slice(0, 12).map((row) => ({
      guidance_id: row.guidance_id,
      rule: row.rule,
      operator_action: row.operator_action,
      status: row.status,
    })),
    key_doc_anchors: keyDocAnchors,
  };
}

async function buildTemplateStudio({ generatedAt, repoRoot, templateRoot }) {
  const managerManifest = await parseFlatYamlFile(path.join(repoRoot, "Harness", "manifest.yaml"));
  const templateManifestPath = path.join(templateRoot, "Harness", "manifest.yaml");
  const templateRootAvailable = await fileExists(templateManifestPath);
  if (!templateRootAvailable) {
    const payloadManifest = await parseFlatYamlFile(path.join(repoRoot, "Harness", "moradin_payload", "manifest.yaml"));
    const validation = await readTemplateValidation(path.join(repoRoot, "Harness", "generated", "validation_results.json"));
    const dryRun = await readDryRunSummary(path.join(repoRoot, "public_audit", "dry_run_smoke_test_report.md"));

    return {
      version: "TemplateStudioV1",
      generated_at: generatedAt,
      manager_manifest: managerManifest,
      template_manifest: payloadManifest,
      required_sections: [],
      sections: [],
      inventory: {
        total_files: 0,
        docs_markdown_count: 0,
        harness_markdown_count: 0,
        placeholder_count: 0,
      },
      validation,
      dry_run: dryRun,
    };
  }

  const templateManifest = await parseFlatYamlFile(path.join(templateRoot, "Harness", "manifest.yaml"));
  const templateDocsRoot = path.join(templateRoot, "docs");
  const templateHarnessRoot = path.join(templateRoot, "Harness");
  const [templateDocFiles, templateHarnessMarkdownFiles, templateAllFiles, sectionEntries] = await Promise.all([
    walkMarkdownFiles(templateDocsRoot),
    walkMarkdownFiles(templateHarnessRoot),
    walkAllFiles(templateRoot),
    fs.readdir(templateDocsRoot, { withFileTypes: true }),
  ]);

  const requiredSections = sectionEntries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right));

  const sections = [];
  for (const section of requiredSections) {
    const indexPath = path.join(templateDocsRoot, section, "index.md");
    let raw = "";
    try {
      raw = await fs.readFile(indexPath, "utf8");
    } catch {
      continue;
    }
    const { frontMatter } = parseFrontMatter(raw);
    const questions = Array.isArray(frontMatter.questions) ? frontMatter.questions : [];
    const title = String(frontMatter.title ?? `${section} index`).trim();
    const status = String(frontMatter.status ?? "").trim();
    sections.push({
      section,
      relative_path: normalizePath(path.relative(repoRoot, indexPath)),
      title,
      status,
      owner: String(frontMatter.owner ?? "").trim(),
      placeholder: status.toLowerCase() === "placeholder",
      question_count: questions.length,
    });
  }

  const validation = await readTemplateValidation(path.join(repoRoot, "Harness", "generated", "validation_results.json"));
  const dryRun = await readDryRunSummary(path.join(repoRoot, "public_audit", "dry_run_smoke_test_report.md"));

  return {
    version: "TemplateStudioV1",
    generated_at: generatedAt,
    manager_manifest: managerManifest,
    template_manifest: templateManifest,
    required_sections: requiredSections,
    sections,
    inventory: {
      total_files: templateAllFiles.length,
      docs_markdown_count: templateDocFiles.length,
      harness_markdown_count: templateHarnessMarkdownFiles.length,
      placeholder_count: sections.filter((section) => section.placeholder).length,
    },
    validation,
    dry_run: dryRun,
  };
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function parseFlatYamlFile(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  const parsed = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const separator = trimmed.indexOf(":");
    if (separator <= 0) {
      continue;
    }
    const key = trimmed.slice(0, separator).trim();
    const value = trimmed.slice(separator + 1).trim().replace(/^['"]|['"]$/g, "");
    parsed[key] = value;
  }
  return parsed;
}

async function walkAllFiles(root) {
  const results = [];
  const entries = await fs.readdir(root, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      const nested = await walkAllFiles(fullPath);
      results.push(...nested);
      continue;
    }
    if (entry.isFile()) {
      results.push(fullPath);
    }
  }
  return results;
}

async function readTemplateValidation(filePath) {
  try {
    const payload = JSON.parse(await fs.readFile(filePath, "utf8"));
    const managerMessages = Array.isArray(payload.manager?.messages) ? payload.manager.messages : [];
    const templateMessages = Array.isArray(payload.template?.messages) ? payload.template.messages : [];
    return {
      available: true,
      overall_ok: payload.overall_ok === true,
      manager_ok: payload.manager?.ok === true,
      template_ok: payload.template?.ok === true,
      messages: [...managerMessages, ...templateMessages].slice(0, 10),
    };
  } catch {
    return {
      available: false,
      overall_ok: false,
      manager_ok: false,
      template_ok: false,
      messages: [],
    };
  }
}

async function readDryRunSummary(filePath) {
  try {
    const markdown = await fs.readFile(filePath, "utf8");
    const blankTarget = markdown.match(/- Blank target: `([^`]+)`/)?.[1] ?? "";
    const existingTarget = markdown.match(/- Existing fixture target: `([^`]+)`/)?.[1] ?? "";
    const blankOk = markdown.includes("- Blank deployment: pass");
    const existingOk = markdown.includes("- Existing fixture overlay: pass");
    const messages = markdown
      .split(/\r?\n/)
      .filter((line) => line.startsWith("- "))
      .slice(4, 12)
      .map((line) => line.replace(/^- /, "").trim());
    return {
      available: true,
      blank_ok: blankOk,
      existing_ok: existingOk,
      blank_target: blankTarget,
      existing_target: existingTarget,
      messages,
    };
  } catch {
    return {
      available: false,
      blank_ok: false,
      existing_ok: false,
      blank_target: "",
      existing_target: "",
      messages: [],
    };
  }
}

function getRecordByPath(records, relativePath) {
  const match = records.find((record) => record.relative_path === relativePath);
  if (!match) {
    throw new Error(`Required source file missing in snapshot generation: ${relativePath}`);
  }
  return match;
}

function getRecordByPaths(records, relativePaths) {
  for (const relativePath of relativePaths) {
    const match = records.find((record) => record.relative_path === relativePath);
    if (match) {
      return match;
    }
  }
  throw new Error(`Required source file missing in snapshot generation. tried: ${relativePaths.join(", ")}`);
}

function getOptionalRecordByPaths(records, relativePaths) {
  for (const relativePath of relativePaths) {
    const match = records.find((record) => record.relative_path === relativePath);
    if (match) {
      return match;
    }
  }
  return null;
}

function collectQaSignals(documentationReviewStatusMarkdown) {
  const engineerEntryGuard = runCheck(
    process.execPath,
    [path.join(uiRoot, "scripts", "check-engineer-entry-frontmatter.mjs")],
    {
      cwd: uiRoot,
      parseJson: false,
    },
  );

  const branchHygiene = runCheck(
    "uv",
    ["run", "python", path.join(repoRoot, "scripts", "check_branch_hygiene.py"), "--json"],
    {
      cwd: repoRoot,
      parseJson: true,
    },
  );
  const documentationReview = evaluateDocumentationReviewStatus(documentationReviewStatusMarkdown);

  return {
    version: "QaSignalsV1",
    generated_at: new Date().toISOString(),
    engineer_entry_guard: engineerEntryGuard,
    branch_hygiene: branchHygiene,
    documentation_review: documentationReview,
  };
}

function isActionableDocStatus(status) {
  const normalized = String(status ?? "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return !NON_ACTIONABLE_DOC_STATUSES.has(normalized);
}

function buildReviewQueue({ records, changelog, humanGateStats }) {
  const queueSpecs = [
    {
      queue_id: "updates",
      label: "Updates",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/updates/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "upgrades",
      label: "Upgrades",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/upgrades/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "tooling",
      label: "Tooling",
      include: (relativePath) =>
        relativePath.startsWith("docs/exec_plans/tooling/active/") && !relativePath.endsWith("/index.md"),
    },
    {
      queue_id: "suggestions",
      label: "Suggestions",
      include: (relativePath) => {
        if (!relativePath.startsWith("docs/exec_plans/implementation/active/")) {
          return false;
        }
        if (relativePath.endsWith("/index.md")) {
          return false;
        }
        return path.basename(relativePath).startsWith("sug_");
      },
    },
    {
      queue_id: "governance",
      label: "Governance",
      include: (relativePath) => {
        if (!relativePath.startsWith("docs/exec_plans/implementation/active/")) {
          return false;
        }
        if (relativePath.endsWith("/index.md")) {
          return false;
        }
        return !path.basename(relativePath).startsWith("sug_");
      },
    },
  ];

  const queues = queueSpecs.map((spec) => {
    const rows = records
      .filter((doc) => spec.include(doc.relative_path))
      .map((doc) => ({
        doc_id: doc.id,
        relative_path: doc.relative_path,
        title: doc.title,
        status: doc.status,
        owner: doc.owner,
        actionable: isActionableDocStatus(doc.status),
      }));

    const actionableDocs = rows.filter((row) => row.actionable).length;
    return {
      queue_id: spec.queue_id,
      label: spec.label,
      active_docs: rows.length,
      actionable_docs: actionableDocs,
      implemented_docs: rows.length - actionableDocs,
      rows,
    };
  });

  const queueById = Object.fromEntries(queues.map((queue) => [queue.queue_id, queue]));
  const pendingApprovals = changelog.awaiting_human_review_count;
  const pendingTotal = queues.reduce((sum, queue) => sum + queue.actionable_docs, 0);

  const reconciliationIssues = [];
  const latestGate = humanGateStats.latest ?? null;
  if (latestGate && latestGate.pending_approvals !== pendingApprovals) {
    reconciliationIssues.push(
      `human_gate_stats.latest.pending_approvals (${latestGate.pending_approvals}) != changelog.awaiting_human_review_count (${pendingApprovals})`,
    );
  }

  const actionableUpgrades = queueById.upgrades?.actionable_docs ?? 0;
  if (latestGate && latestGate.open_harness_upgrades !== actionableUpgrades) {
    reconciliationIssues.push(
      `human_gate_stats.latest.open_harness_upgrades (${latestGate.open_harness_upgrades}) != actionable upgrades (${actionableUpgrades})`,
    );
  }

  for (const queue of queues) {
    if (queue.active_docs > 0 && queue.actionable_docs === 0) {
      reconciliationIssues.push(
        `${queue.label} active queue contains only non-actionable docs; move implemented/closed docs out of active index.`,
      );
    }
  }

  return {
    version: "ReviewQueueV1",
    generated_at: new Date().toISOString(),
    pending_approvals: pendingApprovals,
    pending_total: pendingTotal,
    queues,
    zero_state: {
      updates: (queueById.updates?.actionable_docs ?? 0) === 0,
      upgrades: (queueById.upgrades?.actionable_docs ?? 0) === 0,
      tooling: (queueById.tooling?.actionable_docs ?? 0) === 0,
      suggestions: (queueById.suggestions?.actionable_docs ?? 0) === 0,
    },
    reconciliation: {
      status: reconciliationIssues.length === 0 ? "pass" : "warn",
      issues: reconciliationIssues,
    },
  };
}

async function buildRouteContextCoverage({ uiRoot }) {
  const appPath = path.join(uiRoot, "src", "App.tsx");
  const routeContextPath = path.join(uiRoot, "src", "lib", "route-context.ts");

  const [appSource, contextSource] = await Promise.all([
    fs.readFile(appPath, "utf8"),
    fs.readFile(routeContextPath, "utf8"),
  ]);

  const routerRoutes = new Set();
  for (const match of appSource.matchAll(/<Route\s+path="([^"]+)"/g)) {
    const route = String(match[1] ?? "").trim();
    if (!route || route === "*") {
      continue;
    }
    routerRoutes.add(route);
  }

  const contextRoutes = new Set();
  for (const match of contextSource.matchAll(/route:\s*"([^"]+)"/g)) {
    const route = String(match[1] ?? "").trim();
    if (!route) {
      continue;
    }
    contextRoutes.add(route);
  }

  const missingInContext = [...routerRoutes].filter((route) => !contextRoutes.has(route)).sort((a, b) => a.localeCompare(b));
  const extraInContext = [...contextRoutes].filter((route) => !routerRoutes.has(route)).sort((a, b) => a.localeCompare(b));

  const unionRoutes = [...new Set([...routerRoutes, ...contextRoutes])].sort((a, b) => a.localeCompare(b));
  const rows = unionRoutes.map((route) => {
    const routerPresent = routerRoutes.has(route);
    const contextPresent = contextRoutes.has(route);
    return {
      route,
      router_present: routerPresent,
      context_present: contextPresent,
      status: routerPresent && contextPresent ? "covered" : routerPresent ? "missing_context" : "orphan_context",
    };
  });

  const covered = [...routerRoutes].filter((route) => contextRoutes.has(route)).length;
  const coveragePercent = routerRoutes.size === 0 ? 100 : Number(((covered / routerRoutes.size) * 100).toFixed(1));

  return {
    version: "RouteContextCoverageV1",
    router_route_count: routerRoutes.size,
    context_route_count: contextRoutes.size,
    coverage_percent: coveragePercent,
    missing_in_context: missingInContext,
    extra_in_context: extraInContext,
    rows,
  };
}

function isStaleReviewDate(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return true;
  }
  const timestamp = Date.parse(trimmed);
  if (Number.isNaN(timestamp)) {
    return true;
  }
  const ageMs = Date.now() - timestamp;
  const staleMs = 180 * 24 * 60 * 60 * 1000;
  return ageMs > staleMs;
}

function severityFromCount(value) {
  if (value <= 0) {
    return "none";
  }
  if (value >= 3) {
    return "high";
  }
  if (value >= 2) {
    return "medium";
  }
  return "low";
}

function buildHumanReviewSummary({
  reviewQueue,
  changelog,
  currentFeatures,
  capabilityGaps,
  records,
  humanReviewMarkdown,
}) {
  const queueById = Object.fromEntries(reviewQueue.queues.map((queue) => [queue.queue_id, queue]));
  const docsNeedingMetadata = records.filter((doc) => {
    if (!(doc.relative_path.startsWith("docs/") || doc.relative_path === "HUMAN_REVIEW.md")) {
      return false;
    }
    if (!doc.has_frontmatter) {
      return true;
    }
    if (!doc.owner || !doc.status) {
      return true;
    }
    return isStaleReviewDate(doc.last_reviewed);
  }).length;

  const projectReview = [
    {
      review_id: "project-approvals",
      label: "Pending approvals",
      pending_count: changelog.awaiting_human_review_count,
      severity: severityFromCount(changelog.awaiting_human_review_count),
      route: "/exchange",
      source: "changelog.awaiting_human_review_count",
    },
    {
      review_id: "project-features",
      label: "Pending features",
      pending_count: currentFeatures.pending_count,
      severity: severityFromCount(currentFeatures.pending_count),
      route: "/features",
      source: "current_features.pending_count",
    },
    {
      review_id: "project-capability-gaps",
      label: "Open capability gaps",
      pending_count: capabilityGaps.open_count,
      severity: severityFromCount(capabilityGaps.open_count),
      route: "/cycles",
      source: "capability_gaps.open_count",
    },
    {
      review_id: "project-doc-metadata",
      label: "Docs needing metadata/review",
      pending_count: docsNeedingMetadata,
      severity: severityFromCount(docsNeedingMetadata),
      route: "/policies",
      source: "docs frontmatter + owner/status + stale review checks",
    },
  ];

  const harnessReview = [
    {
      review_id: "harness-updates",
      label: "Pending updates",
      pending_count: queueById.updates?.actionable_docs ?? 0,
      severity: severityFromCount(queueById.updates?.actionable_docs ?? 0),
      route: "/exchange",
      source: "review_queue.updates.actionable_docs",
    },
    {
      review_id: "harness-upgrades",
      label: "Pending upgrades",
      pending_count: queueById.upgrades?.actionable_docs ?? 0,
      severity: severityFromCount(queueById.upgrades?.actionable_docs ?? 0),
      route: "/exchange",
      source: "review_queue.upgrades.actionable_docs",
    },
    {
      review_id: "harness-tooling",
      label: "Pending tooling items",
      pending_count: queueById.tooling?.actionable_docs ?? 0,
      severity: severityFromCount(queueById.tooling?.actionable_docs ?? 0),
      route: "/exchange",
      source: "review_queue.tooling.actionable_docs",
    },
    {
      review_id: "harness-suggestions",
      label: "Pending suggestions",
      pending_count: queueById.suggestions?.actionable_docs ?? 0,
      severity: severityFromCount(queueById.suggestions?.actionable_docs ?? 0),
      route: "/exchange",
      source: "review_queue.suggestions.actionable_docs",
    },
  ];

  const pendingTotal =
    projectReview.reduce((sum, row) => sum + row.pending_count, 0) + harnessReview.reduce((sum, row) => sum + row.pending_count, 0);

  const notes = [];
  if (!String(humanReviewMarkdown ?? "").trim()) {
    notes.push("HUMAN_REVIEW.md is missing or empty.");
  }
  if (reviewQueue.reconciliation.status !== "pass") {
    notes.push(...reviewQueue.reconciliation.issues);
  }

  return {
    version: "HumanReviewSummaryV1",
    generated_at: new Date().toISOString(),
    next_action: changelog.awaiting_human_review_count > 0 ? "pause" : pendingTotal > 0 ? "pause" : "continue",
    pending_total: pendingTotal,
    project_review: projectReview,
    harness_review: harnessReview,
    notes,
  };
}

function runCheck(command, args, { cwd, parseJson }) {
  try {
    const raw = execFileSync(command, args, {
      cwd,
      encoding: "utf8",
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    if (parseJson) {
      const parsed = JSON.parse(raw);
      return {
        status: parsed.status === "pass" ? "pass" : "fail",
        detail: parsed,
      };
    }
    return {
      status: "pass",
      detail: raw,
    };
  } catch (error) {
    const raw = String(error?.stderr || error?.stdout || error?.message || error).trim();
    if (parseJson) {
      try {
        const parsed = JSON.parse(raw);
        return {
          status: parsed.status === "pass" ? "pass" : "fail",
          detail: parsed,
        };
      } catch {
        return {
          status: "fail",
          detail: raw,
        };
      }
    }
    return {
      status: "fail",
      detail: raw,
    };
  }
}

main().catch((error) => {
  process.stderr.write(`[sync-docs] failed: ${String(error.stack || error)}\n`);
  process.exitCode = 1;
});
