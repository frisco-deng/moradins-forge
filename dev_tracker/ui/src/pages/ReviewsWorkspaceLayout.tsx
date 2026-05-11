import { Outlet, useLocation } from "react-router-dom";

import { SecondaryNavBar } from "../components/SecondaryNavBar";
import { REVIEW_WORKSPACE_ITEMS } from "../lib/nav";
import { useTracker } from "../lib/tracker-context";

export function ReviewsWorkspaceLayout() {
  const location = useLocation();
  useTracker();

  return (
    <>
      <div className="page-grid">
        <SecondaryNavBar
          label="Reviews"
          currentPath={location.pathname}
          navLabel="Reviews workspace navigation"
          tabs={REVIEW_WORKSPACE_ITEMS.map((item) => ({ label: item.label, to: item.path }))}
        />
      </div>
      <Outlet />
    </>
  );
}
