import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { CardExpandPanel } from "./CardExpandPanel";
import "./CardExpandGrid.css";

export type CardExpandItem = {
  id: string;
  title: string;
  subtitle?: string;
  description?: string;
  image?: { src: string; alt: string };
  meta?: Array<{ label: string; value: string }>;
  actions?: Array<{ label: string; onClick?: () => void; href?: string }>;
  links?: Array<{ label: string; href: string; ariaLabel?: string }>;
};

interface CardExpandGridProps {
  items: CardExpandItem[];
  expandedId?: string;
  defaultExpandedId?: string;
  onExpandedChange?: (id: string | null) => void;
  columns?: { base: number; sm?: number; md?: number; lg?: number };
  renderCard?: (item: CardExpandItem) => ReactNode;
  renderExpanded?: (item: CardExpandItem) => ReactNode;
  collapseOnSecondClick?: boolean;
  className?: string;
  reducedMotion?: boolean;
  uniformCardHeights?: boolean;
}

interface BridgeMetrics {
  left: number;
  width: number;
  fullWidth: boolean;
}

const BREAKPOINTS = {
  sm: 640,
  md: 900,
  lg: 1200,
};

function clampIndex(value: number, max: number) {
  return Math.min(value, max);
}

function resolveColumnCount(
  width: number,
  columns: Required<Pick<NonNullable<CardExpandGridProps["columns"]>, "base">> & Partial<NonNullable<CardExpandGridProps["columns"]>>,
) {
  if (width >= BREAKPOINTS.lg && columns.lg) {
    return columns.lg;
  }
  if (width >= BREAKPOINTS.md && columns.md) {
    return columns.md;
  }
  if (width >= BREAKPOINTS.sm && columns.sm) {
    return columns.sm;
  }
  return columns.base;
}

function getRowEndIndex(index: number, columnCount: number, itemCount: number) {
  const rowEndIndex = index - (index % columnCount) + (columnCount - 1);
  return clampIndex(rowEndIndex, itemCount - 1);
}

