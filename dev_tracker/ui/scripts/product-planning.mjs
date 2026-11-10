/** Product-grounded planning; no filesystem, network, approvals or execution. */
const list = (value) =>
  Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter(Boolean)
    : [];
const text = (value) => String(value ?? "").trim();
const csv = (value) => text(value).split(",").map(text).filter(Boolean);

export function recommendProfile(intake = {}) {
  const goal =
    `${intake.project_goal || ""} ${intake.project_prompt || ""} ${intake.integrations || ""}`.toLowerCase();
  if (["pipeline", "etl", "batch"].some((word) => goal.includes(word)))
    return "data_pipeline";
  if (["agent", "assistant"].some((word) => goal.includes(word)))
    return "agent_platform";
  if (["internal", "ops", "admin"].some((word) => goal.includes(word)))
    return "internal_tooling";
  return "web_app"; // Advisory profile label, never an inferred deployment architecture.
}

export function normalizeSynthesis(raw = {}) {
  return {
    summary: text(raw.summary),
    recommended_profile: text(raw.recommended_profile) || "web_app",
    must_haves: list(raw.must_haves),
    open_questions: list(raw.open_questions),
    product_spec: {
      intent: text(raw.product_spec?.intent),
      target_users: list(raw.product_spec?.target_users),
      constraints: list(raw.product_spec?.constraints),
      milestones: list(raw.product_spec?.milestones),
    },
    design: {
      components: list(raw.design?.components),
      data_flows: list(raw.design?.data_flows),
      risks: list(raw.design?.risks),
    },
    plan: {
      workstreams: list(raw.plan?.workstreams),
      initial_backlog: list(raw.plan?.initial_backlog),
    },
  };
}

export function deterministicSynthesis(session) {
  const intake = session.intake ?? {};
  const goal = text(intake.project_goal || intake.project_prompt);
  const users = csv(intake.users);
  const integrations = csv(intake.integrations);
  const answers = Object.entries(session.answers ?? {}).filter(([, value]) =>
    text(value),
  );
  const gaps = list(session.project_scan_summary?.critical_gaps);
  const questions = [
    ...(!goal
      ? [
          "Product outcome unknown: recover the accepted user journey before dependent implementation choices.",
        ]
      : []),
    ...(!users.length
      ? [
          "Intended users unknown: inspect existing product evidence before choosing interaction boundaries.",
        ]
      : []),
    ...(!text(intake.deployment_target) && !list(session.project_scan_summary?.deployment_surfaces).length
      ? ["Deployment surface not declared or observed: inspect the owning repository before deployment choices."] : []),
    ...(!text(intake.constraints) && !text(intake.other_context)
      ? ["Operating constraints not supplied in intake: recover existing limits before capacity choices."] : []),
    ...gaps.map(
      (gap) =>
        `Investigate the operation affected by this recorded scan gap: ${gap}`,
    ),
  ];
  return {
    summary: `Product planning for ${goal || "an unresolved product outcome"}; ${answers.length} recorded answers are evidence, not a sufficiency threshold.`,
    recommended_profile: recommendProfile(intake),
    must_haves: [
      `Prove a normal-path baseline journey for: ${goal || "the accepted product outcome once recovered"}.`,
      "Connect the selected slice to the full accepted product scope, owning interfaces and integration acceptance.",
      "Retain essential safeguards and actual adoption/promotion approvals; deferred outcomes remain unfinished.",
      "Review affected consumers, contracts and evidence when a material dependency or assumption changes; preserve unaffected work.",
    ],
    open_questions: questions,
    product_spec: {
      intent: goal,
      target_users: users,
      constraints: [
        ...csv(intake.constraints),
        ...[
          "timeline",
          "compliance",
          "deployment_target",
          "other_context",
        ].flatMap((key) =>
          text(intake[key]) ? [`${key}: ${text(intake[key])}`] : [],
        ),
      ],
      milestones: [
        `Observe baseline acceptance through the normal journey for: ${goal || "the unresolved product outcome"}.`,
        "Prove integrated repeatability while retaining broader accepted outcomes.",
        "Automate known steps, then refine capacity, resilience and broader hardening against accepted targets.",
      ],
    },
    design: {
      components: [
        ...(text(intake.deployment_target)
          ? [`Declared deployment surface: ${text(intake.deployment_target)}`]
          : []),
        ...integrations.map(
          (name) =>
            `Declared integration: ${name}; owner/interface acceptance to be verified.`,
        ),
      ],
      data_flows: goal
        ? [
            `Accepted journey: ${goal}; trace its actual entrypoint, owners and dependency handoffs.`,
          ]
        : [],
      risks: [
        "Data ownership, interface, identity/trust, deployment and capacity assumptions can cause downstream rework; probe material uncertainty before dependent changes.",
        "A profile recommendation does not establish a need for services, databases or agent orchestration.",
        ...gaps.map(
          (gap) => `Recorded scan gap, applicability unverified: ${gap}`,
        ),
      ],
    },
    plan: {
      workstreams: [
        "Product-linked working baseline",
        "Normal-path integration and repeatability",
        "Automation and evidence-based refinement",
      ],
      initial_backlog: [
        `Select the smallest integrated acceptance check for: ${goal || "the accepted outcome after recovering it"}.`,
        "Identify the selected slice's owners, consumed/provided interfaces and material assumptions from current evidence.",
        ...(answers.length
          ? [
              "Review relevant recorded answers in the existing discovery session; do not promote unrelated responses to product constraints.",
            ]
          : []),
        "Run the smallest feasibility or discriminating check before committing uncertain dependent implementation.",
        "On dependency change, update affected consumers/contracts/plans and invalidate only affected evidence; continue independent lanes.",
        "Keep deferred accepted outcomes visible; a branch or component milestone cannot close the whole product.",
      ],
    },
  };
}

