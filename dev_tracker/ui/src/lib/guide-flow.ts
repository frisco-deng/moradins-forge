export type GuideRouteId = "quick-start" | "readiness" | "deploy-map" | "builder" | "system-status";
export type GuideTutorialStepId = GuideRouteId | "deploy-example";

export interface GuideRouteStep {
  id: GuideRouteId;
  path: string;
  label: string;
  shortLabel: string;
  description: string;
}

export interface GuideStateV2 {
  version: "GuideStateV2";
  hidden: boolean;
  dismissed: boolean;
  completed: boolean;
  visited_route_ids: GuideRouteId[];
  completed_tutorial_step_ids: GuideTutorialStepId[];
  example_flow_viewed: boolean;
  last_route_id: GuideRouteId | null;
  updated_at: string;
}

export const GUIDE_STORAGE_KEY = "mh_release_v1_guide_state_v1";
export const GUIDE_STATE_CHANGED_EVENT = "mh-guide-state-changed";

export const GUIDE_ROUTE_STEPS: GuideRouteStep[] = [
  {
    id: "quick-start",
    path: "/deploy/quick-start",
    label: "Quick Start",
    shortLabel: "Start",
    description: "Choose access mode, learn the control flow, and set up the release path.",
  },
  {
    id: "readiness",
    path: "/deploy/readiness",
    label: "Readiness",
    shortLabel: "Ready",
    description: "Check host tools, install request artifacts, and repo registry state.",
  },
  {
    id: "deploy-map",
    path: "/deploy/map",
    label: "Deploy Map",
    shortLabel: "Map",
    description: "Understand what the harness deploys and how the fill sources connect.",
  },
  {
    id: "builder",
    path: "/deploy/builder",
    label: "Builder",
    shortLabel: "Build",
    description: "Run discovery, generation, or guarded deploy flows.",
  },
  {
    id: "system-status",
    path: "/deploy/status",
    label: "Verify",
    shortLabel: "Verify",
    description: "Check project verification results after guarded deploy or import work.",
  },
];

function normalizeRouteId(value: unknown): GuideRouteId | null {
  if (value === "verify") {
    return "system-status";
  }
  return GUIDE_ROUTE_STEPS.some((step) => step.id === value) ? (value as GuideRouteId) : null;
}

function normalizeTutorialStepId(value: unknown): GuideTutorialStepId | null {
  if (value === "deploy-example") {
    return "deploy-example";
  }
  return normalizeRouteId(value);
}

function emitGuideStateChanged(nextState: GuideStateV2) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(GUIDE_STATE_CHANGED_EVENT, { detail: nextState }));
}

export function createDefaultGuideState(): GuideStateV2 {
  return {
    version: "GuideStateV2",
    hidden: false,
    dismissed: false,
    completed: false,
    visited_route_ids: [],
    completed_tutorial_step_ids: [],
    example_flow_viewed: false,
    last_route_id: null,
    updated_at: "",
  };
}

export function readGuideState(storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null): GuideStateV2 {
  if (!storage) {
    return createDefaultGuideState();
  }

  try {
    const raw = storage.getItem(GUIDE_STORAGE_KEY);
    if (!raw) {
      return createDefaultGuideState();
    }
    const parsed = JSON.parse(raw) as Partial<GuideStateV2> & { hidden?: boolean };
    const dismissed = parsed.dismissed === true || parsed.hidden === true;
    return {
      version: "GuideStateV2",
      hidden: dismissed,
      dismissed,
      completed: parsed.completed === true,
      visited_route_ids: Array.isArray(parsed.visited_route_ids)
        ? parsed.visited_route_ids
            .map((value) => normalizeRouteId(value))
            .filter((value): value is GuideRouteId => value !== null)
        : [],
      completed_tutorial_step_ids: Array.isArray(parsed.completed_tutorial_step_ids)
        ? parsed.completed_tutorial_step_ids
            .map((value) => normalizeTutorialStepId(value))
            .filter((value): value is GuideTutorialStepId => value !== null)
        : [],
      example_flow_viewed: parsed.example_flow_viewed === true,
      last_route_id: normalizeRouteId(parsed.last_route_id) ?? null,
      updated_at: String(parsed.updated_at ?? ""),
    };
  } catch {
    return createDefaultGuideState();
  }
}

export function writeGuideState(
  nextState: GuideStateV2,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
) {
  if (!storage) {
    return nextState;
  }
  const payload = {
    ...nextState,
    version: "GuideStateV2",
    hidden: nextState.dismissed,
    dismissed: nextState.dismissed,
    updated_at: new Date().toISOString(),
  } satisfies GuideStateV2;
  storage.setItem(
    GUIDE_STORAGE_KEY,
    JSON.stringify(payload),
  );
  emitGuideStateChanged(payload);
  return payload;
}

export function routeIdForPath(pathname: string): GuideRouteId | null {
  const normalized = pathname.trim();
  const match = GUIDE_ROUTE_STEPS.find((step) => normalized === step.path || normalized.startsWith(`${step.path}/`));
  return match?.id ?? null;
}

export function markGuideRouteVisited(
  routeId: GuideRouteId,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
): GuideStateV2 {
  const current = readGuideState(storage);
  const visited = current.visited_route_ids.includes(routeId) ? current.visited_route_ids : [...current.visited_route_ids, routeId];
  const nextState: GuideStateV2 = {
    ...current,
    visited_route_ids: visited,
    last_route_id: routeId,
  };
  return writeGuideState(nextState, storage);
}

export function setGuideDismissed(
  dismissed: boolean,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
): GuideStateV2 {
  const current = readGuideState(storage);
  return writeGuideState({ ...current, hidden: dismissed, dismissed }, storage);
}

export function setGuideHidden(
  hidden: boolean,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
): GuideStateV2 {
  return setGuideDismissed(hidden, storage);
}

export function setGuideCompleted(
  completed: boolean,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
): GuideStateV2 {
  const current = readGuideState(storage);
  return writeGuideState({ ...current, completed }, storage);
}

export function markGuideTutorialStepCompleted(
  stepId: GuideTutorialStepId,
  storage: Storage | null = typeof window !== "undefined" ? window.localStorage : null,
): GuideStateV2 {
  const current = readGuideState(storage);
  const completedSteps = current.completed_tutorial_step_ids.includes(stepId)
    ? current.completed_tutorial_step_ids
    : [...current.completed_tutorial_step_ids, stepId];
  return writeGuideState(
    {
      ...current,
      completed_tutorial_step_ids: completedSteps,
      example_flow_viewed: current.example_flow_viewed || stepId === "deploy-example",
    },
    storage,
  );
}

export function nextGuideStep(routeId: GuideRouteId | null): GuideRouteStep | null {
  if (!routeId) {
    return GUIDE_ROUTE_STEPS[0] ?? null;
  }
  const index = GUIDE_ROUTE_STEPS.findIndex((step) => step.id === routeId);
  if (index < 0 || index + 1 >= GUIDE_ROUTE_STEPS.length) {
    return null;
  }
  return GUIDE_ROUTE_STEPS[index + 1] ?? null;
}
