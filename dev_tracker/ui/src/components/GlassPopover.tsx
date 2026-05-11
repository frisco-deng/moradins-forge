import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type PopoverAlign = "start" | "center" | "end";

interface GlassPopoverProps {
  trigger: ReactNode;
  children: ReactNode | ((controls: { close: () => void }) => ReactNode);
  ariaLabel: string;
  triggerClassName?: string;
  panelClassName?: string;
  preferredWidth?: number;
  align?: PopoverAlign;
  openOnHover?: boolean;
}

interface PanelPosition {
  top: number;
  left: number;
  width: number;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function GlassPopover({
  trigger,
  children,
  ariaLabel,
  triggerClassName = "",
  panelClassName = "",
  preferredWidth = 320,
  align = "center",
  openOnHover = false,
}: GlassPopoverProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<number | null>(null);
  const wasOpenRef = useRef(false);
  const popoverId = useId();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PanelPosition | null>(null);
  const panelContent = useMemo(
    () => (typeof children === "function" ? children({ close: () => setOpen(false) }) : children),
    [children],
  );

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
      const width = Math.min(preferredWidth, viewportWidth - 24);
      const anchorX =
        align === "start" ? rect.left : align === "end" ? rect.right - width : rect.left + rect.width / 2 - width / 2;
      const left = clamp(anchorX, 12, viewportWidth - width - 12);
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
  }, [align, open, preferredWidth]);

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
    if (!open && wasOpenRef.current) {
      triggerRef.current?.focus();
    }
    wasOpenRef.current = open;
  }, [open]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  const scheduleClose = () => {
    if (!openOnHover) {
      return;
    }
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 120);
  };

  const cancelScheduledClose = () => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        aria-label={ariaLabel}
        className={triggerClassName}
        onClick={() => {
          cancelScheduledClose();
          setOpen((previous) => !previous);
        }}
        onMouseEnter={() => {
          if (!openOnHover) {
            return;
          }
          cancelScheduledClose();
          setOpen(true);
        }}
        onMouseLeave={scheduleClose}
      >
        {trigger}
      </button>
      {open && position && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={panelRef}
              id={popoverId}
              role="dialog"
              aria-modal="false"
              className={`glass-popover-panel ${panelClassName}`.trim()}
              style={{
                position: "fixed",
                top: position.top,
                left: position.left,
                width: position.width,
              }}
              onMouseEnter={cancelScheduledClose}
              onMouseLeave={scheduleClose}
            >
              {panelContent}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
