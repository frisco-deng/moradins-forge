import { Outlet, useLocation } from "react-router-dom";

import { SecondaryNavBar } from "../components/SecondaryNavBar";
import { SETTINGS_WORKSPACE_ITEMS } from "../lib/nav";
import { useTracker } from "../lib/tracker-context";

export function SettingsWorkspaceLayout() {
  const location = useLocation();
  useTracker();

  return (
    <>
      <div className="page-grid">
        <SecondaryNavBar
          label="Settings"
          currentPath={location.pathname}
          navLabel="Settings workspace navigation"
          tabs={SETTINGS_WORKSPACE_ITEMS.map((item) => ({ label: item.label, to: item.path }))}
        />
      </div>
      <Outlet />
    </>
  );
}
