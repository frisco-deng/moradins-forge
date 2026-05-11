import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

interface WorkspaceTab {
  label: string;
  to: string;
}

interface WorkspaceTabsProps {
  title?: string;
  description?: string;
  tabs: WorkspaceTab[];
  chips?: ReactNode;
  actions?: ReactNode;
  eyebrow?: string;
  compact?: boolean;
  navLabel?: string;
  descriptionTone?: "muted" | "accent";
}

export function WorkspaceTabs({
  title,
  description,
  tabs,
  chips,
  actions,
  eyebrow = "Workspace",
  compact = false,
  navLabel,
  descriptionTone = "muted",
}: WorkspaceTabsProps) {
  return (
    <section className={`card card-pad workspace-header-card ${compact ? "compact" : ""}`.trim()} style={{ gridColumn: "span 12" }}>
      <div className="workspace-header-copy">
        <div>
          {eyebrow ? <p className="card-head">{eyebrow}</p> : null}
          {title ? <h2 className="workspace-header-title">{title}</h2> : null}
          {description ? (
            <p className={`workspace-header-description ${descriptionTone === "accent" ? "accent" : ""}`.trim()}>{description}</p>
          ) : null}
        </div>
        {actions ? <div className="workspace-header-actions">{actions}</div> : null}
      </div>
      {chips ? <div className="workspace-header-chips">{chips}</div> : null}
      <nav className="workspace-tabs" aria-label={navLabel ?? `${title ?? "Workspace"} navigation`}>
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={({ isActive }) => `workspace-tab ${isActive ? "active" : ""}`.trim()}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </section>
  );
}
