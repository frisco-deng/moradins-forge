export const SEEDED_DEPLOY_EXAMPLE = {
  repoName: "seeded-analytics-portal",
  workflow: "Current Project",
  goal: "Deploy a governed sidecar for a single-user analytics portal without mutating the app repo directly.",
  users: "Operator and project maintainer",
  constraints: "Linux-hosted, browser-based, single-user scope, sidecar-only writes",
  deploymentTarget: "Local sidecar companion under .moradins-harness",
  sidecarPath: "/sandbox/seeded-analytics-portal/.moradins-harness",
  approvalState: "awaiting_human_review",
  criticalGaps: [
    "Confirm the existing repo already has an operator-approved deployment target.",
    "Fill the remaining project-specific docs before phase execution.",
  ],
  artifacts: [
    "template_fill_map.md",
    "alignment_state.md",
    "phase_plan.md",
    "execution_prompts.md",
  ],
  phaseSummary: "Three phases generated: baseline alignment, sidecar hydration, and first implementation slice.",
  verifySummary: {
    overall: "attention",
    manualRequired: 2,
    missing: 1,
    nextAction: "Review the alignment state, confirm the sidecar destination, and approve the first bootstrap prompt.",
  },
} as const;
