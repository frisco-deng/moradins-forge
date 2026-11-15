/* @vitest-environment node */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import crypto from "node:crypto";
import vm from "node:vm";
import ts from "typescript";
import { deterministicSynthesis, normalizeSynthesis, buildDeterministicPhasePlan, buildFollowOnPrompts } from "../scripts/product-planning.mjs";

const cases = [
  { id: "cli", intake: { project_goal: "Operators convert local CSV files to audited reports", users: "operators", deployment_target: "local CLI", constraints: "offline only", other_context: "Baseline: valid CSV produces one report; defer bulk scheduling" }, answers: {} },
  { id: "web", intake: { project_goal: "Customers submit orders and receive confirmation", users: "customers", deployment_target: "existing web app", constraints: "retain existing authentication", integrations: "Order API v1", other_context: "Baseline acceptance: confirmation follows a valid order" }, answers: { acceptance: "retain historical orders" } },
  { id: "existing", intake: { project_goal: "Extend an existing document review flow", users: "reviewers", constraints: "preserve current SQLite data", integrations: "Existing review component", deployment_target: "existing monolith" }, answers: { baseline: "review and approve one document" }, project_scan_summary: { languages: ["Python"], ci_surfaces: ["existing GitHub workflow"], critical_gaps: ["optional scanner unavailable"] } },
  { id: "incomplete", intake: {}, answers: { unrelated1: "blue", unrelated2: "tomorrow", unrelated3: "small" } },
  { id: "dependency-change", intake: { project_goal: "Export approved inventory", users: "operators", integrations: "Inventory API v2", constraints: "preserve independent local export", other_context: "API v2 replaces v1; inspect the remote consumer contract" }, answers: {} },
  { id: "agent-label", intake: { project_goal: "Assistant CLI formats a local text file", users: "developers", deployment_target: "single local process", constraints: "no new model provider or orchestration" }, answers: {} },
];
cases.push({ id: "redundant-inline-facts", intake: { project_goal: "Export one approved report", constraints: "Retain offline operation and the existing data ownership contract; preserve every accepted deferred capacity and recovery obligation without introducing external services.", other_context: "Baseline accepted report; later accepted bulk export remains unfinished" }, answers: {}, alignment_fixture: { summary: { overall_status: "partial", manual_required_count: 1, missing_count: 2 }, next_recommended_phase_id: "phase_1", next_recommended_action: { next_action: "verify producer consumer boundary", route: "native validation" } } });
const options = (session) => ({ session, targetRepo: "fixture-product", workflowType: session.id === "existing" ? "existing_project" : "new_project" });
function run(api, input) {
  const session = structuredClone(input);
  session.session_id = `fixture-${input.id}`;
  session.artifacts = {};
  session.synthesis = api.deterministicSynthesis(session);
  session.synthesis.must_haves.push("Later accepted outcome: measured batch capacity; deferred remains unfinished");
  const phasePlan = api.buildDeterministicPhasePlan(options(session));
  const prompts = api.buildFollowOnPrompts({ ...options(session), selectedProfile: session.synthesis.recommended_profile, phasePlan, alignmentState: session.alignment_fixture || null });
  return { synthesis: session.synthesis, phasePlan, prompts };
}
const candidate = { deterministicSynthesis, buildDeterministicPhasePlan, buildFollowOnPrompts };
function grade(input, result) {
  const encoded = JSON.stringify(result);
  return {
    supplied_goal: result.synthesis.product_spec.intent === (input.intake.project_goal || ""),
    supplied_constraints: !input.intake.constraints || encoded.includes(input.intake.constraints),
    no_invented_architecture: !result.synthesis.design.components.some((c) => ["Project-facing API/service boundary", "Persistence and observability surface"].includes(c)),
    product_first_phase: result.phasePlan.phases[0].objective.includes("normal-path journey"),
    broader_scope_retained: JSON.stringify(result.phasePlan).includes("Later accepted outcome: measured batch capacity; deferred remains unfinished"),
    no_answer_count_gate: !result.synthesis.open_questions.some((q) => q.includes("Insufficient discovery answers")),
    no_extra_phase_confirmations: !result.prompts.some((p) => p.prompt.includes("Preserve human confirmation at phase boundaries")),
    declared_dependency_in_plan: !input.intake.integrations || JSON.stringify(result.phasePlan).includes(input.intake.integrations),
  };
}

