import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

const CHECKBOX_DONE_RE = /^\s*-\s*\[(x|X)\]\s+/;
const CHECKBOX_ANY_RE = /^\s*-\s*\[( |x|X)\]\s+/;
const HEADING_RE = /^(#{1,6})\s+(.+)$/;

export function normalizePath(inputPath) {
  return inputPath.split(path.sep).join("/");
}

export function getSectionFromRelativePath(relativePath) {
  const parts = normalizePath(relativePath).split("/");
  if (parts[0] === "skills") {
    return "skills";
  }
  if (parts[0] === "Harness") {
    return parts[1] ?? "Harness";
  }
  if (parts[0] !== "docs") {
    return "root";
  }
  return parts[1] ?? "root";
}

export function docIdFromPath(relativePath) {
  return Buffer.from(relativePath, "utf8").toString("base64url");
}

export function pathFromDocId(docId) {
  return Buffer.from(docId, "base64url").toString("utf8");
}

export function parseFrontMatter(markdown) {
  if (!markdown.startsWith("---\n")) {
    return { frontMatter: {}, body: markdown };
  }

  const end = markdown.indexOf("\n---\n", 4);
  if (end === -1) {
    return { frontMatter: {}, body: markdown };
  }

  const rawFrontMatter = markdown.slice(4, end);
  const body = markdown.slice(end + 5);
  const lines = rawFrontMatter.split("\n");
  const frontMatter = {};

  let activeKey = "";
  for (const line of lines) {
    const keyMatch = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (keyMatch) {
      const [, key, rawValue] = keyMatch;
      activeKey = key;
      if (rawValue === "") {
        frontMatter[key] = [];
      } else {
        frontMatter[key] = stripQuotes(rawValue.trim());
      }
      continue;
    }

    const itemMatch = line.match(/^\s*-\s*(.+)$/);
    if (itemMatch && activeKey) {
      if (!Array.isArray(frontMatter[activeKey])) {
        frontMatter[activeKey] = [];
      }
      frontMatter[activeKey].push(stripQuotes(itemMatch[1].trim()));
    }
  }

  return { frontMatter, body };
}

function stripQuotes(value) {
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  return value;
}

export function extractHeadings(markdownBody) {
  const headings = [];
  const lines = markdownBody.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(HEADING_RE);
    if (!match) {
      continue;
    }

    headings.push({
      level: match[1].length,
      text: match[2].trim(),
      line: index + 1,
    });
  }
  return headings;
}

export function countCheckboxes(markdownBody) {
  let total = 0;
  let done = 0;
  const lines = markdownBody.split("\n");

  for (const line of lines) {
    if (CHECKBOX_ANY_RE.test(line)) {
      total += 1;
      if (CHECKBOX_DONE_RE.test(line)) {
        done += 1;
      }
    }
  }

  return { total, done };
}

