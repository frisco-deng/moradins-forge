import { Outlet, useLocation } from "react-router-dom";

import { GuideRail } from "../components/GuideRail";
import { SecondaryNavBar } from "../components/SecondaryNavBar";
import { routeIdForPath } from "../lib/guide-flow";
import { DEPLOY_WORKSPACE_ITEMS } from "../lib/nav";
import { useGuideState } from "../lib/use-guide-state";
import { useTracker } from "../lib/tracker-context";

export function DeployWorkspaceLayout() {
  const location = useLocation();
  useTracker();
  const guideState = useGuideState();
  const currentRouteId = routeIdForPath(location.pathname) ?? "quick-start";
  const tabs = DEPLOY_WORKSPACE_ITEMS.map((item) => {
    const itemRouteId = routeIdForPath(item.path);
    return {
      label: item.label,
      to: item.path,
      showDot: itemRouteId ? currentRouteId !== itemRouteId && !guideState.visited_route_ids.includes(itemRouteId) : false,
    };
  });

  return (
    <>
      <div className="page-grid">
        <SecondaryNavBar
          label="Deploy"
          currentPath={location.pathname}
          navLabel="Deploy workspace navigation"
          tabs={tabs}
        />
        <GuideRail currentRouteId={currentRouteId} />
      </div>
      <Outlet />
    </>
  );
}