export function buildDeterministicPhasePlan({
  session,
  targetRepo,
  workflowType,
}) {
  const s = normalizeSynthesis(
    session.synthesis ?? deterministicSynthesis(session),
  );
  const goal =
    s.product_spec.intent ||
    text(session.intake?.project_goal || session.intake?.project_prompt) ||
    "the unresolved product outcome";
  const surfaces = [
    "languages",
    "package_managers",
    "ci_surfaces",
    "deployment_surfaces",
  ].flatMap((key) =>
    list(session.project_scan_summary?.[key]).length
      ? [`${key}: ${list(session.project_scan_summary[key]).join(", ")}`]
      : [],
  );
  return {
    summary: `Product-linked phase plan for ${targetRepo} from ${workflowType}; profiles are advisory and all accepted outcomes remain in scope.`,
    next_recommended_phase_id: "phase_1",
    phases: [
      {
        phase_id: "phase_1",
        title: "Prove The Product Baseline",
        objective: `Build and observe the smallest normal-path journey for ${goal}.`,
        deliverables: [
          `Recover intended users, journey, baseline acceptance and broader scope from current product evidence: ${goal}.`,
          "Identify owning interfaces, critical dependencies and essential safeguards; probe unknowns material to this slice.",
          "Implement and test a working product slice through its normal entrypoint; preparation alone is not acceptance.",
          `Preserve existing repository and validation surface${surfaces.length ? `: ${surfaces.join("; ")}` : "; establish missing facts through bounded inspection"}.`,
          ...(s.product_spec.target_users.length
            ? [`Intended users: ${s.product_spec.target_users.join("; ")}.`]
            : []),
          ...s.product_spec.constraints.map(
            (value) => `Retain supplied constraint/context: ${value}`,
          ),
        ],
        execution_focus:
          "Keep the whole product visible while implementing one useful journey; documentation hydration supports implementation rather than becoming its endpoint.",
      },
      {
        phase_id: "phase_2",
        title: "Integrate And Prove Repeatability",
        objective: `Connect the baseline to the remaining accepted journey for ${goal}.`,
        deliverables: [
          "Exercise actual producer/consumer configuration, trust, software and durable execution handoffs.",
          "Prove native repeatability and affected recovery; manual/reference success remains distinct from installed product acceptance.",
          ...s.must_haves,
          ...s.design.components,
          ...s.design.data_flows,
          ...s.plan.initial_backlog,
        ],
        execution_focus:
          "Review dependency changes against affected consumers/contracts and preserve unaffected work; retain every accepted outcome.",
      },
      {
        phase_id: "phase_3",
        title: "Automate And Refine Against Product Targets",
        objective: `Automate proven work and refine ${targetRepo} against accepted capacity, reliability and release targets.`,
        deliverables: [
          "Run native checks and required qualification; retain essential safeguards throughout.",
          "Measure the accepted workload before adding scaling complexity; unestablished capacity remains unknown.",
          "Keep deferred obligations explicit and require observed acceptance for the complete product.",
          ...s.design.risks,
        ],
        execution_focus:
          "Continue authorized independent lanes across stages; actual adoption, live-operation and promotion boundaries remain binding.",
      },
    ],
  };
}

