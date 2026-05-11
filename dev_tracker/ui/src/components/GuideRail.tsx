import { useEffect } from "react";
import { Link } from "react-router-dom";

import {
  GUIDE_ROUTE_STEPS,
  markGuideRouteVisited,
  nextGuideStep,
  setGuideCompleted,
  setGuideDismissed,
  type GuideRouteId,
} from "../lib/guide-flow";
import { useGuideState } from "../lib/use-guide-state";

interface GuideRailProps {
  currentRouteId: GuideRouteId;
}

export function GuideRail({ currentRouteId }: GuideRailProps) {
  const guideState = useGuideState();

  useEffect(() => {
    markGuideRouteVisited(currentRouteId);
  }, [currentRouteId]);

  const nextStep = nextGuideStep(currentRouteId);
  const allRouteStepsVisited = GUIDE_ROUTE_STEPS.every((step) => guideState.visited_route_ids.includes(step.id));
  const tutorialReadyToFinish = allRouteStepsVisited && guideState.example_flow_viewed;
  const progressSummary = guideState.completed
    ? "Tutorial completed. Reopen Quick Start any time for a guided refresher."
    : guideState.dismissed
      ? "Tutorial dismissed. Open Quick Start to resume the guided walkthrough."
      : "Keep the deploy path visible while moving between Quick Start, Deploy Map, Builder, and Verify.";

  return (
    <section className="guide-rail" style={{ gridColumn: "span 12" }}>
      <div className="guide-rail-head">
        <div>
          <p className="secondary-nav-breadcrumb">
            <span>Guided Path</span>
            <span>{guideState.completed ? "Finished" : "In Progress"}</span>
          </p>
          <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
            {progressSummary}
          </p>
        </div>
        <div className="guide-rail-actions">
          <Link to="/deploy/quick-start" className="btn" style={{ textDecoration: "none" }}>
            {guideState.completed ? "Review Tutorial" : "Continue Tutorial"}
          </Link>
          {!guideState.completed && nextStep ? (
            <Link to={nextStep.path} className="btn primary" style={{ textDecoration: "none" }}>
              Next: {nextStep.label}
            </Link>
          ) : null}
          {tutorialReadyToFinish && !guideState.completed ? (
            <button
              type="button"
              className="btn subtle"
              onClick={() => {
                setGuideCompleted(true);
                setGuideDismissed(true);
              }}
            >
              Remove Tutorial
            </button>
          ) : null}
        </div>
      </div>
      <div className="guide-rail-steps">
        {GUIDE_ROUTE_STEPS.map((step, index) => {
          const active = step.id === currentRouteId;
          const visited = guideState.visited_route_ids.includes(step.id);
          return (
            <Link
              key={step.id}
              to={step.path}
              className={`guide-rail-step ${active ? "active" : ""} ${visited ? "visited" : ""}`.trim()}
              style={{ textDecoration: "none" }}
            >
              <span className="guide-rail-step-index">{index + 1}</span>
              <span className="guide-rail-step-copy">
                <strong>{step.label}</strong>
                <span>{step.description}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
