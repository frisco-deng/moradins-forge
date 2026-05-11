import { useEffect, useRef, useState, type CSSProperties, type HTMLAttributes, type MouseEvent } from "react";

export interface GlowingEdgeCardProps extends HTMLAttributes<HTMLDivElement> {
  mode?: "dark" | "light";
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

export function GlowingEdgeCard({ mode = "dark", className, children, ...props }: GlowingEdgeCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [animating, setAnimating] = useState(false);

  const handlePointerMove = (event: MouseEvent<HTMLDivElement>) => {
    const node = cardRef.current;
    if (!node) {
      return;
    }

    const rect = node.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
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

    if (animating) {
      setAnimating(false);
    }
  };

  const handlePointerLeave = () => {
    const node = cardRef.current;
    if (!node) {
      return;
    }
    node.style.setProperty("--pointer-d", "0");
  };

  useEffect(() => {
    const node = cardRef.current;
    if (!node) {
      return;
    }

    let cancelled = false;
    setAnimating(true);
    node.style.setProperty("--pointer-d", "0");
    node.style.setProperty("--pointer-deg", "130deg");

    const start = performance.now();
    const durationMs = 3900;

    const tick = (now: number) => {
      if (cancelled) {
        return;
      }
      const currentNode = cardRef.current;
      if (!currentNode) {
        return;
      }

      const elapsed = now - start;
      const progress = clamp(elapsed / durationMs, 0, 1);

      const angle = 130 + progress * 320;
      const fadeIn = clamp(elapsed / 1100, 0, 1);
      const fadeOut = clamp((durationMs - elapsed) / 1100, 0, 1);
      const distance = Math.min(fadeIn, fadeOut) * 100;

      currentNode.style.setProperty("--pointer-deg", `${round(angle)}deg`);
      currentNode.style.setProperty("--pointer-d", `${round(distance)}`);

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        setAnimating(false);
      }
    };

    const frame = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, []);

  const style = {
    ["--pointer-x" as string]: "50%",
    ["--pointer-y" as string]: "50%",
    ["--pointer-deg" as string]: "45deg",
    ["--pointer-d" as string]: "0",
  } as CSSProperties;

  return (
    <div
      ref={cardRef}
      className={["glow-card", `mode-${mode}`, animating ? "animating" : "", className ?? ""]
        .filter(Boolean)
        .join(" ")}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      style={style}
      {...props}
    >
      <div className="glow-card-mesh-border" />
      <div className="glow-card-mesh-bg" />
      <div className="glow-card-beam" />
      <div className="glow-card-content">{children}</div>
    </div>
  );
}

export default GlowingEdgeCard;
