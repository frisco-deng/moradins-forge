import { useMemo, useRef, useState, type HTMLAttributes, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";

export interface GuideStepItem {
  id: string;
  title: string;
  summary?: string;
  content: ReactNode;
}

interface GuideStepperProps extends HTMLAttributes<HTMLDivElement> {
  steps: GuideStepItem[];
  initialStep?: number;
  onStepChange?: (stepIndex: number) => void;
  onComplete?: () => void;
  backButtonText?: string;
  nextButtonText?: string;
  completeButtonText?: string;
}

export function GuideStepper({
  steps,
  initialStep = 0,
  onStepChange,
  onComplete,
  backButtonText = "Back",
  nextButtonText = "Continue",
  completeButtonText = "Complete Guide",
  className = "",
  ...rest
}: GuideStepperProps) {
  const [currentIndex, setCurrentIndex] = useState(initialStep);
  const [direction, setDirection] = useState(0);
  const [contentHeight, setContentHeight] = useState<number | "auto">("auto");
  const completedRef = useRef(false);
  const currentStep = steps[currentIndex] ?? steps[0];
  const isLast = currentIndex >= steps.length - 1;

  const indicatorStatus = useMemo(
    () =>
      steps.map((_, index) => {
        if (index < currentIndex) {
          return "complete";
        }
        if (index === currentIndex) {
          return "active";
        }
        return "inactive";
      }),
    [currentIndex, steps],
  );

  function moveTo(index: number) {
    if (index < 0 || index >= steps.length) {
      return;
    }
    setCurrentIndex(index);
    onStepChange?.(index);
  }

  function handleBack() {
    if (currentIndex === 0) {
      return;
    }
    setDirection(-1);
    moveTo(currentIndex - 1);
  }

  function handleNext() {
    if (isLast) {
      if (!completedRef.current) {
        completedRef.current = true;
        onComplete?.();
      }
      return;
    }
    setDirection(1);
    moveTo(currentIndex + 1);
  }

  if (!currentStep) {
    return null;
  }

  return (
    <div className={`guide-stepper ${className}`.trim()} {...rest}>
      <div className="guide-stepper-indicators">
        {steps.map((step, index) => {
          const status = indicatorStatus[index];
          return (
            <div key={step.id} className="guide-stepper-indicator-wrap">
              <button
                type="button"
                className={`guide-stepper-indicator ${status}`.trim()}
                onClick={() => {
                  setDirection(index > currentIndex ? 1 : -1);
                  moveTo(index);
                }}
                aria-label={`Open guide step ${index + 1}: ${step.title}`}
              >
                {status === "complete" ? <Check size={16} /> : <span>{index + 1}</span>}
              </button>
              {index + 1 < steps.length ? <div className={`guide-stepper-connector ${index < currentIndex ? "complete" : ""}`.trim()} /> : null}
            </div>
          );
        })}
      </div>

      <motion.div className="guide-stepper-content-shell" animate={{ height: contentHeight }} transition={{ duration: 0.35, ease: "easeOut" }}>
        <AnimatePresence custom={direction} initial={false} mode="wait">
          <GuideStepPanel
            key={currentStep.id}
            step={currentStep}
            direction={direction}
            onMeasured={(height) => setContentHeight(height)}
          />
        </AnimatePresence>
      </motion.div>

      <div className="guide-stepper-footer">
        <div className="guide-stepper-footer-copy">
          <strong>{currentStep.title}</strong>
          {currentStep.summary ? <span>{currentStep.summary}</span> : null}
        </div>
        <div className="guide-stepper-actions">
          <button type="button" className="btn" onClick={handleBack} disabled={currentIndex === 0}>
            <ArrowLeft size={16} />
            <span>{backButtonText}</span>
          </button>
          <button type="button" className="btn primary" onClick={handleNext}>
            <span>{isLast ? completeButtonText : nextButtonText}</span>
            {!isLast ? <ArrowRight size={16} /> : null}
          </button>
        </div>
      </div>
    </div>
  );
}

function GuideStepPanel({
  step,
  direction,
  onMeasured,
}: {
  step: GuideStepItem;
  direction: number;
  onMeasured: (height: number) => void;
}) {
  return (
    <motion.div
      ref={(node) => {
        if (node) {
          requestAnimationFrame(() => onMeasured(node.offsetHeight));
        }
      }}
      custom={direction}
      variants={{
        enter: (dir: number) => ({
          x: dir >= 0 ? 26 : -26,
          opacity: 0,
        }),
        center: {
          x: 0,
          opacity: 1,
        },
        exit: (dir: number) => ({
          x: dir >= 0 ? -26 : 26,
          opacity: 0,
        }),
      }}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{
        x: { type: "spring", stiffness: 320, damping: 28 },
        opacity: { duration: 0.2 },
      }}
      className="guide-step-panel"
    >
      {step.content}
    </motion.div>
  );
}
