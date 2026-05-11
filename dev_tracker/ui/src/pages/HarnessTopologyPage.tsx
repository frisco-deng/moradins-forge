import { Link } from "react-router-dom";

import { PageHero } from "../components/PageHero";
import { RoutingSurfacesCard } from "../components/RoutingSurfacesCard";
import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import { TooltipHint } from "../components/TooltipHint";
import type { CardExpandItem } from "../components/ui";
import { CardExpandGrid } from "../components/ui";
import { useTracker } from "../lib/tracker-context";

interface PipelineBranch {
  id: string;
  domain: string;
  trigger: string;
  policyDoc: string;
  checklistDoc: string;
}

export function HarnessTopologyPage() {
  const { snapshot, settings } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No harness topology data available.</div>;
  }
  const docs = snapshot.docs;

  const defaultContextDocs = [
    "AGENTS.md",
    "docs/engineer_entry/index.md",
    "docs/00_overview/engineer_entrypoint.md",
    "docs/11_ops/codex_run_loop.md",
    "docs/11_ops/git_workflow_gitlab.md",
    "docs/11_ops/tooling_pipeline.md",
    "docs/15_checklists/agent_cycle_gate.md",
  ];

  const policyBranches: PipelineBranch[] = [
    {
      id: "security",
      domain: "Security",
      trigger: "security, pii, auth, threat, compliance",
      policyDoc: "docs/11_ops/agent_harness_governance.md",
      checklistDoc: "docs/15_checklists/security_review.md",
    },
    {
      id: "infra",
      domain: "Infra / Ops",
      trigger: "deploy, runtime, tooling, harness, branching",
      policyDoc: "docs/11_ops/index.md",
      checklistDoc: "docs/15_checklists/change_control.md",
    },
    {
      id: "retrieval",
      domain: "Retrieval",
      trigger: "query, ranking, grounding, citation, policy filter",
      policyDoc: "docs/02_contracts/index.md",
      checklistDoc: "docs/15_checklists/retrieval_change.md",
    },
    {
      id: "ingestion",
      domain: "Ingestion",
      trigger: "connector, parser, chunking, enrichment, index write",
      policyDoc: "docs/00_overview/service_catalog.md",
      checklistDoc: "docs/15_checklists/pipeline_change.md",
    },
    {
      id: "contracts",
      domain: "Contracts",
      trigger: "schema, api, message catalog, compatibility",
      policyDoc: "docs/02_contracts/index.md",
      checklistDoc: "docs/15_checklists/contract_change.md",
    },
    {
      id: "observability",
      domain: "Observability / Eval",
      trigger: "metrics, alerts, evaluation, thresholds, incidents",
      policyDoc: "docs/11_ops/tooling_pipeline.md",
      checklistDoc: "docs/15_checklists/incident_checklist.md",
    },
    {
      id: "architecture",
      domain: "Architecture",
      trigger: "boundaries, topology, service ownership, adrs",
      policyDoc: "docs/03_architecture/index.md",
      checklistDoc: "docs/15_checklists/service_addition.md",
    },
  ];

  const commandGates = [
    "make branch-hygiene",
    "make lint-md",
    "npm --prefix dev_tracker/ui run check:engineer-entry",
    "make lint",
  ];

  const harnessFlowItems: CardExpandItem[] = [
    {
      id: "intake",
      title: "Phase Project Request",
      subtitle: "01 Intake",
      description: "Objective, phase/stage target, acceptance checks, and stop conditions are parsed first.",
    },
    {
      id: "context-load",
      title: "Default Inputs",
      subtitle: "02 Context Load",
      description: "Engineer-entry constraints, architecture defaults, and harness runbooks are loaded before implementation.",
    },
    {
      id: "deterministic-gates",
      title: "Rule + Tool Enforcement",
      subtitle: "03 Deterministic Gates",
      description: "Deterministic branch/lint/guard gates run before any cycle may continue.",
    },
    {
      id: "policy-branch",
      title: "Domain Routing",
      subtitle: "04 Policy Branch",
      description: "Request keywords map to policy docs and checklist gates before execution.",
    },
    {
      id: "cycle-controls",
      title: "Human Gate + Artifacts",
      subtitle: "05 Cycle Controls",
      description: "Cycle-close artifacts and explicit human continue/pause/stop decision govern progression.",
    },
  ];

  const harnessFlowDetails: Record<
    string,
    {
      inputs: string[];
      checks: string[];
      routing: string[];
      outputs: string[];
      docs: string[];
    }
  > = {
    intake: {
      inputs: [
        "Engineer prompt with objective, phase/stage, and acceptance checks",
        "Scope boundaries and out-of-scope constraints",
        "Human gate expectation",
      ],
      checks: ["Map to phase_id/stage_id/cycle_id", "Validate stop conditions and gate requirements"],
      routing: ["Route request into harness topology pipeline", "Enforce one approved cycle per execution pass"],
      outputs: ["Bounded cycle objective", "Initial routing context"],
      docs: ["AGENTS.md", "docs/00_overview/engineer_entrypoint.md", "docs/entrypoint_guide/how_to_direct.md"],
    },
    "context-load": {
      inputs: defaultContextDocs,
      checks: ["Ensure required context docs are present in snapshot", "Load engineer-entry context without write access"],
      routing: ["Hydrate planner/implementer context", "Attach contracts, architecture, and checklist anchors"],
      outputs: ["Context bundle for deterministic execution", "Doc links for route-aware navigation"],
      docs: defaultContextDocs,
    },
    "deterministic-gates": {
      inputs: commandGates,
      checks: ["Branch hygiene must pass", "Engineer-entry guard must pass", "Lint/compatibility gates must pass"],
      routing: ["Fail-fast on guardrail violations", "Block continuation on failed enforcement"],
      outputs: ["Pass/fail enforcement evidence", "QA signals consumed by tracker"],
      docs: ["docs/11_ops/tooling_pipeline.md", "docs/11_ops/codex_run_loop.md", "docs/15_checklists/agent_cycle_gate.md"],
    },
    "policy-branch": {
      inputs: policyBranches.map((branch) => `${branch.domain}: ${branch.trigger}`),
      checks: ["Match domain triggers", "Resolve policy source + checklist gate"],
      routing: ["Apply domain checklist before implementation", "Prevent cross-domain boundary drift"],
      outputs: ["Domain-scoped policy path", "Checklist gate linkage"],
      docs: ["docs/11_ops/agent_harness_governance.md", "docs/03_architecture/service_boundaries.md", "docs/00_overview/service_catalog.md"],
    },
    "cycle-controls": {
      inputs: [
        "Changelog + current-features + current-guidance rows",
        "Human gate stats + archive register updates",
        "Harness upgrade backlog routing",
      ],
      checks: ["Require approval fields before cycle N+1", "Require artifact updates for cycle closeout"],
      routing: ["Human decision: continue/pause/stop", "Upgrade routing: upgrade_next_cycle/defer_with_risk/reject"],
      outputs: ["Auditable cycle state", "Observable loop progression and remaining estimates"],
      docs: [
        "docs/11_ops/codex_run_loop.md",
        "Harness/artifacts/control/changelog.md",
        "Harness/artifacts/control/human_gate_stats.md",
        "docs/exec_plans/tech-debt-tracker.md",
      ],
    },
  };

  function docLink(path: string) {
    return docs.find((entry) => entry.relative_path === path);
  }
  const sortedPolicyBranches = [...policyBranches].sort((a, b) => a.domain.localeCompare(b.domain));
  const policyBranchContract = sortedPolicyBranches.map((branch) => {
    const policyDoc = docLink(branch.policyDoc);
    const checklistDoc = docLink(branch.checklistDoc);
    return {
      ...branch,
      policyDocRecord: policyDoc,
      checklistDocRecord: checklistDoc,
      valid: Boolean(policyDoc && checklistDoc),
    };
  });
  const harnessProcessLoopItems: CardExpandItem[] = snapshot.harness_help.flows.map((flow, index) => ({
    id: flow.flow_id,
    title: flow.title,
    subtitle: `Loop ${String(index + 1).padStart(2, "0")}`,
    description: flow.trigger,
  }));

  return (
    <div className="page-grid">
      <PageHero
        title="Harness Topology"
        subtitle="Harness observability for loop controls, gates, artifacts, approvals, and policy routing behavior."
        eyebrow="Execution Routing"
        chips={
          <>
            <StatusChip tone="info">{`${harnessFlowItems.length} routing stages`}</StatusChip>
            <StatusChip tone="success">{`${snapshot.harness_help.flows.length} loop contracts`}</StatusChip>
            <StatusChip tone="warning">{`${policyBranchContract.filter((branch) => !branch.valid).length} policy link gaps`}</StatusChip>
          </>
        }
        actions={
          <>
            <Link to="/deploy/quick-start" className="btn" style={{ textDecoration: "none" }}>
              Quick Start
            </Link>
            <Link to="/deploy/map" className="btn" style={{ textDecoration: "none" }}>
              Deploy Map
            </Link>
          </>
        }
      >
        <div className="card card-pad page-hero-inline-card" style={{ padding: "0.8rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <strong>Routing model</strong>
            <TooltipHint text="Topology-level view of routing, policy branching, and deterministic gate controls." />
          </div>
          <p className="metric-sub" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
            Use the pipeline cards for fast flow understanding, then expand the loop and policy sections for deeper routing detail.
          </p>
        </div>
      </PageHero>

      <RoutingSurfacesCard
        links={[
          { to: "/help", label: "Help: Quick Orientation" },
          { to: "/cycles", label: "Loop Processes: Gate State" },
          { to: "/reviews/exchange", label: "Activity: Approval Routing" },
          { to: "/project-topology", label: "Project Topology" },
        ]}
        subtitle="Use these shared surfaces to inspect routing state, approvals, and governance handoffs."
      />

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Harness Routing Pipeline</h3>
        <p className="section-subtitle">
          Default harness flow for phase-project requests: context load, deterministic gates, policy branching, and cycle controls.
        </p>
        <CardExpandGrid
          items={harnessFlowItems}
          columns={{ base: 1, sm: 2, md: 3, lg: 5 }}
          reducedMotion={settings.reducedMotion}
          uniformCardHeights
          renderCard={(item) => (
            <>
              <p className="card-head">{item.subtitle}</p>
              <h4>{item.title}</h4>
              <p className="muted">{item.description}</p>
            </>
          )}
          renderExpanded={(item) => {
            const detail = harnessFlowDetails[item.id];
            if (!detail) {
              return null;
            }

            return (
              <div className="harness-expanded-body">
                <h4 style={{ margin: 0 }}>{item.title}</h4>
                <p className="muted" style={{ margin: "0.35rem 0 0.7rem" }}>
                  {item.description}
                </p>
                <div className="harness-expanded-grid">
                  <section>
                    <p className="card-head">Inputs</p>
                    <ul>
                      {detail.inputs.map((value) => (
                        <li key={`${item.id}-input-${value}`}>{value}</li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Deterministic Checks</p>
                    <ul>
                      {detail.checks.map((value) => (
                        <li key={`${item.id}-checks-${value}`}>{value}</li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Routing</p>
                    <ul>
                      {detail.routing.map((value) => (
                        <li key={`${item.id}-routing-${value}`}>{value}</li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Outputs</p>
                    <ul>
                      {detail.outputs.map((value) => (
                        <li key={`${item.id}-outputs-${value}`}>{value}</li>
                      ))}
                    </ul>
                  </section>
                </div>
                <div className="harness-expanded-links">
                  {detail.docs.map((path) => {
                    const doc = docLink(path);
                    if (!doc) {
                      return (
                        <span key={`${item.id}-doc-${path}`} className="mono">
                          {path}
                        </span>
                      );
                    }
                    return (
                      <Link
                        key={`${item.id}-doc-${path}`}
                        to={`/docs/${doc.id}`}
                        className="mono"
                        style={{ color: "var(--cyan)", textDecoration: "none" }}
                      >
                        {path}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          }}
        />
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Harness Process Loops</h3>
        <p className="section-subtitle">
          Canonical loop contracts with triggers, ordered steps, required artifacts, human gates, and source references.
        </p>
        <CardExpandGrid
          items={harnessProcessLoopItems}
          columns={{ base: 1, sm: 2, md: 2, lg: 3 }}
          reducedMotion={settings.reducedMotion}
          renderCard={(item) => (
            <>
              <p className="card-head">{item.subtitle}</p>
              <h4>{item.title}</h4>
              <p className="muted">{item.description}</p>
            </>
          )}
          renderExpanded={(item) => {
            const flow = snapshot.harness_help.flows.find((entry) => entry.flow_id === item.id);
            if (!flow) {
              return null;
            }

            return (
              <div className="harness-expanded-body">
                <h4 style={{ margin: 0 }}>{flow.title}</h4>
                <p className="muted" style={{ margin: "0.35rem 0 0.7rem" }}>
                  Trigger: {flow.trigger}
                </p>
                <div className="harness-expanded-grid">
                  <section>
                    <p className="card-head">Flow Steps</p>
                    <ol style={{ margin: "0.55rem 0 0", paddingLeft: "1.05rem" }}>
                      {flow.steps.map((step) => (
                        <li key={`${flow.flow_id}-step-${step}`}>{step}</li>
                      ))}
                    </ol>
                  </section>
                  <section>
                    <p className="card-head">Required Artifacts</p>
                    <ul>
                      {flow.required_artifacts.map((artifact) => (
                        <li key={`${flow.flow_id}-artifact-${artifact}`}>{artifact}</li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Human Gates</p>
                    <ul>
                      {flow.human_gates.map((gate) => (
                        <li key={`${flow.flow_id}-gate-${gate}`}>{gate}</li>
                      ))}
                    </ul>
                  </section>
                </div>
                <div className="harness-expanded-links">
                  {flow.source_docs.map((path) => {
                    const doc = docLink(path);
                    if (!doc) {
                      return (
                        <span key={`${flow.flow_id}-source-${path}`} className="mono">
                          {path}
                        </span>
                      );
                    }
                    return (
                      <Link
                        key={`${flow.flow_id}-source-${path}`}
                        to={`/docs/${doc.id}`}
                        className="mono"
                        style={{ color: "var(--cyan)", textDecoration: "none" }}
                      >
                        {path}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          }}
        />
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Policy Branch Matrix</h3>
        <ScrollSurface className="effects-table-wrap">
          <table className="table effects-table">
            <thead>
              <tr>
                <th>Project Domain</th>
                <th>Typical Trigger Keywords</th>
                <th>Policy Source</th>
                <th>Checklist Gate</th>
                <th>Contract Status</th>
              </tr>
            </thead>
            <tbody>
              {policyBranchContract.map((branch) => {
                return (
                  <tr key={branch.id}>
                    <td>{branch.domain}</td>
                    <td>{branch.trigger}</td>
                    <td className="mono">
                      {branch.policyDocRecord ? (
                        <Link to={`/docs/${branch.policyDocRecord.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                          {branch.policyDoc}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="mono">
                      {branch.checklistDocRecord ? (
                        <Link to={`/docs/${branch.checklistDocRecord.id}`} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                          {branch.checklistDoc}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <StatusChip tone={branch.valid ? "success" : "warning"}>{branch.valid ? "valid" : "missing"}</StatusChip>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Deterministic Gate Controls</h3>
        <p className="section-subtitle">Required gate commands that enforce harness routing readiness and approval safety.</p>
        <ul style={{ margin: "0.65rem 0 0", paddingLeft: "1rem" }}>
          {commandGates.map((command) => (
            <li key={command} className="mono">
              {command}
            </li>
          ))}
        </ul>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
          {["docs/11_ops/tooling_pipeline.md", "docs/11_ops/codex_run_loop.md", "docs/15_checklists/agent_cycle_gate.md"].map((path) => {
            const doc = docs.find((entry) => entry.relative_path === path);
            if (!doc) {
              return null;
            }
            return (
              <Link key={path} to={`/docs/${doc.id}`} className="btn" style={{ textDecoration: "none" }}>
                {doc.title}
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