export function buildPromptContextSummary(
  session,
  { targetRepo, selectedProfile, workflowType, alignmentState = null },
) {
  const lines = [
    `target_repo=${targetRepo}`,
    `workflow_type=${workflowType}`,
    `selected_profile=${selectedProfile || "unselected"} (advisory)`,
    `product_scope_source=${session.artifacts?.product_spec || `docs/product_specs/discovery_${session.session_id}_project_spec.md`}`,
    `project_goal=${session.intake.project_goal || "unset"}`,
    `users=${session.intake.users || "unset"}`,
    `constraints=${session.intake.constraints || "unset"}`,
    `timeline=${session.intake.timeline || "unset"}`,
    `integrations=${session.intake.integrations || "unset"}`,
    `compliance=${session.intake.compliance || "unset"}`,
    `deployment_target=${session.intake.deployment_target || "unset"}`,
    `other_context=${session.intake.other_context || "unset"}`,
    `approval_required=${session.approval?.approved ? "approved" : "pending"}`,
  ];

  const scanLanguages = list(session.project_scan_summary?.languages);
  const scanPackageManagers = list(
    session.project_scan_summary?.package_managers,
  );
  const scanCiSurfaces = list(session.project_scan_summary?.ci_surfaces);
  const scanDeploymentSurfaces = list(
    session.project_scan_summary?.deployment_surfaces,
  );
  lines.push(`languages=${scanLanguages.join("; ") || "none"}`);
  lines.push(`package_managers=${scanPackageManagers.join("; ") || "none"}`);
  lines.push(`ci_surfaces=${scanCiSurfaces.join("; ") || "none"}`);
  lines.push(
    `deployment_surfaces=${scanDeploymentSurfaces.join("; ") || "none"}`,
  );
  if (session.project_scan_summary?.critical_gaps?.length) {
    lines.push(
      `critical_gaps=${session.project_scan_summary.critical_gaps.join("; ")}`,
    );
  }
  if (alignmentState) {
    lines.push(`alignment_overall=${alignmentState.summary.overall_status}`);
    lines.push(
      `alignment_manual_required=${alignmentState.summary.manual_required_count}`,
    );
    lines.push(`alignment_missing=${alignmentState.summary.missing_count}`);
    if (alignmentState.next_recommended_action) {
      lines.push(
        `alignment_next_action=${alignmentState.next_recommended_action.next_action}`,
      );
      lines.push(
        `alignment_next_route=${alignmentState.next_recommended_action.route}`,
      );
    }
  }

  return lines.join("\n");
}

