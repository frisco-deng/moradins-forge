export type DeployWorkflowId = "new_project" | "existing_project" | "import_existing_harness";
export type FillSourceKind = "seed_template" | "profile_overlay" | "user_filled" | "scan_derived";

export interface WorkflowStepSpec {
  id: string;
  title: string;
  detail: string;
  tone: FillSourceKind;
}

export interface WorkflowGraphSpec {
  title: string;
  description: string;
  steps: WorkflowStepSpec[];
}

export interface DeployMapPreviewV1 {
  version: "DeployMapPreviewV1";
  generated_at: string;
  workflow: DeployWorkflowId;
  generated_files: string[];
}

export const DEPLOY_MAP_PREVIEW_STORAGE_KEY = "mh_deploy_map_preview_v1";

export const FILL_SOURCE_META: Record<FillSourceKind, { label: string; accent: string; background: string }> = {
  seed_template: {
    label: "Moradin Payload",
    accent: "rgba(80, 180, 255, 0.92)",
    background: "rgba(80, 180, 255, 0.12)",
  },
  profile_overlay: {
    label: "Profile Overlay",
    accent: "rgba(78, 216, 156, 0.92)",
    background: "rgba(78, 216, 156, 0.12)",
  },
  user_filled: {
    label: "User Filled",
    accent: "rgba(255, 189, 84, 0.92)",
    background: "rgba(255, 189, 84, 0.12)",
  },
  scan_derived: {
    label: "Scan Derived",
    accent: "rgba(255, 113, 113, 0.92)",
    background: "rgba(255, 113, 113, 0.12)",
  },
};

export const WORKFLOW_GRAPH_SPECS: Record<DeployWorkflowId, WorkflowGraphSpec> = {
  new_project: {
    title: "New Project Bootstrap",
    description: "Operator input and compact discovery fill a new repo from the Moradin payload plus profile overlays.",
    steps: [
      {
        id: "intake",
        title: "Choose Workflow",
        detail: "Set project goal, users, constraints, and deployment target.",
        tone: "user_filled",
      },
      {
        id: "discovery",
        title: "Generate Discovery",
        detail: "Create prompt bundles, questions, and synthesis from compact context packs.",
        tone: "scan_derived",
      },
      {
        id: "seed",
        title: "Apply Moradin Payload",
        detail: "Copy manifest-approved docs trees, scripts, skills, and tracker surfaces.",
        tone: "seed_template",
      },
      {
        id: "overlay",
        title: "Write Project Artifacts",
        detail: "Overlay defaults and discovery-specific docs into the destination repo.",
        tone: "profile_overlay",
      },
    ],
  },
  existing_project: {
    title: "Current Project Sidecar",
    description: "The harness scans a selected repo, generates guarded artifacts locally, then writes a traceable sidecar over SSH or on the local host.",
    steps: [
      {
        id: "scan",
        title: "Scan Current Repo",
        detail: "Read languages, CI/test posture, governance surfaces, and critical gaps.",
        tone: "scan_derived",
      },
      {
        id: "intake",
        title: "Collect Project Context",
        detail: "Capture operator answers and sidecar boundaries for the selected repository.",
        tone: "user_filled",
      },
      {
        id: "seed",
        title: "Generate Sidecar",
        detail: "Fill the Moradin payload locally with the approved discovery profile.",
        tone: "seed_template",
      },
      {
        id: "overlay",
        title: "Deploy Guarded Output",
        detail: "Stream the validated sidecar into the allowlisted repo path and keep project status traceable.",
        tone: "profile_overlay",
      },
    ],
  },
  import_existing_harness: {
    title: "Import Existing Harness",
    description: "Import a known-good harness tree by path or bundle, validate boundaries, then review before execution resumes.",
    steps: [
      {
        id: "select",
        title: "Select Source",
        detail: "Choose a local path or uploaded bundle to import.",
        tone: "user_filled",
      },
      {
        id: "validate",
        title: "Validate Layout",
        detail: "Reject traversal, unsafe archive shapes, and out-of-root destinations.",
        tone: "scan_derived",
      },
      {
        id: "seed",
        title: "Copy Harness Tree",
        detail: "Import the approved harness seed into the destination repo.",
        tone: "seed_template",
      },
      {
        id: "review",
        title: "Review Imported State",
        detail: "Inspect the imported tree and artifacts before continuing execution.",
        tone: "profile_overlay",
      },
    ],
  },
};

const BASELINE_TEMPLATE_PATHS: Record<FillSourceKind, string[]> = {
  seed_template: [
    "README.md",
    "AGENTS.md",
    "scripts/generate_openapi_snapshots.py",
    "skills/",
    "dev_tracker/ui/",
    "docs/15_checklists/project_builder_beta_checklist.md",
  ],
  profile_overlay: [
    "docs/product_specs/generated_profile_overlay.md",
    "docs/11_ops/day0_onboarding_runbook.md",
    "docs/11_ops/day1_onboarding_runbook.md",
  ],
  user_filled: [
    "docs/product_specs/discovery_<session>_project_spec.md",
    "docs/design_docs/discovery_<session>_architecture.md",
    "docs/exec_plans/implementation/active/plan_<session>_discovery_generated.md",
  ],
  scan_derived: [
    "Harness/artifacts/control/discovery_sessions/<session>/prompt_context_v1.json",
    "Harness/artifacts/control/discovery_sessions/<session>/prompt_bundle.md",
    "Harness/artifacts/control/discovery_sessions/<session>/template_fill_map.md",
  ],
};

export function baselineTemplatePaths(): Array<{ path: string; sourceKind: FillSourceKind; preview: boolean }> {
  return (Object.keys(BASELINE_TEMPLATE_PATHS) as FillSourceKind[]).flatMap((sourceKind) =>
    BASELINE_TEMPLATE_PATHS[sourceKind].map((path) => ({
      path,
      sourceKind,
      preview: true,
    })),
  );
}

export function classifyGeneratedFileSource(relativePath: string): FillSourceKind {
  const normalized = relativePath.replaceAll("\\", "/");
  if (normalized.startsWith("Harness/artifacts/control/discovery_sessions/")) {
    return "scan_derived";
  }
  if (normalized === "docs/product_specs/generated_profile_overlay.md" || normalized.startsWith("docs/11_ops/day")) {
    return "profile_overlay";
  }
  if (
    normalized.startsWith("docs/product_specs/discovery_") ||
    normalized.startsWith("docs/design_docs/discovery_") ||
    normalized.startsWith("docs/exec_plans/implementation/active/plan_")
  ) {
    return "user_filled";
  }
  return "seed_template";
}