describe("product-aware planning", () => {
  it("keeps whole-product scope in a standalone execution prompt when plan files are absent", () => {
    const result = run(candidate, cases[0]);
    const prompt = result.prompts.find((p) => p.prompt_id === "run_all_phases").prompt;
    expect(prompt).toContain("Later accepted outcome: measured batch capacity; deferred remains unfinished");
    expect(prompt).toContain("offline only");
    expect(prompt).toContain("when available");
    expect(prompt).toContain("recover missing acceptance before claiming completion");
  });

  for (const input of cases) {
    it(`${input.id}: preserves supplied product facts and avoids unrequested architecture`, () => {
      const result = run(candidate, input);
      expect(Object.values(grade(input, result)).every(Boolean)).toBe(true);
      expect(result.phasePlan.phases.map((p) => p.phase_id)).toEqual(["phase_1", "phase_2", "phase_3"]);
      expect(result.prompts.map((p) => p.prompt_id)).toEqual(["bootstrap_hydration", "phase_planning", "phase_1_execution", "run_all_phases"]);
      expect(result.prompts.find((p) => p.prompt_id === "run_all_phases").prompt).toContain("existing discovery/adoption");
    });
  }
  it("does not ask generic questions when intake already supplies the next-slice facts", () => {
    expect(deterministicSynthesis(cases[0]).open_questions).toEqual([]);
    expect(deterministicSynthesis(cases[1]).open_questions).toEqual([]);
  });
  it("names missing facts even when three irrelevant answers exist", () => {
    const result = deterministicSynthesis(cases[3]);
    expect(result.product_spec.intent).toBe("");
    expect(result.product_spec.target_users).toEqual([]);
    expect(result.product_spec.constraints).toEqual([]);
    expect(result.open_questions.some((q) => q.startsWith("Product outcome unknown"))).toBe(true);
    expect(result.open_questions.some((q) => q.startsWith("Intended users unknown"))).toBe(true);
  });
  it("changes affected dependency evidence while preserving independent constraints", () => {
    const latest = run(candidate, cases[4]);
    const prior = run(candidate, { ...cases[4], intake: { ...cases[4].intake, integrations: "Inventory API v1" } });
    expect(latest.synthesis.product_spec.constraints).toEqual(prior.synthesis.product_spec.constraints);
    expect(JSON.stringify(latest.phasePlan)).toContain("Inventory API v2");
    expect(JSON.stringify(latest.phasePlan)).not.toContain("Inventory API v1");
    expect(JSON.stringify(latest)).toContain("preserve independent local export");
  });
  it("deduplicates only facts present in the same standalone prompt", () => {
    const input = cases.find((c) => c.id === "redundant-inline-facts");
    const result = run(candidate, input);
    for (const prompt of result.prompts) expect(prompt.prompt).toContain(input.intake.constraints);
    const execution = result.prompts.find((p) => p.prompt_id === "run_all_phases").prompt;
    expect(execution).toContain("Later accepted outcome: measured batch capacity; deferred remains unfinished");
    expect(execution).toContain("alignment_next_phase_id=phase_1");
    expect(execution.split("alignment_overall=partial")).toHaveLength(2);
    expect(execution).not.toContain("- overall_status:");
    expect(result.prompts.map((p) => p.prompt_id)).toEqual(["bootstrap_hydration", "phase_planning", "phase_1_execution", "run_all_phases"]);
  });
  it("normalizes legacy synthesis without a new schema or fabricated facts", () => {
    const legacy = { summary: "old", product_spec: { intent: "Existing outcome", constraints: ["retain data"] }, design: { components: ["Existing module"] } };
    const result = normalizeSynthesis(legacy);
    expect(Object.keys(result)).toEqual(["summary", "recommended_profile", "must_haves", "open_questions", "product_spec", "design", "plan"]);
    expect(result.design.components).toEqual(["Existing module"]);
    expect(result.product_spec.constraints).toEqual(["retain data"]);
    expect(result.product_spec.target_users).toEqual([]);
  });
});

if (process.env.PRODUCT_PLAN_BASELINE_SOURCE || process.env.PRODUCT_PLAN_BASELINE_MODULE) {
  it("replays frozen prior and candidate implementations on the same declared cases", () => {
    const raw = fs.readFileSync(process.env.PRODUCT_PLAN_BASELINE_MODULE || process.env.PRODUCT_PLAN_BASELINE_SOURCE, "utf8");
    const context = vm.createContext({});
    if (process.env.PRODUCT_PLAN_BASELINE_MODULE) {
      vm.runInContext(raw.replace(/^export /gm, "") + ";this.api={deterministicSynthesis,buildDeterministicPhasePlan,buildFollowOnPrompts};", context, { timeout: 1000 });
    } else {
      const ast = ts.createSourceFile("baseline.mjs", raw, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
      const names = ["deterministicSynthesis", "recommendProfile", "normalizeSynthesis", "buildDeterministicPhasePlan", "buildPromptContextSummary", "buildFollowOnPrompts", "splitCsv", "normalizeStringArray"];
      const declarations = ast.statements.filter((n) => ts.isFunctionDeclaration(n) && names.includes(n.name?.text));
      expect(declarations).toHaveLength(names.length);
      vm.runInContext(declarations.map((n) => n.getText(ast)).join("\n") + ";this.api={deterministicSynthesis,buildDeterministicPhasePlan,buildFollowOnPrompts};", context, { timeout: 1000 });
    }
    const rows = cases.map((input) => {
      const prior = run(context.api, input), current = run(candidate, input);
      const before = grade(input, prior), after = grade(input, current);
      return { id: input.id, before, after, improvements: Object.keys(before).filter((k) => !before[k] && after[k]), regressions: Object.keys(before).filter((k) => before[k] && !after[k]), unchanged: Object.keys(before).filter((k) => before[k] === after[k]), selected_prompt_bytes: current.prompts.map((p, i) => ({ prompt_id: p.prompt_id, prior: Buffer.byteLength(prior.prompts[i].prompt), current: Buffer.byteLength(p.prompt) })), output_bytes: { prior: Buffer.byteLength(JSON.stringify(prior)), current: Buffer.byteLength(JSON.stringify(current)) } };
    });
    expect(rows.every((r) => !r.regressions.length)).toBe(true);
    const report = { schema_version: "product-planning-replay-v1", baseline_source_sha256: crypto.createHash("sha256").update(raw).digest("hex"), candidate_source_sha256: crypto.createHash("sha256").update(fs.readFileSync(new URL("../scripts/product-planning.mjs", import.meta.url))).digest("hex"), cases: rows, dimensions: ["product framing", "architecture assumptions", "integrated baseline", "scope retention", "authority boundaries"], limit: "Synthetic deterministic tool replay; not model comprehension, policy causality or task-cost efficiency" };
    fs.writeFileSync(process.env.PRODUCT_PLAN_REPLAY_REPORT, JSON.stringify(report, null, 2) + "\n");
  });
}
