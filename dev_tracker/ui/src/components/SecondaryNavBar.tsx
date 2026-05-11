import { NavLink } from "react-router-dom";

interface SecondaryNavItem {
  label: string;
  to: string;
  showDot?: boolean;
}

interface SecondaryNavBarProps {
  label: string;
  currentPath: string;
  tabs: SecondaryNavItem[];
  navLabel: string;
}

function isActivePath(currentPath: string, targetPath: string) {
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`);
}

export function SecondaryNavBar({ label, currentPath, tabs, navLabel }: SecondaryNavBarProps) {
  const activeTab = tabs.find((tab) => isActivePath(currentPath, tab.to)) ?? tabs[0] ?? null;

  return (
    <section className="secondary-nav-shell" style={{ gridColumn: "span 12" }}>
      <div className="secondary-nav-head">
        <p className="secondary-nav-breadcrumb">
          <span>{label}</span>
          {activeTab ? <span>{activeTab.label}</span> : null}
        </p>
      </div>
      <nav className="secondary-nav-links" aria-label={navLabel}>
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={({ isActive }) => `secondary-nav-link ${isActive ? "active" : ""}`.trim()}>
            <span>{tab.label}</span>
            {tab.showDot ? <span className="secondary-nav-dot" aria-hidden="true" /> : null}
          </NavLink>
        ))}
      </nav>
    </section>
  );
}
