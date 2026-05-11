import { Link } from "react-router-dom";

import { TooltipHint } from "./TooltipHint";

export interface RoutingSurfaceLink {
  to: string;
  label: string;
}

interface RoutingSurfacesCardProps {
  title?: string;
  subtitle?: string;
  links: RoutingSurfaceLink[];
}

export function RoutingSurfacesCard({
  title = "Operational Routing Surfaces",
  subtitle = "Navigate loop processes, approvals, artifacts, and topology handoffs from one place.",
  links,
}: RoutingSurfacesCardProps) {
  return (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
        <span>{title}</span>
        <TooltipHint text="Shared navigation surface for loop execution, approval routing, and architecture context handoffs." />
      </h3>
      <p className="section-subtitle">{subtitle}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.7rem" }}>
        {links.map((link) => (
          <Link key={link.to} to={link.to} className="btn" style={{ textDecoration: "none" }}>
            {link.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
