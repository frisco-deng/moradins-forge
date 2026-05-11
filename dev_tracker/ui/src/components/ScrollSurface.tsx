import type { HTMLAttributes, ReactNode } from "react";

interface ScrollSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function ScrollSurface({ children, className = "", ...rest }: ScrollSurfaceProps) {
  return (
    <div {...rest} className={`scroll-surface ${className}`.trim()}>
      {children}
    </div>
  );
}
