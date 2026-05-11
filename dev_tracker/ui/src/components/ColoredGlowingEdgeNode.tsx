import { useEffect, useRef, useState, type CSSProperties, type HTMLAttributes, type PointerEvent } from "react";

export interface ColoredGlowingEdgeNodeProps extends HTMLAttributes<HTMLDivElement> {
  mode?: "dark" | "light";
  compact?: boolean;
  introAnimation?: boolean;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function round(value: number, precision = 3) {
  return Number(value.toFixed(precision));
}

function angleFromPointer(dx: number, dy: number) {
  if (dx === 0 && dy === 0) {
    return 0;
  }

  let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
  if (angle < 0) {
    angle += 360;
  }
  return angle;
}

function edgeDistance(rect: DOMRect, x: number, y: number) {
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = x - cx;
  const dy = y - cy;

  let kx = Number.POSITIVE_INFINITY;
  let ky = Number.POSITIVE_INFINITY;

  if (dx !== 0) {
    kx = cx / Math.abs(dx);
  }
  if (dy !== 0) {
    ky = cy / Math.abs(dy);
  }

  return clamp(1 / Math.min(kx, ky), 0, 1);
}

function shouldReduceMotion() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function ColoredGlowingEdgeNode({
  mode = "dark",
  compact = false,
  introAnimation = true,
  className,
  style,
  children,
  onPointerMove,
  onPointerLeave,
  ...props
}: ColoredGlowingEdgeNodeProps) {
  const nodeRef = useRef<HTMLDivElement>(null);
  const [animating, setAnimating] = useState(false);
  const animatingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const delayRef = useRef<number | null>(null);

  const stopIntroAnimation = () => {
    animatingRef.current = false;
    setAnimating(false);
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const node = nodeRef.current;
    if (!node) {
      onPointerMove?.(event);
      return;
    }

    const rect = node.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      onPointerMove?.(event);
      return;
    }

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      onPointerMove?.(event);
      return;
    }
    const percentX = clamp((100 / rect.width) * x, 0, 100);
    const percentY = clamp((100 / rect.height) * y, 0, 100);

    const dx = x - rect.width / 2;
    const dy = y - rect.height / 2;
    const pointerAngle = angleFromPointer(dx, dy);
    const pointerDistance = edgeDistance(rect, x, y);

    node.style.setProperty("--pointer-x", `${round(percentX)}%`);
    node.style.setProperty("--pointer-y", `${round(percentY)}%`);
    node.style.setProperty("--pointer-deg", `${round(pointerAngle)}deg`);
    node.style.setProperty("--pointer-d", `${round(pointerDistance * 100)}`);

    if (animatingRef.current) {
      stopIntroAnimation();
    }

    onPointerMove?.(event);
  };

  const handlePointerLeave = (event: PointerEvent<HTMLDivElement>) => {
    const node = nodeRef.current;
    if (node) {
      node.style.setProperty("--pointer-d", "0");
    }
    onPointerLeave?.(event);
  };

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return;
    }

    if (!introAnimation || shouldReduceMotion()) {
      return;
    }

    animatingRef.current = true;
    setAnimating(true);
    node.style.setProperty("--pointer-d", "0");
    node.style.setProperty("--pointer-deg", "110deg");

    const angleStart = 110;
    const angleEnd = 465;
    const durationMs = 4500;
    const startTime = performance.now();

    const animate = (now: number) => {
      if (!animatingRef.current || !nodeRef.current) {
        return;
      }

      const elapsed = now - startTime;
      const currentNode = nodeRef.current;

      if (elapsed > 500 && elapsed < 1000) {
        const t = (elapsed - 500) / 500;
        const easeOut = 1 - (1 - t) ** 3;
        currentNode.style.setProperty("--pointer-d", `${round(easeOut * 100)}`);
      }

      if (elapsed > 500 && elapsed < 2000) {
        const t = (elapsed - 500) / 1500;
        const easeIn = t ** 3;
        const value = (angleEnd - angleStart) * (easeIn * 0.5) + angleStart;
        currentNode.style.setProperty("--pointer-deg", `${round(value)}deg`);
      }

      if (elapsed >= 2000 && elapsed < 4250) {
        const t = (elapsed - 2000) / 2250;
        const easeOut = 1 - (1 - t) ** 3;
        const value = (angleEnd - angleStart) * (0.5 + easeOut * 0.5) + angleStart;
        currentNode.style.setProperty("--pointer-deg", `${round(value)}deg`);
      }

      if (elapsed > 3000 && elapsed < durationMs) {
        const t = (elapsed - 3000) / 1500;
        const easeIn = t ** 3;
        currentNode.style.setProperty("--pointer-d", `${round((1 - easeIn) * 100)}`);
      }

      if (elapsed < durationMs) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        stopIntroAnimation();
      }
    };

    delayRef.current = window.setTimeout(() => {
      rafRef.current = requestAnimationFrame(animate);
    }, 450);

    return () => {
      animatingRef.current = false;
      setAnimating(false);
      if (delayRef.current !== null) {
        window.clearTimeout(delayRef.current);
        delayRef.current = null;
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [introAnimation]);

  const resolvedStyle = {
    ["--pointer-x" as string]: "50%",
    ["--pointer-y" as string]: "50%",
    ["--pointer-deg" as string]: "45deg",
    ["--pointer-d" as string]: "0",
    ...(style as CSSProperties),
  } as CSSProperties;

  return (
    <div
      ref={nodeRef}
      className={[
        "colored-edge-node",
        `mode-${mode}`,
        compact ? "compact" : "",
        animating ? "animating" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      style={resolvedStyle}
      {...props}
    >
      <div className="colored-edge-node-mesh-border" />
      <div className="colored-edge-node-mesh-bg" />
      <div className="colored-edge-node-glow" />
      <div className="colored-edge-node-content">{children}</div>
    </div>
  );
}

export default ColoredGlowingEdgeNode;
