import type { ReactNode } from "react";

interface PageHeroProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  chips?: ReactNode;
  actions?: ReactNode;
  centerContent?: ReactNode;
  children?: ReactNode;
  compact?: boolean;
}

export function PageHero({
  title,
  subtitle,
  eyebrow,
  chips,
  actions,
  centerContent,
  children,
  compact = false,
}: PageHeroProps) {
  const hasUtilityContent = Boolean(title || subtitle || eyebrow || chips || actions || centerContent || children);
  if (!hasUtilityContent) {
    return null;
  }

  return (
    <section className={`card card-pad page-hero ${compact ? "compact" : ""}`.trim()} style={{ gridColumn: "span 12" }}>
      <div className={`page-hero-head ${centerContent ? "with-center" : ""}`.trim()}>
        <div className="page-hero-copy">
          {eyebrow ? <p className="page-hero-eyebrow">{eyebrow}</p> : null}
          {title ? <h1 className="page-hero-title">{title}</h1> : null}
          {subtitle ? <p className="page-hero-subtitle">{subtitle}</p> : null}
        </div>
        {centerContent ? <div className="page-hero-center">{centerContent}</div> : null}
        {actions ? <div className="page-hero-actions">{actions}</div> : null}
      </div>
      {chips ? <div className="page-hero-chips">{chips}</div> : null}
      {children ? <div className="page-hero-body">{children}</div> : null}
    </section>
  );
}
