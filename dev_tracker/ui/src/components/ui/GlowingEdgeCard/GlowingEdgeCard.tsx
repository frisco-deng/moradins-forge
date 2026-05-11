import {
  type CSSProperties,
  type ComponentPropsWithoutRef,
  type ElementType,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useRef,
} from "react";

import "./glowing-edge-card.css";

type GlowingEdgeCardBaseProps = {
  as?: ElementType;
  disableAnimations?: boolean;
  glowRgb?: string;
  glowStrength?: number;
  radiusPx?: number;
  className?: string;
};

export type GlowingEdgeCardProps<T extends ElementType = "div"> = GlowingEdgeCardBaseProps &
  Omit<ComponentPropsWithoutRef<T>, keyof GlowingEdgeCardBaseProps | "as" | "className" | "style"> & {
    as?: T;
    className?: string;
    style?: CSSProperties;
  };

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function round(value: number, precision = 3) {
  return Number(value.toFixed(precision));
}

function pointerAngle(width: number, height: number, x: number, y: number) {
  const dx = x - width / 2;
  const dy = y - height / 2;
  if (dx === 0 && dy === 0) {
    return 0;
  }

  let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
  if (angle < 0) {
    angle += 360;
  }
  return angle;
}

function edgeProximity(width: number, height: number, x: number, y: number) {
  const nearestEdgeDistance = Math.min(x, width - x, y, height - y);
  const maxDistance = Math.max(Math.min(width, height) / 2, 1);
  return clamp(1 - nearestEdgeDistance / maxDistance, 0, 1);
}

function edgeAnchor(width: number, height: number, x: number, y: number) {
  const cx = width / 2;
  const cy = height / 2;
  const dx = x - cx;
  const dy = y - cy;

  if (dx === 0 && dy === 0) {
    return { x: cx, y: cy };
  }

  const nx = cx === 0 ? 0 : Math.abs(dx) / cx;
  const ny = cy === 0 ? 0 : Math.abs(dy) / cy;
  const maxNorm = Math.max(nx, ny);
  if (!Number.isFinite(maxNorm) || maxNorm <= 0) {
    return { x: cx, y: cy };
  }

  const scale = 1 / maxNorm;
  return {
    x: clamp(cx + dx * scale, 0, width),
    y: clamp(cy + dy * scale, 0, height),
  };
}

function prefersReducedMotion() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function GlowingEdgeCard<T extends ElementType = "div">({
  as,
  disableAnimations = false,
  glowRgb,
  glowStrength,
  radiusPx,
  className,
  style,
  children,
  onPointerMove,
  onPointerLeave,
  ...rest
}: GlowingEdgeCardProps<T>) {
  const Component = (as ?? "div") as ElementType;
  const cardRef = useRef<HTMLElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const pointerRef = useRef<{ clientX: number; clientY: number } | null>(null);

  const reducedMotion = prefersReducedMotion();
  const animationsDisabled = disableAnimations || reducedMotion;

  const externalPointerMove = onPointerMove as ((event: ReactPointerEvent<HTMLElement>) => void) | undefined;
  const externalPointerLeave = onPointerLeave as ((event: ReactPointerEvent<HTMLElement>) => void) | undefined;

  const resetPointerVars = () => {
    const node = cardRef.current;
    if (!node) {
      return;
    }
    node.style.setProperty("--gec-x", "50%");
    node.style.setProperty("--gec-y", "50%");
    node.style.setProperty("--gec-edge-x", "50%");
    node.style.setProperty("--gec-edge-y", "50%");
    node.style.setProperty("--gec-deg", "45deg");
    node.style.setProperty("--gec-d", "0");
  };

  const flushPointerFrame = () => {
    rafRef.current = null;
    const node = cardRef.current;
    const pointer = pointerRef.current;
    if (!node || !pointer || animationsDisabled) {
      return;
    }

    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }

    const x = clamp(pointer.clientX - rect.left, 0, rect.width);
    const y = clamp(pointer.clientY - rect.top, 0, rect.height);
    const xPct = round((x / rect.width) * 100);
    const yPct = round((y / rect.height) * 100);
    const deg = round(pointerAngle(rect.width, rect.height, x, y));
    const distance = round(edgeProximity(rect.width, rect.height, x, y) * 100);
    const borderAnchor = edgeAnchor(rect.width, rect.height, x, y);
    const edgeXPct = round((borderAnchor.x / rect.width) * 100);
    const edgeYPct = round((borderAnchor.y / rect.height) * 100);

    node.style.setProperty("--gec-x", `${xPct}%`);
    node.style.setProperty("--gec-y", `${yPct}%`);
    node.style.setProperty("--gec-edge-x", `${edgeXPct}%`);
    node.style.setProperty("--gec-edge-y", `${edgeYPct}%`);
    node.style.setProperty("--gec-deg", `${deg}deg`);
    node.style.setProperty("--gec-d", `${distance}`);
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    if (!animationsDisabled) {
      pointerRef.current = {
        clientX: event.clientX,
        clientY: event.clientY,
      };
      if (rafRef.current === null) {
        rafRef.current = window.requestAnimationFrame(flushPointerFrame);
      }
    }

    externalPointerMove?.(event);
  };

  const handlePointerLeave = (event: ReactPointerEvent<HTMLElement>) => {
    pointerRef.current = null;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    resetPointerVars();
    externalPointerLeave?.(event);
  };

  useEffect(() => {
    if (!animationsDisabled) {
      return;
    }
    resetPointerVars();
  }, [animationsDisabled]);

  useEffect(
    () => () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    },
    [],
  );

  const cssVars: CSSProperties & Record<string, string> = {
    "--gec-x": "50%",
    "--gec-y": "50%",
    "--gec-edge-x": "50%",
    "--gec-edge-y": "50%",
    "--gec-deg": "45deg",
    "--gec-d": "0",
  };

  if (typeof glowRgb === "string" && glowRgb.trim().length > 0) {
    cssVars["--gec-glow-rgb"] = glowRgb;
  }
  if (typeof glowStrength === "number" && Number.isFinite(glowStrength)) {
    cssVars["--gec-glow-strength"] = `${Math.max(glowStrength, 0)}`;
  }
  if (typeof radiusPx === "number" && Number.isFinite(radiusPx)) {
    cssVars["--gec-radius-px"] = `${Math.max(radiusPx, 1)}px`;
  }

  return (
    <Component
      {...rest}
      ref={(node: HTMLElement | null) => {
        cardRef.current = node;
      }}
      className={["gec-card", animationsDisabled ? "gec-static" : "", className ?? ""].filter(Boolean).join(" ")}
      style={{ ...cssVars, ...(style ?? {}) }}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <span aria-hidden className="gec-layer gec-border-layer" />
      <span aria-hidden className="gec-layer gec-mesh-layer" />
      <span aria-hidden className="gec-layer gec-halo-layer" />
      <span className="gec-content">{children}</span>
    </Component>
  );
}
