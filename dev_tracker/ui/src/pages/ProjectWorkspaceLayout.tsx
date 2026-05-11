import { useEffect } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";

import { SecondaryNavBar } from "../components/SecondaryNavBar";
import {
  decodeProjectRouteId,
  isOverviewManagerProject,
  OVERVIEW_MANAGER_PROJECT_ID,
  OVERVIEW_MANAGER_PROJECT_LABEL,
  writeOverviewActiveProject,
} from "../lib/overview-project";
import { useTracker } from "../lib/tracker-context";

export function ProjectWorkspaceLayout() {
  const { projectId } = useParams();
  const location = useLocation();
  const { builderStatus, snapshot } = useTracker();
  const resolvedProject = decodeProjectRouteId(projectId);
  const projectLabel = isOverviewManagerProject(resolvedProject) ? OVERVIEW_MANAGER_PROJECT_LABEL : resolvedProject;
  const projectPath = isOverviewManagerProject(resolvedProject)
    ? snapshot?.repo_root ?? "/repo"
    : builderStatus?.known_repos.find((repo) => repo.name === resolvedProject)?.path ?? "Unknown repo path";
  const routeId = projectId || "manager";

  useEffect(() => {
    writeOverviewActiveProject(resolvedProject || OVERVIEW_MANAGER_PROJECT_ID);
  }, [resolvedProject]);

  return (
    <>
      <div className="page-grid">
        <SecondaryNavBar
          label={projectLabel}
          currentPath={location.pathname}
          navLabel={`${projectLabel} workspace`}
          tabs={[
            { label: "Overview", to: `/project/${routeId}/overview` },
            { label: "Delivery", to: `/project/${routeId}/delivery/features` },
            { label: "Governance", to: `/project/${routeId}/governance` },
            { label: "Topology", to: `/project/${routeId}/topology/project` },
            { label: "Docs", to: `/project/${routeId}/docs` },
            { label: "Operations", to: `/project/${routeId}/operations/loops` },
          ]}
        />
      </div>
      <div className="workspace-layout-body">
        <Outlet />
      </div>
    </>
  );
}
