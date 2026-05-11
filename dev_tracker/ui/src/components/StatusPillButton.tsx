import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { GlassPopover } from "./GlassPopover";

type PillTone = "success" | "warning" | "error" | "info";

interface StatusPillButtonProps {
  tone: PillTone;
  children: string;
  ariaLabel?: string;
  popoverContent?: ReactNode | ((controls: { close: () => void }) => ReactNode);
  preferredWidth?: number;
  align?: "start" | "center" | "end";
  to?: string;
  onClick?: () => void;
}

export function StatusPillButton({
  tone,
  children,
  ariaLabel,
  popoverContent,
  preferredWidth,
  align,
  to,
  onClick,
}: StatusPillButtonProps) {
  const className = `chip interactive ${tone}`;
  if (popoverContent) {
    return (
      <GlassPopover
        ariaLabel={ariaLabel ?? children}
        preferredWidth={preferredWidth}
        align={align}
        triggerClassName={className}
        trigger={<span>{children}</span>}
      >
        {popoverContent}
      </GlassPopover>
    );
  }

  if (to) {
    return (
      <Link to={to} className={className} style={{ textDecoration: "none" }}>
        {children}
      </Link>
    );
  }

  return (
    <button type="button" className={className} onClick={onClick} aria-label={ariaLabel ?? children}>
      {children}
    </button>
  );
}