export function countWords(markdownBody) {
  const tokens = markdownBody
    .replace(/[`*_>#\-\[\](){}|]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  return tokens.length;
}

export function parseMarkdownTable(markdown, headingText) {
  const lines = markdown.split("\n");
  const headingIndex = lines.findIndex((line) => line.trim().toLowerCase() === headingText.trim().toLowerCase());
  if (headingIndex === -1) {
    return [];
  }

  const tableLines = [];
  for (let i = headingIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (tableLines.length > 0) {
        break;
      }
      continue;
    }
    if (!line.startsWith("|")) {
      if (tableLines.length > 0) {
        break;
      }
      continue;
    }
    tableLines.push(line);
  }

  if (tableLines.length < 3) {
    return [];
  }

  const headers = splitTableLine(tableLines[0]);
  const rows = [];

  for (let i = 2; i < tableLines.length; i += 1) {
    const values = splitTableLine(tableLines[i]);
    if (values.length === 0) {
      continue;
    }

    const row = {};
    headers.forEach((header, idx) => {
      row[header] = values[idx] ?? "";
    });
    rows.push(row);
  }

  return rows;
}

function splitTableLine(line) {
  return line
    .slice(1, -1)
    .split("|")
    .map((item) => item.trim());
}

export function parseImplementationPhases(markdown) {
  const lines = markdown.split("\n");
  const phases = [];
  let currentPhase = null;
  let currentStage = null;
  let inDoneWhen = false;

  for (const line of lines) {
    const phaseMatch = line.match(/^##\s+Phase\s+(\d+)\s+[—-]\s+(.+)$/);
    if (phaseMatch) {
      if (currentStage && currentPhase) {
        currentPhase.stages.push(finalizeStage(currentStage));
        currentStage = null;
      }
      if (currentPhase) {
        phases.push(finalizePhase(currentPhase));
      }

      currentPhase = {
        phase_number: Number(phaseMatch[1]),
        title: phaseMatch[2].trim(),
        phase_status: "unknown",
        stages: [],
        done_when: [],
      };
      inDoneWhen = false;
      continue;
    }

    if (!currentPhase) {
      continue;
    }

    const statusMatch = line.match(/^Phase status:\s+`([^`]+)`$/);
    if (statusMatch) {
      currentPhase.phase_status = statusMatch[1].trim();
      continue;
    }

    const stageMatch = line.match(/^###\s+Stage\s+([A-Za-z0-9]+)\s+[—-]\s+(.+)$/);
    if (stageMatch) {
      if (currentStage) {
        currentPhase.stages.push(finalizeStage(currentStage));
      }

      currentStage = {
        stage_id: stageMatch[1],
        title: stageMatch[2].trim(),
        checklist: [],
      };
      inDoneWhen = false;
      continue;
    }

    if (line.trim() === "Done when:") {
      if (currentStage) {
        currentPhase.stages.push(finalizeStage(currentStage));
        currentStage = null;
      }
      inDoneWhen = true;
      continue;
    }

    if (line.startsWith("## ")) {
      if (currentStage) {
        currentPhase.stages.push(finalizeStage(currentStage));
        currentStage = null;
      }
      inDoneWhen = false;
      continue;
    }

    const checklistMatch = line.match(/^\s*-\s*\[( |x|X)\]\s+(.+)$/);
    if (checklistMatch && currentStage) {
      currentStage.checklist.push({
        text: checklistMatch[2].trim(),
        done: checklistMatch[1].toLowerCase() === "x",
      });
      continue;
    }

    const bulletMatch = line.match(/^\s*-\s+(.+)$/);
    if (bulletMatch && inDoneWhen) {
      currentPhase.done_when.push(bulletMatch[1].trim());
    }
  }

  if (currentStage && currentPhase) {
    currentPhase.stages.push(finalizeStage(currentStage));
  }
  if (currentPhase) {
    phases.push(finalizePhase(currentPhase));
  }

  const stageCount = phases.reduce((acc, phase) => acc + phase.stages.length, 0);
  const stageDoneCount = phases.reduce(
    (acc, phase) => acc + phase.stages.reduce((stageAcc, stage) => stageAcc + Number(stage.is_complete), 0),
    0,
  );

  return {
    phase_count: phases.length,
    stage_count: stageCount,
    stage_done_count: stageDoneCount,
    phases,
  };
}

function finalizeStage(stage) {
  const checklist_total = stage.checklist.length;
  const checklist_done = stage.checklist.filter((item) => item.done).length;
  return {
    ...stage,
    checklist_total,
    checklist_done,
    completion: checklist_total === 0 ? 0 : Number((checklist_done / checklist_total).toFixed(3)),
    is_complete: checklist_total > 0 && checklist_total === checklist_done,
  };
}

function finalizePhase(phase) {
  const checklist_total = phase.stages.reduce((acc, stage) => acc + stage.checklist_total, 0);
  const checklist_done = phase.stages.reduce((acc, stage) => acc + stage.checklist_done, 0);

  return {
    ...phase,
    checklist_total,
    checklist_done,
    completion: checklist_total === 0 ? 0 : Number((checklist_done / checklist_total).toFixed(3)),
  };
}

export function parseLoopState(markdown) {
  const currentState = {};
  const stateSection = sectionBetween(markdown, "## Current State", "## Cycle History");
  for (const line of stateSection.split("\n")) {
    const match = line.match(/^\s*-\s*`([^`]+)`:\s*(.+)$/);
    if (!match) {
      continue;
    }
    const [, key, rawValue] = match;
    currentState[key] = rawValue.trim();
  }

  const history = parseMarkdownTable(markdown, "## Cycle History");
  return {
    ...currentState,
    run_count: Number(currentState.run_count ?? 0),
    history,
  };
}

export function parseCapabilityGaps(markdown) {
  const rows = parseMarkdownTable(markdown, "## Register Table");
  const normalized = rows.map((row) => ({
    gap_id: row.gap_id ?? "",
    opened_on: row.opened_on ?? "",
    status: row.status ?? "",
    class: row.class ?? "",
    owner: row.owner ?? "",
    enforcement_target: row.enforcement_target ?? "",
    evidence_link: row.evidence_link ?? "",
  }));

  return {
    open_count: normalized.filter((row) => row.status === "open").length,
    in_progress_count: normalized.filter((row) => row.status === "in_progress").length,
    blocked_count: normalized.filter((row) => row.status === "blocked").length,
    rows: normalized,
  };
}

export function parseChangelog(markdown) {
  const rows = parseMarkdownTable(markdown, "## Changelog Table");
  const normalized = rows.map((row) => ({
    entry_id: row.entry_id ?? "",
    date: row.date ?? "",
    cycle_id: row.cycle_id ?? "",
    phase_stage: row.phase_stage ?? "",
    change_type: row.change_type ?? "",
    summary: row.summary ?? "",
    docs_updated: row.docs_updated ?? "",
    human_gate_decision: row.human_gate_decision ?? "",
    approval_ref: row.approval_ref ?? "",
    approval_status: row.approval_status ?? "",
  }));

  return {
    entry_count: normalized.length,
    awaiting_human_review_count: normalized.filter((row) => row.approval_status === "awaiting_human_review").length,
    approved_count: normalized.filter((row) => row.approval_status === "approved").length,
    rows: normalized,
  };
}

export function parseCurrentFeatures(markdown) {
  const rows = parseMarkdownTable(markdown, "## Feature Table");
  const normalized = rows.map((row) => ({
    feature_id: row.feature_id ?? "",
    capability: row.capability ?? "",
    status: row.status ?? "",
    source_phase_stage: row.source_phase_stage ?? "",
    owner: row.owner ?? "",
    evidence_link: row.evidence_link ?? "",
    last_updated: row.last_updated ?? "",
  }));

  return {
    implemented_count: normalized.filter((row) => row.status === "implemented").length,
    pending_count: normalized.filter((row) => row.status === "pending").length,
    rows: normalized,
  };
}

export function parseCurrentGuidance(markdown) {
  const rows = parseMarkdownTable(markdown, "## Guidance Table");
  const normalized = rows.map((row) => ({
    guidance_id: row.guidance_id ?? "",
    rule: row.rule ?? "",
    enforcement_anchor: row.enforcement_anchor ?? "",
    operator_action: row.operator_action ?? "",
    status: row.status ?? "",
  }));

  return {
    active_count: normalized.filter((row) => row.status === "active").length,
    rows: normalized,
  };
}

export function parseLoopProcesses(markdown) {
  const rows = parseMarkdownTable(markdown, "## Process Table");
  const normalized = rows.map((row) => ({
    process_id: row.process_id ?? "",
    process_type: row.process_type ?? "",
    trigger: row.trigger ?? "",
    steps_summary: row.steps_summary ?? "",
    required_artifacts: row.required_artifacts ?? "",
    human_gate: row.human_gate ?? "",
    next_cycle_rule: row.next_cycle_rule ?? "",
  }));

  return {
    row_count: normalized.length,
    rows: normalized,
  };
}

function parseNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function parseHumanGateStats(markdown) {
  const rows = parseMarkdownTable(markdown, "## Human Gate Stats Table");
  const normalized = rows.map((row) => ({
    gate_id: row.gate_id ?? "",
    date: row.date ?? "",
    cycle_id: row.cycle_id ?? "",
    loop_id: row.loop_id ?? "",
    cycles_completed: parseNumber(row.cycles_completed),
    estimated_cycles_remaining: parseNumber(row.estimated_cycles_remaining),
    estimated_loops_remaining: parseNumber(row.estimated_loops_remaining),
    stages_remaining: parseNumber(row.stages_remaining),
    pending_approvals: parseNumber(row.pending_approvals),
    pending_features: parseNumber(row.pending_features),
    open_capability_gaps: parseNumber(row.open_capability_gaps),
    open_harness_upgrades: parseNumber(row.open_harness_upgrades),
    completion_percent: parseNumber(row.completion_percent),
    next_cycle_type: row.next_cycle_type ?? "",
    reviewer_action_required: row.reviewer_action_required ?? "",
    notes: row.notes ?? "",
  }));

  const latest =
    normalized[normalized.length - 1] ??
    {
      gate_id: "",
      date: "",
      cycle_id: "",
      loop_id: "",
      cycles_completed: 0,
      estimated_cycles_remaining: 0,
      estimated_loops_remaining: 0,
      stages_remaining: 0,
      pending_approvals: 0,
      pending_features: 0,
      open_capability_gaps: 0,
      open_harness_upgrades: 0,
      completion_percent: 0,
      next_cycle_type: "",
      reviewer_action_required: "",
      notes: "",
    };

  return {
    row_count: normalized.length,
    latest_estimated_cycles_remaining: latest.estimated_cycles_remaining,
    latest_estimated_loops_remaining: latest.estimated_loops_remaining,
    latest,
    rows: normalized,
  };
}

export function parseArchiveRegister(markdown) {
  const rows = parseMarkdownTable(markdown, "## Archive Register Table");
  const normalized = rows.map((row) => ({
    archive_id: row.archive_id ?? "",
    archived_on: row.archived_on ?? "",
    record_type: row.record_type ?? "",
    source_cycle: row.source_cycle ?? "",
    title: row.title ?? "",
    status: row.status ?? "",
    archive_path: row.archive_path ?? "",
    upgrade_review: row.upgrade_review ?? "",
    notes: row.notes ?? "",
  }));

  return {
    row_count: normalized.length,
    update_count: normalized.filter((row) => row.record_type === "update").length,
    upgrade_review_count: normalized.filter((row) => row.record_type === "upgrade_review").length,
    suggestion_count: normalized.filter((row) => row.record_type === "suggestion").length,
    rows: normalized,
  };
}

export function evaluateDocumentationReviewStatus(markdown) {
  const artifactPath = "Harness/artifacts/control/documentation_review_status.md";
  if (!markdown || typeof markdown !== "string" || !markdown.trim()) {
    return {
      status: "fail",
      detail: {
        reason: "artifact_unreadable_or_missing",
        artifact: artifactPath,
      },
    };
  }

  const kv = {};
  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.trim();
    const match = line.match(/^- `([^`]+)`: (.+)$/);
    if (match) {
      kv[match[1].trim()] = match[2].trim();
    }
  }

  const requiredKeys = ["review_loop_enabled", "cadence", "blocking_mode", "last_review_cycle", "next_review_due_cycle"];
  const missingKeys = requiredKeys.filter((key) => !String(kv[key] ?? "").trim());
  const enabled = String(kv.review_loop_enabled ?? "").trim().toLowerCase() === "true";
  const blockingMode = String(kv.blocking_mode ?? "").trim();

  if (!enabled) {
    return {
      status: "fail",
      detail: {
        reason: "review_loop_disabled_or_invalid",
        artifact: artifactPath,
        parsed: kv,
      },
    };
  }

  if (missingKeys.length > 0) {
    return {
      status: "warn",
      detail: {
        reason: "required_keys_missing_or_empty",
        artifact: artifactPath,
        missing_keys: missingKeys,
        parsed: kv,
      },
    };
  }

  if (blockingMode !== "risk_based") {
    return {
      status: "fail",
      detail: {
        reason: "blocking_mode_not_risk_based",
        artifact: artifactPath,
        expected: "risk_based",
        actual: blockingMode,
        parsed: kv,
      },
    };
  }

  return {
    status: "pass",
    detail: {
      artifact: artifactPath,
      parsed: kv,
    },
  };
}

function parseKeyValueBullets(markdown) {
  const kv = {};
  for (const rawLine of String(markdown ?? "").split("\n")) {
    const line = rawLine.trim();
    const match = line.match(/^- `([^`]+)`: (.+)$/);
    if (match) {
      kv[match[1].trim()] = match[2].trim();
    }
  }
  return kv;
}

function parseBoolean(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase() === "true";
}

export function parseCompatibilityWindowStatus(markdown) {
  if (!markdown || typeof markdown !== "string" || !markdown.trim()) {
    return null;
  }

  const kv = parseKeyValueBullets(markdown);
  const blockingIssuesRaw = String(kv.blocking_issues ?? "")
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    window_start_date: String(kv.window_start_date ?? ""),
    required_approved_cycles: Number(kv.required_approved_cycles ?? 0) || 0,
    approved_cycles_completed: Number(kv.approved_cycles_completed ?? 0) || 0,
    current_slot: String(kv.current_slot ?? ""),
    legacy_pointers_enabled: parseBoolean(kv.legacy_pointers_enabled),
    legacy_fallbacks_enabled: parseBoolean(kv.legacy_fallbacks_enabled),
    cycle_028_ready: parseBoolean(kv.cycle_028_ready),
    blocking_issues: blockingIssuesRaw,
  };
}

export function parseTopology(containerTopologyMarkdown, serviceBoundariesMarkdown) {
  const namespaces = parseMarkdownTable(containerTopologyMarkdown, "## Topology by Namespace");
  const boundaries = parseMarkdownTable(serviceBoundariesMarkdown, "## Boundary Map");

  return {
    namespaces: namespaces.map((row) => ({
      namespace: row.namespace ?? "",
      containers_services: row["containers/services"] ?? "",
      intent: row.intent ?? "",
    })),
    boundaries: boundaries.map((row) => ({
      service: row.service ?? "",
      primary_role: row["primary role"] ?? "",
      owns: row.owns ?? "",
      does_not_own: row["does not own"] ?? "",
      key_contracts: row["key contracts"] ?? "",
    })),
  };
}

function stripCodeTicks(value) {
  return String(value ?? "").trim().replace(/^`(.+)`$/, "$1");
}

export function parseServiceCatalog(markdown) {
  const rows = parseMarkdownTable(markdown, "## Catalog Table");
  return rows.map((row) => ({
    service: stripCodeTicks(row.service ?? ""),
    domain: row.domain ?? "",
    responsibility: row.responsibility ?? "",
    phase_target: row.phase_target ?? "",
  }));
}

export async function collectImplementedSurfaces(repoRoot) {
  const implemented = new Set(["apps/ui"]);
  const servicesDir = path.join(repoRoot, "apps", "services");

  try {
    const entries = await fs.readdir(servicesDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) {
        continue;
      }
      if (entry.name === "__pycache__" || entry.name.startsWith(".")) {
        continue;
      }
      implemented.add(entry.name);
    }
  } catch {
    // Best-effort inventory; if services dir is unavailable we still include apps/ui.
  }

  return implemented;
}

function parseListSection(markdown, startHeading) {
  const lines = markdown.split("\n");
  const startIndex = lines.findIndex((line) => line.trim().toLowerCase() === startHeading.toLowerCase());
  if (startIndex === -1) {
    return [];
  }

  const items = [];
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.startsWith("## ")) {
      break;
    }
    const match = line.match(/^\s*-\s+(.+)$/);
    if (match) {
      items.push(match[1].trim());
    }
  }
  return items;
}

function parseActiveObjectives(markdown) {
  const lines = markdown.split("\n");
  const objectives = [];
  let current = null;

  for (const line of lines) {
    const objectiveStart = line.match(/^##\s+Active Objective\s+(.+)$/);
    if (objectiveStart) {
      if (current) {
        objectives.push(current);
      }
      current = {
        objective_id: objectiveStart[1].trim(),
        goal: "",
        in_scope: "",
        out_of_scope: "",
        stop_conditions: "",
      };
      continue;
    }

    if (!current) {
      continue;
    }

    if (line.startsWith("## ")) {
      objectives.push(current);
      current = null;
      continue;
    }

    const goalMatch = line.match(/^\s*-\s+Goal:\s*(.+)$/);
    if (goalMatch) {
      current.goal = goalMatch[1].trim();
      continue;
    }

    const inScopeMatch = line.match(/^\s*-\s+In scope:\s*(.+)$/);
    if (inScopeMatch) {
      current.in_scope = inScopeMatch[1].trim();
      continue;
    }

    const outOfScopeMatch = line.match(/^\s*-\s+Out of scope:\s*(.+)$/);
    if (outOfScopeMatch) {
      current.out_of_scope = outOfScopeMatch[1].trim();
      continue;
    }

    const stopConditionsMatch = line.match(/^\s*-\s+Stop conditions:\s*(.+)$/);
    if (stopConditionsMatch) {
      current.stop_conditions = stopConditionsMatch[1].trim();
    }
  }

  if (current) {
    objectives.push(current);
  }

  return objectives.filter((objective) => objective.goal);
}

function parseMission(readmeMarkdown) {
  const lines = readmeMarkdown
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  for (const line of lines) {
    if (line.startsWith("#")) {
      continue;
    }
    if (line.startsWith("##")) {
      continue;
    }
    if (line.startsWith("-")) {
      continue;
    }
    return line;
  }

  return "Docs-first harness for an enterprise, multi-container, agentic RAG platform.";
}

export function buildProjectOverview({ readmeMarkdown, architectureMarkdown, engineerEntrypointMarkdown, phases }) {
  const mission = parseMission(readmeMarkdown);
  const architectureGoals = parseListSection(architectureMarkdown, "## Architectural Goals");
  const activeObjectives = parseActiveObjectives(engineerEntrypointMarkdown);

  const summary = {
    completed: 0,
    pending: 0,
    other: 0,
  };

  for (const phase of phases.phases) {
    if (phase.phase_status === "completed") {
      summary.completed += 1;
    } else if (phase.phase_status === "pending") {
      summary.pending += 1;
    } else {
      summary.other += 1;
    }
  }

  return {
    mission,
    architecture_goals: architectureGoals,
    active_objective_count: activeObjectives.length,
    active_objectives: activeObjectives,
    phase_status_summary: summary,
  };
}

export function buildServiceInventory(catalogRows, implementedSurfaces) {
  const rows = [];
  const plannedServices = new Set();

  for (const row of catalogRows) {
    const service = row.service;
    plannedServices.add(service);
    const implemented = implementedSurfaces.has(service);
    rows.push({
      service,
      domain: row.domain,
      phase_target: row.phase_target,
      implementation_surface: implemented ? (service === "apps/ui" ? "apps/ui" : `apps/services/${service}`) : "",
      status: implemented ? "implemented" : "planned_only",
    });
  }

  for (const service of implementedSurfaces) {
    if (plannedServices.has(service)) {
      continue;
    }
    rows.push({
      service,
      domain: "runtime",
      phase_target: "n/a",
      implementation_surface: service === "apps/ui" ? "apps/ui" : `apps/services/${service}`,
      status: "unmapped_implementation",
    });
  }

  const plannedCount = catalogRows.length;
  const implementedCount = rows.filter((row) => row.status === "implemented").length;
  const plannedOnlyCount = rows.filter((row) => row.status === "planned_only").length;
  const unmappedImplementationCount = rows.filter((row) => row.status === "unmapped_implementation").length;

  rows.sort((a, b) => a.service.localeCompare(b.service));

  return {
    planned_count: plannedCount,
    implemented_count: implementedCount,
    planned_only_count: plannedOnlyCount,
    unmapped_implementation_count: unmappedImplementationCount,
    rows,
  };
}

function sectionByHeading(markdown, heading) {
  const lines = markdown.split("\n");
  const headingNormalized = heading.trim().toLowerCase();
  const startIndex = lines.findIndex((line) => line.trim().toLowerCase() === headingNormalized);
  if (startIndex === -1) {
    return "";
  }

  const startLine = lines[startIndex].trim();
  const headingLevel = (startLine.match(/^#+/)?.[0] ?? "").length || 1;
  const section = [];

  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const line = lines[index];
    const headingMatch = line.match(/^(#{1,6})\s+/);
    if (headingMatch && headingMatch[1].length <= headingLevel) {
      break;
    }
    section.push(line);
  }

  return section.join("\n");
}

function sectionByHeadingAny(markdown, headings) {
  for (const heading of headings) {
    const section = sectionByHeading(markdown, heading);
    if (section.trim()) {
      return section;
    }
  }
  return "";
}

function parseBulletList(text) {
  const rows = [];
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*-\s+(.+)$/);
    if (match) {
      rows.push(match[1].trim());
    }
  }
  return rows;
}

function parseChecklistRows(text) {
  const rows = [];
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*-\s*\[( |x|X)\]\s+(.+)$/);
    if (match) {
      rows.push(match[2].trim());
    }
  }
  return rows;
}

function parseNumberedList(text) {
  const rows = [];
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*\d+\.\s+(.+)$/);
    if (match) {
      rows.push(match[1].trim());
    }
  }
  return rows;
}

function normalizeDocPath(basePath, linkPath) {
  const value = String(linkPath ?? "").trim();
  if (!value) {
    return "";
  }
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }
  if (
    value === "AGENTS.md" ||
    value === "README.md" ||
    value.startsWith("docs/") ||
    value.startsWith("skills/")
  ) {
    return normalizePath(value);
  }

  const normalizedBase = normalizePath(basePath);
  const baseDir = path.posix.dirname(normalizedBase);
  const joined = path.posix.join(baseDir, value);
  return normalizePath(path.posix.normalize(joined));
}

function parseNumberedLinkItems(text, basePath) {
  const rows = [];
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*\d+\.\s+\[([^\]]+)\]\(([^)]+)\)/);
    if (!match) {
      continue;
    }
    rows.push({
      label: match[1].trim(),
      path: normalizeDocPath(basePath, match[2].trim()),
    });
  }
  return rows;
}

function parsePurpose(markdown) {
  const purposeSection = sectionByHeading(markdown, "## Purpose");
  const bullets = parseBulletList(purposeSection);
  if (bullets.length > 0) {
    return bullets[0];
  }

  const lines = purposeSection
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines[0] ?? "";
}

function buildFlow({ flow_id, title, trigger, steps, required_artifacts, human_gates, source_docs }) {
  return {
    flow_id,
    title,
    trigger,
    steps,
    required_artifacts,
    human_gates,
    source_docs,
  };
}

function buildSkill({ skill_id, title, source_doc, markdown, currentItemsHeading, fallbackItemsHeading }) {
  const primarySection = sectionByHeading(markdown, currentItemsHeading);
  const fallbackSection = fallbackItemsHeading ? sectionByHeading(markdown, fallbackItemsHeading) : "";
  const currentItems = parseNumberedLinkItems(primarySection || fallbackSection, source_doc);

  return {
    skill_id,
    title,
    purpose: parsePurpose(markdown),
    source_doc,
    current_items: currentItems,
  };
}

function pickCommand(commands, matchText) {
  const lowered = matchText.toLowerCase();
  return commands.find((command) => command.toLowerCase().includes(lowered)) ?? "";
}

export function buildHarnessHelp({
  codexRunLoopMarkdown,
  updateRoutineMarkdown,
  upgradeRoutineMarkdown,
  toolingPipelineMarkdown,
  changeTrackingMarkdown,
  agentsMarkdown,
  gitWorkflowMarkdown,
  docStyleMarkdown,
  readmeMarkdown,
  capabilityUpdatesMarkdown,
  capabilityUpgradesMarkdown,
  capabilityToolingMarkdown,
  capabilityGovernanceMarkdown,
  capabilityIntegrationsMarkdown,
  capabilitySuggestionsMarkdown,
  repoSkillRegistryMarkdown = "",
  compatibilityWindowStatusMarkdown = "",
}) {
  const readmeCommands = parseBulletList(sectionByHeading(readmeMarkdown, "### Deterministic Quality Gates"));
  const toolingChecklist = parseChecklistRows(sectionByHeading(toolingPipelineMarkdown, "## Verification Checklist"));
  const toolingStages = parseNumberedList(sectionByHeading(toolingPipelineMarkdown, "## Pipeline Stages"));
  const updateSteps = parseNumberedList(sectionByHeadingAny(updateRoutineMarkdown, ["## Steps", "## Routine"]));
  const updateHumanGates = parseBulletList(
    sectionByHeadingAny(updateRoutineMarkdown, ["## Gate Requirement", "## Human Gate", "## Human Gate Requirement"]),
  );
  const upgradeSteps = parseNumberedList(sectionByHeadingAny(upgradeRoutineMarkdown, ["## Steps", "## Routine"]));
  const upgradeHumanGates = parseBulletList(
    sectionByHeadingAny(upgradeRoutineMarkdown, ["## Gate Requirement", "## Human Gate", "## Human Gate Requirement"]),
  );

  const flows = [
    buildFlow({
      flow_id: "phase_execution_loop",
      title: "Phase Execution Loop",
      trigger: "Approved phase and stage task",
      steps: parseNumberedList(sectionByHeading(codexRunLoopMarkdown, "## Cycle Contract")),
      required_artifacts: parseBulletList(sectionByHeading(codexRunLoopMarkdown, "## Required Artifacts Per Cycle")),
      human_gates: parseBulletList(sectionByHeading(codexRunLoopMarkdown, "## Mandatory Human Gate")),
      source_docs: [
        "docs/11_ops/codex_run_loop.md",
        "docs/15_checklists/agent_cycle_gate.md",
        "Harness/artifacts/control/loop_processes.md",
      ],
    }),
    buildFlow({
      flow_id: "update_cycle_loop",
      title: "Update Cycle Loop",
      trigger: "Implementation/update cycle scope approved",
      steps: updateSteps,
      required_artifacts: parseBulletList(sectionByHeading(changeTrackingMarkdown, "## Tracking Artifacts")),
      human_gates: updateHumanGates,
      source_docs: [
        "docs/entrypoint_guide/update_cycle_routine.md",
        "docs/11_ops/change_tracking_system.md",
        "docs/11_ops/codex_run_loop.md",
      ],
    }),
    buildFlow({
      flow_id: "upgrade_cycle_loop",
      title: "Upgrade Cycle Loop",
      trigger: "Post-human-gate triage or open harness backlog item",
      steps: upgradeSteps,
      required_artifacts: [
        "docs/exec_plans/tech-debt-tracker.md",
        "Harness/artifacts/control/changelog.md",
        "Harness/artifacts/control/current_guidance.md",
        "Harness/artifacts/control/archive_register.md",
        "Harness/artifacts/control/human_gate_stats.md",
      ],
      human_gates: upgradeHumanGates,
      source_docs: [
        "docs/entrypoint_guide/upgrade_cycle_routine.md",
        "docs/11_ops/upgrades.md",
        "docs/exec_plans/tech-debt-tracker.md",
      ],
    }),
    buildFlow({
      flow_id: "tooling_pipeline_loop",
      title: "Tooling and Guardrail Loop",
      trigger: "Cycle closeout and quality gate verification",
      steps: toolingStages,
      required_artifacts: parseBulletList(sectionByHeading(toolingPipelineMarkdown, "## Generated QA Signals")),
      human_gates: [
        ...toolingStages.filter((step) => step.toLowerCase().includes("block continuation")),
        ...toolingChecklist,
      ],
      source_docs: [
        "docs/11_ops/tooling_pipeline.md",
        "docs/11_ops/git_workflow_gitlab.md",
        "docs/exec_plans/tooling/completed/tooling_review_2026-02-24_harness_and_branching.md",
      ],
    }),
    buildFlow({
      flow_id: "harness_review_loop",
      title: "Harness Review and Tracking Loop",
      trigger: "Cycle closeout requires report synchronization and approval visibility",
      steps: parseNumberedList(sectionByHeading(changeTrackingMarkdown, "## Required Update Contract Per Cycle")),
      required_artifacts: parseBulletList(sectionByHeading(changeTrackingMarkdown, "## Tracking Artifacts")),
      human_gates: parseBulletList(sectionByHeading(changeTrackingMarkdown, "## Approval Gate Contract")),
      source_docs: [
        "docs/11_ops/change_tracking_system.md",
        "Harness/artifacts/control/changelog.md",
        "Harness/artifacts/control/human_gate_stats.md",
      ],
    }),
  ];

  const skills = [
    buildSkill({
      skill_id: "capability_updates",
      title: "Capability Pipeline Updates",
      source_doc: "docs/exec_plans/updates/active/index.md",
      markdown: capabilityUpdatesMarkdown,
      currentItemsHeading: "## Current Items",
    }),
    buildSkill({
      skill_id: "capability_upgrades",
      title: "Capability Pipeline Upgrades",
      source_doc: "docs/exec_plans/upgrades/active/index.md",
      markdown: capabilityUpgradesMarkdown,
      currentItemsHeading: "## Current Items",
    }),
    buildSkill({
      skill_id: "capability_tooling",
      title: "Capability Pipeline Tooling",
      source_doc: "docs/exec_plans/tooling/active/index.md",
      markdown: capabilityToolingMarkdown,
      currentItemsHeading: "## Current Items",
    }),
    buildSkill({
      skill_id: "capability_governance",
      title: "Capability Pipeline Governance",
      source_doc: "docs/exec_plans/implementation/active/index.md",
      markdown: capabilityGovernanceMarkdown,
      currentItemsHeading: "## Current Items",
    }),
    buildSkill({
      skill_id: "capability_integrations",
      title: "Capability Pipeline Integrations",
      source_doc: "docs/exec_plans/tooling/active/index.md",
      markdown: capabilityIntegrationsMarkdown,
      currentItemsHeading: "## Current Items",
    }),
    buildSkill({
      skill_id: "capability_suggestions",
      title: "Capability Pipeline Suggestions",
      source_doc: "docs/exec_plans/implementation/active/index.md",
      markdown: capabilitySuggestionsMarkdown,
      currentItemsHeading: "## Current Pending Suggestions",
      fallbackItemsHeading: "## Current Items",
    }),
  ];

  const repoSkills = parseMarkdownTable(repoSkillRegistryMarkdown, "## Skills Table").map((row) => ({
    skill_id: row.skill_id ?? "",
    title: row.title ?? "",
    path: row.path ?? "",
    mode: row.mode ?? "",
    owner: row.owner ?? "",
    status: row.status ?? "",
  }));
  const compatibilityWindow = parseCompatibilityWindowStatus(compatibilityWindowStatusMarkdown);

  const branchStructure = parseBulletList(sectionByHeading(gitWorkflowMarkdown, "## Incremental Branch Structure"));
  const agentsExecution = parseNumberedList(sectionByHeading(agentsMarkdown, "## 1. Execution Model"));
  const docStyleDecisions = parseBulletList(sectionByHeading(docStyleMarkdown, "## Topic Decisions"));

  const conventions = [
    {
      convention_id: "conv-git-branch-hygiene",
      category: "git",
      rule: branchStructure[0] ?? "Start every cycle from main and create one scoped branch.",
      enforcement_command: pickCommand(readmeCommands, "branch-hygiene") || "make branch-hygiene",
      source_doc: "docs/11_ops/git_workflow_gitlab.md",
    },
    {
      convention_id: "conv-python-lint",
      category: "python",
      rule: "Python quality checks are mandatory before handoff and merge.",
      enforcement_command: pickCommand(readmeCommands, "lint-py") || "make lint-py",
      source_doc: "README.md",
    },
    {
      convention_id: "conv-markdown-lint",
      category: "markdown",
      rule: docStyleDecisions[2] ?? "Style rules are tool-enforced and treated as quality gates.",
      enforcement_command: pickCommand(readmeCommands, "lint-md") || "make lint-md",
      source_doc: "docs/13_style_guides/doc_style.md",
    },
    {
      convention_id: "conv-engineer-entry-guard",
      category: "harness",
      rule: "Engineer-entry context is read-only for agent writes and requires frontmatter validation.",
      enforcement_command:
        pickCommand(toolingStages, "check:engineer-entry") || "npm --prefix dev_tracker/ui run check:engineer-entry",
      source_doc: "docs/11_ops/tooling_pipeline.md",
    },
    {
      convention_id: "conv-cycle-gate",
      category: "governance",
      rule: agentsExecution[6] ?? "Execute exactly one approved cycle before stopping at a human gate.",
      enforcement_command: pickCommand(readmeCommands, "make lint") || "make lint",
      source_doc: "AGENTS.md",
    },
  ];

  const guidelines = [
    {
      label: "Codex Run Loop",
      path: "docs/11_ops/codex_run_loop.md",
      description: "Planner->implementer cycle contract, human gates, and stop conditions.",
    },
    {
      label: "Tooling Pipeline",
      path: "docs/11_ops/tooling_pipeline.md",
      description: "Deterministic quality gates and generated QA signals.",
    },
    {
      label: "Git Workflow",
      path: "docs/11_ops/git_workflow_gitlab.md",
      description: "Branch discipline, routing markers, and MR gate requirements.",
    },
    {
      label: "Capability Pipeline Index",
      path: "docs/exec_plans/index.md",
      description: "Lifecycle-first execution plans and completed artifact routing.",
    },
    {
      label: "Entrypoint Guide Index",
      path: "docs/entrypoint_guide/index.md",
      description: "Phase initiation, update routine, and upgrade routine execution guides.",
    },
    {
      label: "Change Tracking System",
      path: "docs/11_ops/change_tracking_system.md",
      description: "Required per-cycle report updates and approval gating.",
    },
  ];

  return {
    flows,
    skills,
    conventions,
    guidelines,
    proposal: {
      title: "Dev Tracker UI Reorganization Update Plan (2026-02-24)",
      path: "docs/exec_plans/commissioning/completed/dev_tracker_ui_reorganization_update_plan_2026-02-24.md",
      guard_text: "DO NOT EXECUTE THIS PLAN WITHOUT HUMAN CONFIRMATION",
    },
    repo_skills: repoSkills,
    compatibility_window: compatibilityWindow,
  };
}

function sectionBetween(markdown, startHeading, endHeading) {
  const lines = markdown.split("\n");
  const startIndex = lines.findIndex((line) => line.trim().toLowerCase() === startHeading.toLowerCase());
  if (startIndex === -1) {
    return "";
  }

  const endIndex = lines.findIndex((line, idx) => idx > startIndex && line.trim().toLowerCase() === endHeading.toLowerCase());
  return lines.slice(startIndex + 1, endIndex === -1 ? undefined : endIndex).join("\n");
}

export function inferPolicyDomain(record) {
  const section = record.section;
  const lowerPath = record.relative_path.toLowerCase();

  if (section === "10_security") return "security";
  if (section === "02_contracts" || section === "04_services") return "interfaces";
  if (section === "07_storage") return "storage";
  if (section === "06_retrieval") return "retrieval";
  if (section === "08_observability" || lowerPath.includes("logging")) return "observability";
  if (section === "11_ops") return "operations";
  if (section === "12_pipelines") return "pipelines";
  if (section === "05_ingestion") return "ingestion";
  if (section === "09_evaluation") return "evaluation";
  if (section === "03_architecture") return "architecture";
  if (section === "15_checklists" || lowerPath.includes("governance")) return "governance";
  return "general";
}

export function buildPolicySummaries(records, nowDate = new Date()) {
  const domainMap = new Map();
  for (const record of records) {
    if (!record.relative_path.startsWith("docs/")) {
      continue;
    }

    const domain = inferPolicyDomain(record);
    if (!domainMap.has(domain)) {
      domainMap.set(domain, {
        domain,
        doc_count: 0,
        missing_owner_count: 0,
        missing_status_count: 0,
        stale_review_count: 0,
        doc_ids: [],
      });
    }

    const entry = domainMap.get(domain);
    entry.doc_count += 1;
    entry.doc_ids.push(record.id);

    if (!record.owner) {
      entry.missing_owner_count += 1;
    }
    if (!record.status) {
      entry.missing_status_count += 1;
    }
    if (isStale(record.last_reviewed, nowDate)) {
      entry.stale_review_count += 1;
    }
  }

  return Array.from(domainMap.values()).sort((a, b) => a.domain.localeCompare(b.domain));
}

export function isStale(lastReviewed, nowDate = new Date()) {
  if (!lastReviewed) {
    return true;
  }
  const timestamp = Date.parse(lastReviewed);
  if (Number.isNaN(timestamp)) {
    return true;
  }

  const ageMs = nowDate.getTime() - timestamp;
  const staleMs = 180 * 24 * 60 * 60 * 1000;
  return ageMs > staleMs;
}

export async function walkMarkdownFiles(baseDir) {
  const queue = [baseDir];
  const files = [];

  while (queue.length > 0) {
    const current = queue.pop();
    const entries = await fs.readdir(current, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        queue.push(fullPath);
        continue;
      }
      if (entry.isFile() && entry.name.endsWith(".md")) {
        files.push(fullPath);
      }
    }
  }

  files.sort((a, b) => normalizePath(a).localeCompare(normalizePath(b)));
  return files;
}

export function collectGitState(repoRoot) {
  const branch = gitRead(repoRoot, ["rev-parse", "--abbrev-ref", "HEAD"], "unknown");
  const short_sha = gitRead(repoRoot, ["rev-parse", "--short", "HEAD"], "unknown");
  const last_commit = gitRead(repoRoot, ["show", "-s", "--format=%h | %ad | %s", "--date=short"], "unknown");
  const statusRaw = gitRead(repoRoot, ["status", "--porcelain=v1"], "");
  const dirty = statusRaw.trim().length > 0;

  const changedFromHead = gitRead(repoRoot, ["diff", "--name-only", "HEAD", "--", "*.md"], "");
  const staged = gitRead(repoRoot, ["diff", "--cached", "--name-only", "--", "*.md"], "");

  const changedSet = new Set();
  parseStatusMarkdownPaths(statusRaw).forEach((item) => changedSet.add(item));
  splitLines(changedFromHead).forEach((item) => changedSet.add(item));
  splitLines(staged).forEach((item) => changedSet.add(item));

  const markdown_changed_files = Array.from(changedSet)
    .map((item) => normalizePath(item))
    .filter((item) => item.endsWith(".md"))
    .sort((a, b) => a.localeCompare(b));

  const grouped_by_section = {};
  for (const file of markdown_changed_files) {
    const section = file.startsWith("docs/") ? file.split("/")[1] ?? "root" : "root";
    if (!grouped_by_section[section]) {
      grouped_by_section[section] = [];
    }
    grouped_by_section[section].push(file);
  }

  return {
    version: "GitStateV1",
    branch,
    short_sha,
    last_commit,
    dirty,
    markdown_changed_count: markdown_changed_files.length,
    markdown_changed_files,
    grouped_by_section,
  };
}

function parseStatusMarkdownPaths(statusRaw) {
  const files = [];
  for (const line of splitLines(statusRaw)) {
    if (line.length < 4) {
      continue;
    }
    const pathPart = line.slice(3).trim();
    if (!pathPart.includes(".md")) {
      continue;
    }
    if (pathPart.includes(" -> ")) {
      files.push(pathPart.split(" -> ").at(-1));
    } else {
      files.push(pathPart);
    }
  }
  return files;
}

function splitLines(input) {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function gitRead(repoRoot, args, fallback) {
  try {
    return execFileSync("git", ["-C", repoRoot, ...args], { encoding: "utf8" }).trim();
  } catch {
    return fallback;
  }
}
