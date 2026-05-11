export const OVERVIEW_ACTIVE_PROJECT_KEY = "mh_overview_active_project_v1";
export const OVERVIEW_PROJECT_CHANGE_EVENT = "mh-overview-project-change";
export const OVERVIEW_MANAGER_PROJECT_ID = "__mh_manager_repo__";
export const OVERVIEW_MANAGER_PROJECT_LABEL = "Moradin Forge";
export const OVERVIEW_MANAGER_ROUTE_ID = "manager";

export function readOverviewActiveProject() {
  try {
    return String(localStorage.getItem(OVERVIEW_ACTIVE_PROJECT_KEY) ?? "").trim();
  } catch {
    return "";
  }
}

export function writeOverviewActiveProject(value: string) {
  const normalized = String(value ?? "").trim();
  try {
    if (!normalized) {
      localStorage.removeItem(OVERVIEW_ACTIVE_PROJECT_KEY);
    } else {
      localStorage.setItem(OVERVIEW_ACTIVE_PROJECT_KEY, normalized);
    }
  } catch {
    // ignore localStorage failures
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(OVERVIEW_PROJECT_CHANGE_EVENT, { detail: { project: normalized } }));
  }
}

export function isOverviewManagerProject(value: string) {
  return String(value ?? "").trim() === OVERVIEW_MANAGER_PROJECT_ID;
}

export function encodeProjectRouteId(value: string) {
  const normalized = String(value ?? "").trim();
  if (!normalized || isOverviewManagerProject(normalized)) {
    return OVERVIEW_MANAGER_ROUTE_ID;
  }
  return encodeURIComponent(normalized);
}

export function decodeProjectRouteId(value: string | undefined) {
  const normalized = String(value ?? "").trim();
  if (!normalized || normalized === OVERVIEW_MANAGER_ROUTE_ID) {
    return OVERVIEW_MANAGER_PROJECT_ID;
  }

  try {
    return decodeURIComponent(normalized);
  } catch {
    return normalized;
  }
}

export function resolveSelectedProjectLabel(value: string) {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "No Project Selected";
  }
  if (isOverviewManagerProject(normalized)) {
    return OVERVIEW_MANAGER_PROJECT_LABEL;
  }
  return normalized;
}