export function buildFollowOnPrompts({
  session,
  targetRepo,
  selectedProfile,
  workflowType,
  phasePlan,
  alignmentState,
}) {
  const contextSummary = buildPromptContextSummary(session, {
    targetRepo,
    selectedProfile,
    workflowType,
    alignmentState,
  });
  const phaseOne = phasePlan.phases[0];
  const phaseReference =
    session.artifacts?.phase_plan_markdown ||
    `Harness/artifacts/control/discovery_sessions/${session.session_id}/phase_plan.md`;
  const phaseLines = phasePlan.phases.flatMap((phase) => [
    `- ${phase.phase_id}: ${phase.title}`,
    `  objective: ${phase.objective}`,
    // Full acceptance and deferred scope remain in the referenced phase plan.
    `  focus: ${phase.execution_focus}`,
  ]);
  const alignmentLines = alignmentState
    ? [
        "Alignment summary:",
        `- overall_status: ${alignmentState.summary.overall_status}`,
        `- manual_required_count: ${alignmentState.summary.manual_required_count}`,
        `- missing_count: ${alignmentState.summary.missing_count}`,
        `- next_recommended_phase_id: ${alignmentState.next_recommended_phase_id}`,
        ...(alignmentState.next_recommended_action
          ? [
              `- next_recommended_action: ${alignmentState.next_recommended_action.next_action}`,
              `- next_recommended_route: ${alignmentState.next_recommended_action.route}`,
            ]
          : []),
        `- alignment_artifact: Harness/artifacts/control/discovery_sessions/${session.session_id}/alignment_state.md`,
      ]
    : [];

  return [
    {
      prompt_id: "bootstrap_hydration",
      title: "Recover Product Context",
      summary:
        "Recover current product intent, journey, dependencies and the next useful slice from existing evidence.",
      prompt: [
        `You are onboarding Moradins Harness inside the repo "${targetRepo}".`,
        "Inspect the existing product and repository context; use authoritative docs and existing capabilities before consequential component choices.",
        "Update only product facts needed for the next slice: users, journey, baseline acceptance, broader scope, owners, dependencies and operating constraints. Distinguish facts, assumptions and unknowns.",
        "Treat the detected repo language, package-manager, CI, and deployment surfaces as constraints unless discovery artifacts explicitly justify a change.",
        "Keep profiles advisory; do not invent services, storage or agent orchestration. Resolve material unknowns with a small check, then implement.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        "Use these source artifacts if present:",
        `- ${session.artifacts?.product_spec ?? "docs/product_specs/discovery_<session>_project_spec.md"}`,
        `- ${session.artifacts?.design_doc ?? "docs/design_docs/discovery_<session>_architecture.md"}`,
        `- ${session.artifacts?.implementation_plan ?? "docs/exec_plans/implementation/active/plan_<session>_discovery_generated.md"}`,
        `- ${session.artifacts?.alignment_state_markdown ?? `Harness/artifacts/control/discovery_sessions/${session.session_id}/alignment_state.md`}`,
      ].join("\n"),
    },
    {
      prompt_id: "phase_planning",
      title: "Build Project Phases",
      summary:
        "Turn the discovery output into a project-specific phase plan with concrete deliverables and verification.",
      prompt: [
        `Create or update the project phase plan for "${targetRepo}".`,
        "Use the deployed harness, discovery output, and the draft phase structure below to produce a concrete implementation route.",
        "Write the plan in the repo's canonical docs/exec_plans and implementation phase surfaces, keeping the scope explicit and verification repo-native.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        `Read complete deliverables and accepted scope from ${phaseReference}; do not drop deferred outcomes.`,
        "Draft phase structure:",
        ...phaseLines,
      ].join("\n"),
    },
    {
      prompt_id: "phase_1_execution",
      title: "Implement Phase 1",
      summary:
        "Implement the selected baseline journey while retaining the complete accepted product scope.",
      prompt: [
        `Implement only ${phaseOne.phase_id} (${phaseOne.title}) for "${targetRepo}".`,
        "Keep this selected slice connected to its actual owners, dependencies and integrated acceptance. Its completion is not whole-product completion.",
        "",
        "Phase objective:",
        phaseOne.objective,
        "",
        "Required deliverables:",
        ...phaseOne.deliverables.map((item) => `- ${item}`),
        "",
        "Execution focus:",
        phaseOne.execution_focus,
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
      ].join("\n"),
    },
    {
      prompt_id: "run_all_phases",
      title: "Run All Phases",
      summary:
        "Execute the accepted product route through integrated acceptance while preserving actual authority boundaries.",
      prompt: [
        `Work through the planned phases for "${targetRepo}" in order.`,
        "Continue authorized reversible work across phases; existing discovery/adoption, live-operation and promotion approvals remain binding. Do not add per-phase confirmation gates.",
        "For each slice retain the product objective, critical constraints, owning interfaces, acceptance and deferred work. Reassess affected consumers and evidence when a dependency changes; preserve independent work.",
        "",
        "Context:",
        contextSummary,
        ...(alignmentLines.length > 0 ? ["", ...alignmentLines] : []),
        "",
        `Read complete deliverables and accepted scope from ${phaseReference}; do not drop deferred outcomes.`,
        "Phase sequence:",
        ...phaseLines,
      ].join("\n"),
    },
  ];
}
