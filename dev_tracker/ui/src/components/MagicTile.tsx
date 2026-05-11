import { useMemo, useState, type CSSProperties, type MouseEvent, type PropsWithChildren } from "react";

interface Props extends PropsWithChildren {
  className?: string;
  reducedMotion?: boolean;
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

export function MagicTile({ children, className = "", reducedMotion = false }: Props) {
  const [style, setStyle] = useState<CSSProperties>({});

  const handlers = useMemo(() => {
    if (reducedMotion) {
      return {
        onMouseMove: undefined,
        onMouseLeave: undefined,
      };
    }

    return {
      onMouseMove: (event: MouseEvent<HTMLElement>) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) * 100;
        const y = ((event.clientY - rect.top) / rect.height) * 100;
        const rotateX = ((y - 50) / 50) * -3;
        const rotateY = ((x - 50) / 50) * 3;
        const localX = event.clientX - rect.left;
        const localY = event.clientY - rect.top;
        const dx = localX - rect.width / 2;
        const dy = localY - rect.height / 2;
        const pointerAngle = angleFromPointer(dx, dy);
        const pointerDistance = edgeDistance(rect, localX, localY) * 100;

        setStyle({
          transform: `perspective(850px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg)`,
          ["--mx" as string]: `${x.toFixed(1)}%`,
          ["--my" as string]: `${y.toFixed(1)}%`,
          ["--pointer-x" as string]: `${round(x)}%`,
          ["--pointer-y" as string]: `${round(y)}%`,
          ["--pointer-deg" as string]: `${round(pointerAngle)}deg`,
          ["--pointer-d" as string]: `${round(pointerDistance)}`,
        });
      },
      onMouseLeave: () => {
        setStyle({
          transform: "perspective(850px) rotateX(0deg) rotateY(0deg)",
          ["--pointer-d" as string]: "0",
        });
      },
    };
  }, [reducedMotion]);

  return (
    <article className={`magic-tile ${className}`} style={style} {...handlers}>
      <div className="magic-tile-content">{children}</div>
    </article>
  );
}
