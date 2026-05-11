import { Navigate } from "react-router-dom";

import { encodeProjectRouteId, OVERVIEW_MANAGER_PROJECT_ID, readOverviewActiveProject } from "../lib/overview-project";

interface LegacyProjectRouteRedirectProps {
  suffix: string;
}

export function LegacyProjectRouteRedirect({ suffix }: LegacyProjectRouteRedirectProps) {
  const selected = readOverviewActiveProject() || OVERVIEW_MANAGER_PROJECT_ID;
  return <Navigate to={`/project/${encodeProjectRouteId(selected)}/${suffix}`} replace />;
}

