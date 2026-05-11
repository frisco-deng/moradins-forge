import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { gsap } from "gsap";

interface CardExpandPanelProps {
  id: string;
  isOpen: boolean;
  reducedMotion?: boolean;
  children: ReactNode;
}

function prefersReducedMotion() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function CardExpandPanel({ id, isOpen, reducedMotion = false, children }: CardExpandPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(isOpen);

  const disableAnimation = useMemo(() => reducedMotion || prefersReducedMotion(), [reducedMotion]);

  useEffect(() => {
    if (isOpen) {
      setMounted(true);
    }
  }, [isOpen]);

  useLayoutEffect(() => {
    const container = containerRef.current;
    const content = contentRef.current;

    if (!mounted || !container || !content) {
      return;
    }

    gsap.killTweensOf(container);

    if (disableAnimation) {
      container.style.height = isOpen ? "auto" : "0px";
      container.style.opacity = isOpen ? "1" : "0";
      if (!isOpen) {
        setMounted(false);
      }
      return;
    }

    const targetHeight = content.offsetHeight;
    const currentHeight = container.getBoundingClientRect().height;

    if (isOpen) {
      gsap.fromTo(
        container,
        {
          height: currentHeight > 0 ? currentHeight : 0,
          opacity: currentHeight > 0 ? 1 : 0,
        },
        {
          height: targetHeight,
          opacity: 1,
          duration: 0.52,
          ease: "power3.out",
          onComplete: () => {
            container.style.height = "auto";
          },
        },
      );
      return;
    }

    gsap.fromTo(
      container,
      {
        height: currentHeight > 0 ? currentHeight : targetHeight,
        opacity: 1,
      },
      {
        height: 0,
        opacity: 0,
        duration: 0.4,
        ease: "power3.out",
        onComplete: () => {
          setMounted(false);
        },
      },
    );
  }, [disableAnimation, isOpen, mounted, children]);

  useEffect(() => {
    return () => {
      if (containerRef.current) {
        gsap.killTweensOf(containerRef.current);
      }
    };
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <section id={id} role="region" aria-hidden={!isOpen} className="card-expand-panel-shell">
      <div ref={containerRef} className="card-expand-panel-animate">
        <div ref={contentRef} className="card-expand-panel-inner">
          {children}
        </div>
      </div>
    </section>
  );
}
