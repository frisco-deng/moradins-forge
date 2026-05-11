import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

interface AttentionItem {
  label: string;
  to: string;
  detail?: string;
}

interface AttentionChipProps {
  label: string;
  summary: string;
  items?: AttentionItem[];
  tone?: "warning" | "error";
}

interface PanelPosition {
  top: number;
  left: number;
  width: number;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function AttentionChip({ label, summary, items = [], tone = "warning" }: AttentionChipProps) {
  const navigate = useNavigate();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const hoverOpenRef = useRef<number | null>(null);
  const hoverCloseRef = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PanelPosition | null>(null);
  const actionableItems = items.filter((item) => item.to.trim().length > 0);
  const hasMultipleItems = actionableItems.length > 1;

  useLayoutEffect(() => {
    if (!open || typeof window === "undefined") {
      return;
    }
    const updatePosition = () => {
      const triggerNode = triggerRef.current;
      if (!triggerNode) {
        return;
      }
      const rect = triggerNode.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const width = Math.min(340, viewportWidth - 24);
      const left = clamp(rect.left + rect.width / 2 - width / 2, 12, viewportWidth - width - 12);
      const top = rect.bottom + 12;
      setPosition({ top, left, width });
    };
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open || typeof document === "undefined") {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (target && (triggerRef.current?.contains(target) || panelRef.current?.contains(target))) {
        return;
      }
      setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    return () => {
      if (hoverOpenRef.current) {
        window.clearTimeout(hoverOpenRef.current);
      }
      if (hoverCloseRef.current) {
        window.clearTimeout(hoverCloseRef.current);
      }
    };
  }, []);

  const scheduleOpen = () => {
    if (hoverCloseRef.current) {
      window.clearTimeout(hoverCloseRef.current);
    }
    if (hoverOpenRef.current) {
      window.clearTimeout(hoverOpenRef.current);
    }
    hoverOpenRef.current = window.setTimeout(() => setOpen(true), 280);
  };

  const scheduleClose = () => {
    if (hoverOpenRef.current) {
      window.clearTimeout(hoverOpenRef.current);
    }
    if (hoverCloseRef.current) {
      window.clearTimeout(hoverCloseRef.current);
    }
    hoverCloseRef.current = window.setTimeout(() => setOpen(false), 150);
  };

  const cancelTimers = () => {
    if (hoverOpenRef.current) {
      window.clearTimeout(hoverOpenRef.current);
      hoverOpenRef.current = null;
    }
    if (hoverCloseRef.current) {
      window.clearTimeout(hoverCloseRef.current);
      hoverCloseRef.current = null;
    }
  };

  const onClick = () => {
    cancelTimers();
    if (actionableItems.length === 1) {
      void navigate(actionableItems[0]!.to);
      return;
    }
    setOpen((value) => !value);
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`chip attention-chip-trigger ${tone}`.trim()}
        onMouseEnter={scheduleOpen}
        onMouseLeave={scheduleClose}
        onFocus={() => setOpen(true)}
        onBlur={scheduleClose}
        onClick={onClick}
        aria-label={`${label}. ${summary}`}
      >
        {label}
      </button>
      {open && position && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={panelRef}
              className="glass-popover-panel attention-popover-panel"
              style={{ position: "fixed", top: position.top, left: position.left, width: position.width }}
              onMouseEnter={cancelTimers}
              onMouseLeave={scheduleClose}
            >
              <div className="attention-popover-copy">
                <p className="card-head" style={{ marginTop: 0 }}>
                  Attention Required
                </p>
                <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
                  {summary}
                </p>
                {actionableItems.length ? (
                  <div className="attention-popover-list">
                    {actionableItems.map((item) => (
                      <button
                        key={`${item.label}-${item.to}`}
                        type="button"
                        className="attention-popover-link"
                        onClick={() => {
                          setOpen(false);
                          void navigate(item.to);
                        }}
                      >
                        <strong>{item.label}</strong>
                        <small>{item.detail ?? item.to}</small>
                      </button>
                    ))}
                  </div>
                ) : null}
                {!actionableItems.length ? (
                  <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
                    No direct route is attached yet.
                  </p>
                ) : null}
                {actionableItems.length === 1 && !hasMultipleItems ? (
                  <p className="metric-sub" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
                    Click the pill to open the affected area directly.
                  </p>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