function DefaultExpandedContent({ item }: { item: CardExpandItem }) {
  return (
    <div className="card-expand-default-content">
      <h4>{item.title}</h4>
      {item.subtitle ? <p className="muted">{item.subtitle}</p> : null}
      {item.description ? <p>{item.description}</p> : null}

      {item.image ? (
        <figure className="card-expand-image">
          <img src={item.image.src} alt={item.image.alt} loading="lazy" />
        </figure>
      ) : null}

      {item.meta && item.meta.length > 0 ? (
        <dl className="card-expand-meta">
          {item.meta.map((entry) => (
            <Fragment key={`${item.id}-${entry.label}-${entry.value}`}>
              <dt>{entry.label}</dt>
              <dd>{entry.value}</dd>
            </Fragment>
          ))}
        </dl>
      ) : null}

      {item.links && item.links.length > 0 ? (
        <div className="card-expand-links">
          {item.links.map((link) => (
            <a key={`${item.id}-${link.href}-${link.label}`} href={link.href} aria-label={link.ariaLabel ?? link.label}>
              {link.label}
            </a>
          ))}
        </div>
      ) : null}

      {item.actions && item.actions.length > 0 ? (
        <div className="card-expand-actions">
          {item.actions.map((action) => {
            if (action.href) {
              return (
                <a key={`${item.id}-${action.label}-${action.href}`} href={action.href} className="btn">
                  {action.label}
                </a>
              );
            }
            return (
              <button key={`${item.id}-${action.label}`} type="button" className="btn" onClick={action.onClick}>
                {action.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function CardExpandGrid({
  items,
  expandedId: controlledExpandedId,
  defaultExpandedId,
  onExpandedChange,
  columns = { base: 1, sm: 2, md: 3, lg: 4 },
  renderCard,
  renderExpanded,
  collapseOnSecondClick = true,
  className = "",
  reducedMotion = false,
  uniformCardHeights = false,
}: CardExpandGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(() => {
    if (typeof window === "undefined") {
      return BREAKPOINTS.lg;
    }
    return window.innerWidth;
  });
  const [uncontrolledExpandedId, setUncontrolledExpandedId] = useState<string | null>(defaultExpandedId ?? null);
  const [uniformHeight, setUniformHeight] = useState(0);
  const [bridgeMetrics, setBridgeMetrics] = useState<BridgeMetrics | null>(null);

  const isControlled = controlledExpandedId !== undefined;
  const expandedId = isControlled ? controlledExpandedId ?? null : uncontrolledExpandedId;

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useLayoutEffect(() => {
    if (!uniformCardHeights) {
      setUniformHeight(0);
      return;
    }

    const root = containerRef.current;
    if (!root) {
      return;
    }

    const triggers = Array.from(root.querySelectorAll<HTMLButtonElement>(".card-expand-trigger"));
    if (triggers.length === 0) {
      setUniformHeight(0);
      return;
    }

    const maxHeight = Math.ceil(
      triggers.reduce((max, trigger) => Math.max(max, trigger.getBoundingClientRect().height), 0),
    );
    setUniformHeight((previous) => (previous === maxHeight ? previous : maxHeight));
  }, [expandedId, items, uniformCardHeights, viewportWidth]);

  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root || !expandedId) {
      setBridgeMetrics(null);
      return;
    }

    const activeTrigger = root.querySelector<HTMLButtonElement>(`.card-expand-trigger[data-item-id="${expandedId}"]`);
    if (!activeTrigger) {
      setBridgeMetrics(null);
      return;
    }

    if (viewportWidth < BREAKPOINTS.sm) {
      setBridgeMetrics({ left: 0, width: root.clientWidth, fullWidth: true });
      return;
    }

    const rootRect = root.getBoundingClientRect();
    const triggerRect = activeTrigger.getBoundingClientRect();
    setBridgeMetrics({
      left: Math.max(triggerRect.left - rootRect.left, 0),
      width: triggerRect.width,
      fullWidth: false,
    });
  }, [expandedId, viewportWidth]);

  const columnCount = resolveColumnCount(viewportWidth, columns);
  const expandedIndex = useMemo(() => items.findIndex((item) => item.id === expandedId), [items, expandedId]);
  const expandedItem = expandedIndex >= 0 ? items[expandedIndex] : null;
  const insertPanelAfterIndex = expandedIndex >= 0 ? getRowEndIndex(expandedIndex, columnCount, items.length) : -1;

  const setExpanded = (next: string | null) => {
    if (!isControlled) {
      setUncontrolledExpandedId(next);
    }
    onExpandedChange?.(next);
  };

  const toggleExpanded = (itemId: string) => {
    if (expandedId === itemId) {
      if (collapseOnSecondClick) {
        setExpanded(null);
      }
      return;
    }
    setExpanded(itemId);
  };

  const style = {
    ["--ceg-cols-base" as string]: String(columns.base),
    ["--ceg-cols-sm" as string]: String(columns.sm ?? columns.base),
    ["--ceg-cols-md" as string]: String(columns.md ?? columns.sm ?? columns.base),
    ["--ceg-cols-lg" as string]: String(columns.lg ?? columns.md ?? columns.sm ?? columns.base),
    ...(uniformCardHeights && uniformHeight > 0
      ? {
          ["--ceg-trigger-min-h" as string]: `${uniformHeight}px`,
        }
      : {}),
  };

  return (
    <div ref={containerRef} className={`card-expand-grid ${className}`.trim()} style={style}>
      {items.map((item, index) => {
        const panelId = `card-expand-panel-${item.id}`;
        const active = expandedId === item.id;

        return (
          <Fragment key={item.id}>
            <button
              type="button"
              className={`card-expand-trigger ${uniformCardHeights ? "uniform-height" : ""} ${active ? "active" : ""}`.trim()}
              data-item-id={item.id}
              aria-expanded={active}
              aria-controls={panelId}
              onClick={() => toggleExpanded(item.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  toggleExpanded(item.id);
                }
              }}
            >
              {renderCard ? (
                renderCard(item)
              ) : (
                <>
                  <p className="card-head">{item.subtitle ?? "Flow Step"}</p>
                  <h4>{item.title}</h4>
                  {item.description ? <p className="muted">{item.description}</p> : null}
                </>
              )}
            </button>

            {expandedItem && index === insertPanelAfterIndex ? (
              <div
                className={`card-expand-panel-slot ${bridgeMetrics?.fullWidth ? "full-width-bridge" : ""}`.trim()}
                style={
                  bridgeMetrics
                    ? {
                        ["--ceg-bridge-left" as string]: `${bridgeMetrics.left}px`,
                        ["--ceg-bridge-width" as string]: `${bridgeMetrics.width}px`,
                      }
                    : undefined
                }
              >
                <CardExpandPanel id={`card-expand-panel-${expandedItem.id}`} isOpen reducedMotion={reducedMotion}>
                  <article className="card-expand-panel card card-pad">
                    <div className="card-expand-panel-toolbar">
                      <p className="card-head">Expanded Flow Detail</p>
                      <button type="button" className="btn card-expand-close" onClick={() => setExpanded(null)}>
                        Close
                      </button>
                    </div>
                    {renderExpanded ? renderExpanded(expandedItem) : <DefaultExpandedContent item={expandedItem} />}
                  </article>
                </CardExpandPanel>
              </div>
            ) : null}
          </Fragment>
        );
      })}
    </div>
  );
}
