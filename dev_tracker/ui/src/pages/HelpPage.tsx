import { Link } from "react-router-dom";

import { RoutingSurfacesCard } from "../components/RoutingSurfacesCard";
import { TooltipHint } from "../components/TooltipHint";
import type { CardExpandItem } from "../components/ui";
import { CardExpandGrid } from "../components/ui";
import { ROUTE_CONTEXT_INVENTORY } from "../lib/route-context";
import { useTracker } from "../lib/tracker-context";

function isExternalLink(path: string) {
  return path.startsWith("http://") || path.startsWith("https://");
}

interface ExampleFlowDetail {
  abstractions: string[];
  routes: Array<{ to: string; label: string }>;
  artifacts: string[];
  humanGate: string;
}

interface QuickLoopDetail {
  goal: string;
  sequence: string[];
  humanGate: string;
}

export function HelpPage() {
  const { snapshot, settings } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No help data available. Run sync and refresh.</div>;
  }

  const resolveDoc = (relativePath: string) => snapshot.docs.find((doc) => doc.relative_path === relativePath);
  const visualReferenceDoc = resolveDoc("docs/design_docs/project_builder_visual_reference.md");

  const renderDocLink = (relativePath: string, label?: string) => {
    if (isExternalLink(relativePath)) {
      return (
        <a href={relativePath} className="mono" style={{ color: "var(--cyan)", textDecoration: "none" }}>
          {label ?? relativePath}
        </a>
      );
    }

    const doc = resolveDoc(relativePath);
    if (!doc) {
      return <span className="mono">{label ?? relativePath}</span>;
    }

    return (
      <Link to={`/docs/${doc.id}`} className="mono" style={{ color: "var(--cyan)", textDecoration: "none" }}>
        {label ?? relativePath}
      </Link>
    );
  };

  const exampleFlowItems: CardExpandItem[] = [
    {
      id: "deploy-builder",
      title: "Deploy Builder",
      subtitle: "Step 01",
      description: "Create/import repo destination and verify deterministic safety controls.",
    },
    {
      id: "project-discovery",
      title: "Project Discovery",
      subtitle: "Step 02",
      description: "Capture intent, constraints, and answers for synthesis-backed setup.",
    },
    {
      id: "plan-phases",
      title: "Plan Phases",
      subtitle: "Step 03",
      description: "Convert discovery outcomes into phase/stage objectives and acceptance checks.",
    },
    {
      id: "execute-initial",
      title: "Execute Initial Phases",
      subtitle: "Step 04",
      description: "Run approved work in deterministic cycles and track cycle-close artifacts.",
    },
    {
      id: "update-policies",
      title: "Update Policies",
      subtitle: "Step 05",
      description: "Refresh policy surfaces when architecture, security, or ops behavior changes.",
    },
    {
      id: "upgrade-project",
      title: "Upgrade Project",
      subtitle: "Step 06",
      description: "Route post-gate upgrade candidates and commission approved items.",
    },
    {
      id: "add-tooling",
      title: "Add Tooling",
      subtitle: "Step 07",
      description: "Expand deterministic checks and QA signal coverage for reliability.",
    },
    {
      id: "execute-remaining",
      title: "Execute Remaining Phases",
      subtitle: "Step 08",
      description: "Continue looped implementation with human gates between cycle transitions.",
    },
    {
      id: "productize",
      title: "Productize and Deploy",
      subtitle: "Step 09",
      description: "Finalize operational endpoints, release posture, and deployment readiness.",
    },
    {
      id: "document",
      title: "Document",
      subtitle: "Step 10",
      description: "Close cycle with changelog, guidance, review, and archive traceability.",
    },
  ];

  const exampleFlowDetails: Record<string, ExampleFlowDetail> = {
    "deploy-builder": {
      abstractions: [
        "Destination safety contract and overwrite controls",
        "Discovery provider availability and local-first defaults",
      ],
      routes: [
        { to: "/reviews/exchange", label: "Activity" },
        { to: "/builder", label: "Deploy Builder" },
        { to: "/project-status", label: "Project Status" },
        { to: "/system-status", label: "System Status" },
      ],
      artifacts: ["builder_operation_audit.md", "discovery_sessions/<session_id>/", ".moradins-harness/"],
      humanGate: "Human approval remains required before sidecar deploy execution into established projects.",
    },
    "project-discovery": {
      abstractions: ["Intake contract", "Question generation", "Synthesis + prompt bundle traceability"],
      routes: [
        { to: "/builder", label: "Deploy Builder" },
        { to: "/review", label: "Review Hub" },
      ],
      artifacts: ["prompt_bundle.json", "prompt_bundle.md", "approval_required.md"],
      humanGate: "Approval artifact must be complete before generation and execution flows.",
    },
    "plan-phases": {
      abstractions: ["Phase/stage boundaries", "Acceptance criteria", "Out-of-scope controls"],
      routes: [
        { to: "/phases", label: "Phases" },
        { to: "/project-topology", label: "Project Topology" },
      ],
      artifacts: ["implementation_phases.md", "engineer_entrypoint.md"],
      humanGate: "Uncertain scope requires explicit human direction before phase commitment.",
    },
    "execute-initial": {
      abstractions: ["One approved cycle per execution pass", "Deterministic quality gates"],
      routes: [
        { to: "/cycles", label: "Loop Processes" },
        { to: "/reviews/exchange", label: "Activity" },
      ],
      artifacts: ["changelog.md", "human_gate_stats.md", "current_features.md"],
      humanGate: "Cycle N+1 blocked until cycle N approval status is approved.",
    },
    "update-policies": {
      abstractions: ["Domain-routing contract", "Policy metadata health", "Checklist gates"],
      routes: [
        { to: "/policies", label: "Policies" },
        { to: "/harness-topology", label: "Harness Topology" },
      ],
      artifacts: ["policy docs + checklists", "route context coverage rows"],
      humanGate: "Policy changes require reviewer sign-off when governance or security semantics shift.",
    },
    "upgrade-project": {
      abstractions: ["Upgrade routing decisions", "Backlog triage", "Risk-based deferral"],
      routes: [
        { to: "/reviews/exchange", label: "Activity" },
        { to: "/review", label: "Review Hub" },
      ],
      artifacts: ["tech-debt-tracker.md", "upgrade review artifacts", "archive_register.md"],
      humanGate: "Each candidate is routed as upgrade_next_cycle, defer_with_risk, or reject.",
    },
    "add-tooling": {
      abstractions: ["Tool-first enforcement", "QA signal generation", "Branch hygiene + entry guards"],
      routes: [
        { to: "/system-status", label: "System Status" },
        { to: "/changes", label: "Changes" },
      ],
      artifacts: ["qa_signals_v1.json", "documentation_review_status.md"],
      humanGate: "Failed deterministic checks block continuation until resolved and re-run.",
    },
    "execute-remaining": {
      abstractions: ["Incremental delivery", "Capability-gap reduction", "Review queue reconciliation"],
      routes: [
        { to: "/cycles", label: "Loop Processes" },
        { to: "/reviews/exchange", label: "Activity" },
        { to: "/review", label: "Review Hub" },
      ],
      artifacts: ["loop_state.md", "current_guidance.md", "review_queue summary"],
      humanGate: "Continue/pause/stop decision is required at each cycle boundary.",
    },
    productize: {
      abstractions: ["Operational endpoint readiness", "Release governance", "Deployment flow controls"],
      routes: [
        { to: "/project-topology", label: "Project Topology" },
        { to: "/harness-topology", label: "Harness Topology" },
      ],
      artifacts: ["service boundaries docs", "ops runbooks", "deployment checklists"],
      humanGate: "Release sign-off required before production-facing endpoint rollout.",
    },
    document: {
      abstractions: ["Auditability", "Canonical records", "Archive traceability"],
      routes: [
        { to: "/docs", label: "Docs" },
        { to: "/archive", label: "Archive" },
      ],
      artifacts: ["changelog.md", "current_guidance.md", "archive_register.md", "HUMAN_REVIEW.md"],
      humanGate: "Documentation and review surfaces must reflect final cycle decision before closure.",
    },
  };

  const quickLoopItems: CardExpandItem[] = [
    {
      id: "phase-loop",
      title: "Phase Loop",
      subtitle: "Generic Loop",
      description: "Discover, plan, implement, and gate each phase transition.",
    },
    {
      id: "update-loop",
      title: "Update Loop",
      subtitle: "Generic Loop",
      description: "Apply update-scope changes with explicit cycle-close and human-gate checks.",
    },
    {
      id: "upgrade-loop",
      title: "Upgrade Loop",
      subtitle: "Generic Loop",
      description: "Route and execute upgrades after human review and risk triage.",
    },
  ];

  const quickLoopDetails: Record<string, QuickLoopDetail> = {
    "phase-loop": {
      goal: "Progress project phases with deterministic checks and explicit human decisions.",
      sequence: [
        "Discover context and acceptance criteria",
        "Plan phase scope and stage boundaries",
        "Ask human when uncertainty remains",
        "Plan git process and deterministic checks",
        "Implement the approved scope",
        "Assess next phase readiness",
        "Human gate for continue/pause/stop",
      ],
      humanGate: "Every phase transition requires explicit reviewer decision before proceeding.",
    },
    "update-loop": {
      goal: "Handle active updates without queue drift or missing approval context.",
      sequence: [
        "Route update work into active update queue",
        "Execute deterministic checks and synchronize impacted docs",
        "Record changelog + guidance + loop-process updates",
        "Run queue reconciliation and verify zero-state accuracy",
        "Archive completed update records and keep active index actionable-only",
      ],
      humanGate: "Cycle continuation is blocked until update-related review and approvals are complete.",
    },
    "upgrade-loop": {
      goal: "Close harness and project capability gaps with routed upgrade decisions.",
      sequence: [
        "Collect post-gate upgrade candidates",
        "Route each candidate: upgrade_next_cycle, defer_with_risk, or reject",
        "Commission approved upgrades and execute deterministic checks",
        "Update tracker artifacts and archive decision evidence",
        "Re-evaluate remaining upgrades at next human gate",
      ],
      humanGate: "No upgrade executes or closes without explicit human routing decision.",
    },
  };

  const loopSummaryRows = snapshot.harness_help.flows.map((flow) => ({
    flow_id: flow.flow_id,
    title: flow.title,
    trigger: flow.trigger,
    step_count: flow.steps.length,
    gate_count: flow.human_gates.length,
  }));

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h2 className="section-title" style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
          <span>Harness Help and Guidance</span>
          <TooltipHint text="Generic operating guidance for project management and harness management flows." />
        </h2>
        <p className="section-subtitle">
          Use Help as the quick orientation layer. Move to Topology, Activity, Review Hub, and Docs for operational drill-downs.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
          <Link to="/deploy/map" className="btn" style={{ textDecoration: "none" }}>
            Open Deploy Map
          </Link>
          <Link to="/deploy/builder" className="btn" style={{ textDecoration: "none" }}>
            Open Builder
          </Link>
          <Link to="/settings/system" className="btn" style={{ textDecoration: "none" }}>
            Open System Status
          </Link>
          <Link to="/deploy/quick-start" className="btn" style={{ textDecoration: "none" }}>
            Quick Start
          </Link>
          {visualReferenceDoc ? (
            <Link to={`/docs/${visualReferenceDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
              Visual Reference
            </Link>
          ) : null}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Example End-to-End Flow</h3>
        <p className="section-subtitle">
          Expand each step to view top-level abstractions, route handoffs, artifact expectations, and human-gate checkpoints.
        </p>
        <CardExpandGrid
          items={exampleFlowItems}
          columns={{ base: 1, sm: 2, md: 2, lg: 5 }}
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
            const detail = exampleFlowDetails[item.id];
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
                    <p className="card-head">Top-Level Abstractions</p>
                    <ul>
                      {detail.abstractions.map((value) => (
                        <li key={`${item.id}-abs-${value}`}>{value}</li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Primary Routes</p>
                    <ul>
                      {detail.routes.map((route) => (
                        <li key={`${item.id}-route-${route.to}`}>
                          <Link to={route.to} style={{ color: "var(--cyan)", textDecoration: "none" }}>
                            {route.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </section>
                  <section>
                    <p className="card-head">Expected Artifacts</p>
                    <ul>
                      {detail.artifacts.map((value) => (
                        <li key={`${item.id}-artifact-${value}`} className="mono">
                          {value}
                        </li>
                      ))}
                    </ul>
                  </section>
                </div>
                <p className="metric-sub" style={{ margin: 0 }}>
                  Human gate: {detail.humanGate}
                </p>
              </div>
            );
          }}
        />
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Generic Quick Loops</h3>
        <p className="section-subtitle">
          Phase, update, and upgrade loops with concise sequencing and mandatory human-gate reminders.
        </p>
        <CardExpandGrid
          items={quickLoopItems}
          columns={{ base: 1, sm: 2, md: 3, lg: 3 }}
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
            const detail = quickLoopDetails[item.id];
            if (!detail) {
              return null;
            }

            return (
              <div className="harness-expanded-body">
                <h4 style={{ margin: 0 }}>{item.title}</h4>
                <p className="muted" style={{ margin: "0.35rem 0 0.7rem" }}>
                  {detail.goal}
                </p>
                <section>
                  <p className="card-head">Sequence</p>
                  <ol style={{ margin: "0.5rem 0 0", paddingLeft: "1.05rem", display: "grid", gap: "0.3rem" }}>
                    {detail.sequence.map((step) => (
                      <li key={`${item.id}-sequence-${step}`}>{step}</li>
                    ))}
                  </ol>
                </section>
                <p className="metric-sub" style={{ margin: 0 }}>
                  Human gate: {detail.humanGate}
                </p>
              </div>
            );
          }}
        />
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Project Management Surfaces</h3>
        <p className="section-subtitle">Project planning and delivery routes for phase execution and architecture alignment.</p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
          {[
            { to: "/project-topology", label: "Project Topology" },
            { to: "/project-status", label: "Project Status" },
            { to: "/phases", label: "Phases" },
            { to: "/cycles", label: "Loop Processes" },
            { to: "/policies", label: "Policies" },
            { to: "/features", label: "Features" },
          ].map((entry) => (
            <Link key={entry.to} to={entry.to} className="btn" style={{ textDecoration: "none" }}>
              {entry.label}
            </Link>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Harness Management Surfaces</h3>
        <p className="section-subtitle">Harness routing, queue governance, builder setup, and runtime diagnostics.</p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
          {[
            { to: "/harness-topology", label: "Harness Topology" },
            { to: "/reviews/exchange", label: "Activity" },
            { to: "/builder", label: "Deploy Builder" },
            { to: "/review", label: "Review Hub" },
            { to: "/system-status", label: "System Status" },
            { to: "/changes", label: "Changes" },
          ].map((entry) => (
            <Link key={entry.to} to={entry.to} className="btn" style={{ textDecoration: "none" }}>
              {entry.label}
            </Link>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Harness Process Loops (Summary)</h3>
        <p className="section-subtitle">
          Full loop contracts are maintained in Harness Topology. Help keeps a quick summary for orientation.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Loop</th>
              <th>Trigger</th>
              <th>Steps</th>
              <th>Human Gates</th>
              <th>Drill-Down</th>
            </tr>
          </thead>
          <tbody>
            {loopSummaryRows.map((row) => (
              <tr key={row.flow_id}>
                <td>{row.title}</td>
                <td>{row.trigger}</td>
                <td>{row.step_count}</td>
                <td>{row.gate_count}</td>
                <td>
                  <Link to="/harness-topology" style={{ color: "var(--cyan)", textDecoration: "none" }}>
                    Open Harness Topology
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <RoutingSurfacesCard
        links={[
          { to: "/harness-topology", label: "Harness Topology: Loop Contracts" },
          { to: "/reviews/exchange", label: "Activity: Approval Routing" },
          { to: "/review", label: "Review Hub: Human Decision" },
          { to: "/project-topology", label: "Project Topology" },
          { to: "/docs", label: "Docs Index" },
        ]}
        subtitle="Use these routes after Help orientation to execute or review work."
      />

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Guidelines and Deep Dives</h3>
        <p className="section-subtitle">Secondary references for operator workflows and governance details.</p>
        <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.7rem" }}>
          {snapshot.harness_help.guidelines.map((guideline) => (
            <div key={guideline.path} className="card card-pad" style={{ padding: "0.7rem" }}>
              <strong>{guideline.label}</strong>
              <p className="muted" style={{ margin: "0.28rem 0 0.45rem" }}>
                {guideline.description}
              </p>
              {renderDocLink(guideline.path)}
            </div>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Route Context Assessment</h3>
        <p className="section-subtitle">
          Ownership and purpose inventory used by routing and review surfaces.
        </p>
        <div className="route-context-grid">
          {ROUTE_CONTEXT_INVENTORY.map((entry) => (
            <article key={entry.route} className="route-context-card">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.4rem" }}>
                <strong>{entry.title}</strong>
                <span className="mono">{entry.route}</span>
              </div>
              <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                {entry.purpose}
              </p>
              <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
                audience: {entry.audience} | owner: {entry.owner}
              </p>
              <p className="metric-sub" style={{ marginTop: "0.25rem" }}>
                overlap: {entry.overlapNotes}
              </p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
