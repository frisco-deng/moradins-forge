import { describe, expect, it } from "vitest";

// @ts-ignore local script module is intentionally untyped
import {
  buildHarnessHelp,
  buildProjectOverview,
  buildServiceInventory,
  evaluateDocumentationReviewStatus,
  parseCompatibilityWindowStatus,
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
} from "../scripts/lib/snapshot-lib.mjs";

describe("snapshot parser helpers", () => {
  it("parses frontmatter lists and body", () => {
    const markdown = `---\ntitle: \"Example\"\nowner: platform\nrelated_docs:\n  - a.md\n  - b.md\n---\n\n# Heading\n`;
    const parsed = parseFrontMatter(markdown);

    expect(parsed.frontMatter.title).toBe("Example");
    expect(parsed.frontMatter.owner).toBe("platform");
    expect(parsed.frontMatter.related_docs).toEqual(["a.md", "b.md"]);
    expect(parsed.body).toContain("# Heading");
  });

  it("parses phase document stages and checklists", () => {
    const markdown = `## Phase 1 — Test\n\nPhase status: \`pending\`\n\n### Stage 01 — A\n\n- [x] done\n- [ ] open\n\nDone when:\n\n- all set\n`;
    const phases = parseImplementationPhases(markdown);

    expect(phases.phase_count).toBe(1);
    expect(phases.stage_count).toBe(1);
    expect(phases.phases[0]?.checklist_done).toBe(1);
  });

  it("parses loop state and capability table", () => {
    const loop = parseLoopState(`# Loop State\n\n## Current State\n\n- \`run_count\`: 3\n- \`last_run_id\`: abc\n\n## Cycle History\n\n| run_id | date | result | human_decision | notes |\n| --- | --- | --- | --- | --- |\n| abc | 2026-02-23 | success | continue | ok |\n`);
    expect(loop.run_count).toBe(3);
    expect(loop.history).toHaveLength(1);

    const gaps = parseCapabilityGaps(`## Register Table\n\n| gap_id | opened_on | status | class | owner | enforcement_target | evidence_link |\n| --- | --- | --- | --- | --- | --- | --- |\n| GAP-1 | 2026-02-23 | open | docs | team | checklist | link |\n`);
    expect(gaps.open_count).toBe(1);
    expect(gaps.rows[0]?.gap_id).toBe("GAP-1");
  });

  it("parses topology and boundary tables", () => {
    const topology = parseTopology(
      `## Topology by Namespace\n\n| namespace | containers/services | intent |\n| --- | --- | --- |\n| rag-edge | ui,gateway | entry |\n`,
      `## Boundary Map\n\n| service | primary role | owns | does not own | key contracts |\n| --- | --- | --- | --- | --- |\n| gateway_api | ingress | auth | ranking | RetrievalRequestV1 |\n`,
    );

    expect(topology.namespaces[0]?.namespace).toBe("rag-edge");
    expect(topology.boundaries[0]?.service).toBe("gateway_api");
  });

  it("builds service inventory and project overview summaries", () => {
    const catalog = parseServiceCatalog(
      `## Catalog Table\n\n| service | domain | responsibility | phase_target |\n| --- | --- | --- | --- |\n| \`gateway_api\` | edge | ingress | phase 1 |\n| \`apps/ui\` | edge | ui | phase 3 |\n`,
    );

    const inventory = buildServiceInventory(catalog, new Set(["gateway_api", "apps/ui", "parser_service"]));
    expect(inventory.planned_count).toBe(2);
    expect(inventory.implemented_count).toBe(2);
    expect(inventory.unmapped_implementation_count).toBe(1);

    const phases = parseImplementationPhases(
      `## Phase 1 - Test\n\nPhase status: \`completed\`\n\n### Stage 01 - A\n\n- [x] done\n\n## Phase 2 - Test\n\nPhase status: \`pending\`\n\n### Stage 02 - B\n\n- [ ] open\n`,
    );

    const overview = buildProjectOverview({
      readmeMarkdown: "# repo\n\nDocs-first harness for testing.\n",
      architectureMarkdown: "## Architectural Goals\n\n- Goal A\n- Goal B\n",
      engineerEntrypointMarkdown:
        "## Active Objective O-001\n\n- Goal: finish stage\n- In scope: scope\n- Out of scope: none\n- Stop conditions: blockers\n",
      phases,
    });

    expect(overview.mission).toBe("Docs-first harness for testing.");
    expect(overview.architecture_goals).toEqual(["Goal A", "Goal B"]);
    expect(overview.active_objective_count).toBe(1);
    expect(overview.phase_status_summary.completed).toBe(1);
    expect(overview.phase_status_summary.pending).toBe(1);
  });

  it("builds harness help loops, skills, conventions, and guideline links", () => {
    const help = buildHarnessHelp({
      codexRunLoopMarkdown: `## Cycle Contract\n\n1. plan\n2. execute\n\n## Required Artifacts Per Cycle\n\n- changelog.md\n- loop_state.md\n\n## Mandatory Human Gate\n\n- approval required\n`,
      updateRoutineMarkdown: `## Steps\n\n1. run update\n2. sync docs\n\n## Gate Requirement\n\n- approval before next cycle\n`,
      upgradeRoutineMarkdown: `## Steps\n\n1. triage\n2. upgrade\n\n## Gate Requirement\n\n- route decisions required\n`,
      toolingPipelineMarkdown: `## Pipeline Stages\n\n1. make branch-hygiene\n2. npm --prefix dev_tracker/ui run check:engineer-entry\n3. Block continuation\n\n## Generated QA Signals\n\n- qa_signals_v1.json\n\n## Verification Checklist\n\n- [ ] tooling checks complete\n`,
      changeTrackingMarkdown: `## Tracking Artifacts\n\n- changelog.md\n- current_guidance.md\n\n## Required Update Contract Per Cycle\n\n1. update reports\n2. add approvals\n\n## Approval Gate Contract\n\n- cycle N+1 blocked without approval\n`,
      agentsMarkdown: `## 1. Execution Model\n\n1. Interpret task\n2. Select ruleset\n3. Execute exactly one approved cycle.\n`,
      gitWorkflowMarkdown: `## Incremental Branch Structure\n\n- Start every cycle from main and create one scoped branch.\n`,
      docStyleMarkdown: `## Topic Decisions\n\n- readability\n- standardize\n- Style rules are tool-enforced and treated as quality gates.\n`,
      readmeMarkdown: `### Deterministic Quality Gates\n\n- make lint-py\n- make lint-md\n- make branch-hygiene\n- make lint\n`,
      capabilityUpdatesMarkdown: `## Purpose\n\n- Track update-scope items.\n\n## Current Items\n\n1. [UPD](upd.md)\n`,
      capabilityUpgradesMarkdown: `## Purpose\n\n- Track upgrade-scope items.\n\n## Current Items\n\n1. [UPR](upr.md)\n`,
      capabilityToolingMarkdown: `## Purpose\n\n- Track tooling items.\n\n## Current Items\n\n1. [TLG](tlg.md)\n`,
      capabilityGovernanceMarkdown: `## Purpose\n\n- Track governance items.\n\n## Current Items\n\n1. [GOV](gov.md)\n`,
      capabilityIntegrationsMarkdown: `## Purpose\n\n- Track integration items.\n\n## Current Items\n\n1. [INT](int.md)\n`,
      capabilitySuggestionsMarkdown: `## Purpose\n\n- Track suggestion items.\n\n## Current Pending Suggestions\n\n1. [SUG](sug.md)\n`,
      compatibilityWindowStatusMarkdown:
        `# Compatibility Window Status\n\n- \`window_start_date\`: 2026-03-02\n- \`required_approved_cycles\`: 2\n- \`approved_cycles_completed\`: 1\n- \`current_slot\`: 1_of_2\n- \`legacy_pointers_enabled\`: true\n- \`legacy_fallbacks_enabled\`: true\n- \`cycle_028_ready\`: false\n- \`blocking_issues\`: branch_hygiene_main_dirty\n`,
    });

    expect(help.flows).toHaveLength(5);
    expect(help.flows[0]?.flow_id).toBe("phase_execution_loop");
    const updateLoop = help.flows.find((flow) => flow.flow_id === "update_cycle_loop");
    const upgradeLoop = help.flows.find((flow) => flow.flow_id === "upgrade_cycle_loop");
    expect(updateLoop?.steps.length).toBeGreaterThan(0);
    expect(updateLoop?.human_gates.length).toBeGreaterThan(0);
    expect(upgradeLoop?.steps.length).toBeGreaterThan(0);
    expect(upgradeLoop?.human_gates.length).toBeGreaterThan(0);
    expect(help.skills).toHaveLength(6);
    expect(help.skills[0]?.current_items[0]?.path).toBe("docs/exec_plans/updates/active/upd.md");
    expect(help.conventions.length).toBeGreaterThan(0);
    expect(help.guidelines.length).toBeGreaterThan(0);
    expect(help.proposal.path).toContain("dev_tracker_ui_reorganization_update_plan_2026-02-24.md");
    expect(help.compatibility_window?.current_slot).toBe("1_of_2");
  });

  it("parses changelog and current-state tables", () => {
    const changelog = parseChangelog(
      `## Changelog Table\n\n| entry_id | date | cycle_id | phase_stage | change_type | summary | docs_updated | human_gate_decision | approval_ref | approval_status |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| CHG-1 | 2026-02-24 | cycle_001 | p0-s00 | governance | update | docs.md | continue | gate-1 | approved |\n`,
    );
    expect(changelog.entry_count).toBe(1);
    expect(changelog.approved_count).toBe(1);

    const features = parseCurrentFeatures(
      `## Feature Table\n\n| feature_id | capability | status | source_phase_stage | owner | evidence_link | last_updated |\n| --- | --- | --- | --- | --- | --- | --- |\n| FEAT-1 | contracts | implemented | p1-s03 | team | link | 2026-02-24 |\n`,
    );
    expect(features.implemented_count).toBe(1);

    const guidance = parseCurrentGuidance(
      `## Guidance Table\n\n| guidance_id | rule | enforcement_anchor | operator_action | status |\n| --- | --- | --- | --- | --- |\n| GUIDE-1 | do x | anchor | action | active |\n`,
    );
    expect(guidance.active_count).toBe(1);

    const processes = parseLoopProcesses(
      `## Process Table\n\n| process_id | process_type | trigger | steps_summary | required_artifacts | human_gate | next_cycle_rule |\n| --- | --- | --- | --- | --- | --- | --- |\n| PROC-1 | implementation | trigger | steps | artifacts | required | blocked |\n`,
    );
    expect(processes.row_count).toBe(1);
    expect(processes.rows[0]?.process_id).toBe("PROC-1");

    const gateStats = parseHumanGateStats(
      `## Human Gate Stats Table\n\n| gate_id | date | cycle_id | loop_id | cycles_completed | estimated_cycles_remaining | estimated_loops_remaining | stages_remaining | pending_approvals | pending_features | open_capability_gaps | open_harness_upgrades | completion_percent | next_cycle_type | reviewer_action_required | notes |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| HGS-1 | 2026-02-24 | cycle_001 | loop-main | 1 | 9 | 2 | 12 | 1 | 4 | 0 | 0 | 0.25 | implementation | approve_or_pause | pending review |\n`,
    );
    expect(gateStats.row_count).toBe(1);
    expect(gateStats.latest.estimated_cycles_remaining).toBe(9);

    const archiveRegister = parseArchiveRegister(
      `## Archive Register Table\n\n| archive_id | archived_on | record_type | source_cycle | title | status | archive_path | upgrade_review | notes |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| ARC-001 | 2026-02-24 | suggestion | cycle_010 | migrated legacy suggestions | archived | docs/exec_plans/implementation/completed/sug_2026_001_terms_and_state_legibility.md | n/a | converted |\n`,
    );
    expect(archiveRegister.row_count).toBe(1);
    expect(archiveRegister.suggestion_count).toBe(1);
  });

  it("evaluates documentation review status signal transitions", () => {
    const passSignal = evaluateDocumentationReviewStatus(
      `# Documentation Review Status\n\n- \`review_loop_enabled\`: true\n- \`cadence\`: every_3_cycles\n- \`blocking_mode\`: risk_based\n- \`last_review_cycle\`: cycle_026\n- \`next_review_due_cycle\`: cycle_029\n`,
    );
    expect(passSignal.status).toBe("pass");

    const warnSignal = evaluateDocumentationReviewStatus(
      `# Documentation Review Status\n\n- \`review_loop_enabled\`: true\n- \`blocking_mode\`: risk_based\n`,
    );
    expect(warnSignal.status).toBe("warn");

    const failSignal = evaluateDocumentationReviewStatus(
      `# Documentation Review Status\n\n- \`review_loop_enabled\`: false\n- \`cadence\`: every_3_cycles\n- \`blocking_mode\`: risk_based\n- \`last_review_cycle\`: cycle_026\n- \`next_review_due_cycle\`: cycle_029\n`,
    );
    expect(failSignal.status).toBe("fail");
  });

  it("parses compatibility window status", () => {
    const parsed = parseCompatibilityWindowStatus(
      `# Compatibility Window Status\n\n- \`window_start_date\`: 2026-03-02\n- \`required_approved_cycles\`: 2\n- \`approved_cycles_completed\`: 1\n- \`current_slot\`: 1_of_2\n- \`legacy_pointers_enabled\`: true\n- \`legacy_fallbacks_enabled\`: true\n- \`cycle_028_ready\`: false\n- \`blocking_issues\`: none\n`,
    );

    expect(parsed?.required_approved_cycles).toBe(2);
    expect(parsed?.approved_cycles_completed).toBe(1);
    expect(parsed?.legacy_pointers_enabled).toBe(true);
    expect(parsed?.blocking_issues).toEqual(["none"]);
  });
});
