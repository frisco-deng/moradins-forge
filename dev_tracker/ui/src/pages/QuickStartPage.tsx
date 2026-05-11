import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Monitor, Network, ServerCog, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";

import { PageHero } from "../components/PageHero";
import { ScrollSurface } from "../components/ScrollSurface";
import { SeededDeployExamplePanel } from "../components/SeededDeployExamplePanel";
import { StatusChip } from "../components/StatusChip";
import { getDocByPath } from "../lib/doc-helpers";
import {
  markGuideRouteVisited,
  markGuideTutorialStepCompleted,
  setGuideCompleted,
  setGuideDismissed,
  type GuideTutorialStepId,
} from "../lib/guide-flow";
import { useGuideState } from "../lib/use-guide-state";
import { useTracker } from "../lib/tracker-context";

function stripLeadingHeading(markdown: string) {
  return markdown.replace(/^#\s+Quick Start\s*\n+/u, "").trim();
}

const TUTORIAL_STEPS: Array<{
  id: GuideTutorialStepId;
  title: string;
  summary: string;
  targetId: string;
  targetLabel: string;
  actionLabel?: string;
  actionTo?: string;
}> = [
  {
    id: "quick-start",
    title: "Choose the operating mode",
    summary: "Start by confirming where the harness is running and how you will access it before touching any deploy action.",
    targetId: "tutorial-access",
    targetLabel: "Access mode",
  },
  {
    id: "deploy-map",
    title: "Understand the deploy map",
    summary: "Use the visual preflight explanation before opening Builder so the payload fill and sidecar model are clear.",
    targetId: "tutorial-map",
    targetLabel: "Deploy map",
    actionLabel: "Open Deploy Map",
    actionTo: "/deploy/map",
  },
  {
    id: "readiness",
    title: "Check readiness",
    summary: "Readiness records present tools, missing tools, install request artifacts, and repo registry state before deploy work.",
    targetId: "tutorial-readiness",
    targetLabel: "Readiness",
    actionLabel: "Open Readiness",
    actionTo: "/deploy/readiness",
  },
  {
    id: "builder",
    title: "Walk the Builder in order",
    summary: "Builder is the execution surface: target repo, project context, deploy harness, build project phases, and then run an explicit prompt.",
    targetId: "tutorial-builder",
    targetLabel: "Builder",
    actionLabel: "Open Builder",
    actionTo: "/deploy/builder",
  },
  {
    id: "system-status",
    title: "Verify before continuing",
    summary: "Use Verify as the canonical status page for what happened, what is missing, and what the next manual action should be.",
    targetId: "tutorial-verify",
    targetLabel: "Verify",
    actionLabel: "Open Verify",
    actionTo: "/deploy/status",
  },
  {
    id: "deploy-example",
    title: "Review a safe deploy example",
    summary: "Walk through a seeded, non-executing example so you can see the Builder and Verify shape without deploying anything for real.",
    targetId: "tutorial-example",
    targetLabel: "Deploy example",
  },
];

function firstIncompleteStepIndex(completedStepIds: GuideTutorialStepId[]) {
  const nextIndex = TUTORIAL_STEPS.findIndex((step) => !completedStepIds.includes(step.id));
  return nextIndex >= 0 ? nextIndex : 0;
}

export function QuickStartPage() {
  const { snapshot, status, loading } = useTracker();
  const guideState = useGuideState();
  const prefersReducedMotion = useReducedMotion();
  const [runbookExpanded, setRunbookExpanded] = useState(false);
  const [tutorialOpen, setTutorialOpen] = useState(() => !guideState.dismissed && !guideState.completed);
  const [currentStepIndex, setCurrentStepIndex] = useState(() => firstIncompleteStepIndex(guideState.completed_tutorial_step_ids));

  const quickStartDoc = snapshot ? getDocByPath(snapshot, "docs/11_ops/quick_start.md") : null;
  const quickStartMarkdown = stripLeadingHeading(quickStartDoc?.content ?? "");
  const uiAccess = status?.ui_access;

  useEffect(() => {
    markGuideRouteVisited("quick-start");
  }, []);

  useEffect(() => {
    if (guideState.dismissed) {
      setTutorialOpen(false);
      return;
    }
    setCurrentStepIndex(firstIncompleteStepIndex(guideState.completed_tutorial_step_ids));
  }, [guideState.completed_tutorial_step_ids, guideState.dismissed]);

  const activeStep = TUTORIAL_STEPS[currentStepIndex] ?? TUTORIAL_STEPS[0]!;
  const tutorialReadyToFinish = TUTORIAL_STEPS.every((step) => guideState.completed_tutorial_step_ids.includes(step.id));

  if (loading && !snapshot) {
    return (
      <div className="page-grid">
        <section className="card card-pad route-skeleton-card" style={{ gridColumn: "span 12" }}>
          <div className="route-skeleton-line wide" />
          <div className="route-skeleton-line medium" />
          <div className="route-skeleton-grid">
            <div className="route-skeleton-block" />
            <div className="route-skeleton-block" />
            <div className="route-skeleton-block" />
          </div>
        </section>
      </div>
    );
  }

  if (!snapshot) {
    return <div className="card card-pad">No quick-start context available.</div>;
  }

  function startTutorial() {
    if (guideState.completed) {
      setGuideCompleted(false);
    }
    setGuideDismissed(false);
    setTutorialOpen(true);
    setCurrentStepIndex(guideState.completed ? 0 : firstIncompleteStepIndex(guideState.completed_tutorial_step_ids));
  }

  function dismissTutorial() {
    setGuideDismissed(true);
    setTutorialOpen(false);
  }

  function advanceTutorial() {
    markGuideTutorialStepCompleted(activeStep.id);
    if (currentStepIndex >= TUTORIAL_STEPS.length - 1) {
      setGuideCompleted(true);
      setGuideDismissed(true);
      setTutorialOpen(false);
      return;
    }
    setCurrentStepIndex((index) => Math.min(index + 1, TUTORIAL_STEPS.length - 1));
  }

  return (
    <div className={`page-grid quick-start-page ${tutorialOpen ? "tutorial-active" : ""}`.trim()}>
      {tutorialOpen ? <div className="tutorial-backdrop" aria-hidden="true" /> : null}
      <AnimatePresence>
        {tutorialOpen ? (
          <motion.aside
            className="tutorial-overlay"
            initial={prefersReducedMotion ? false : { opacity: 0, y: 18 }}
            animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
            exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: 18 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
          >
            <div className="tutorial-overlay-head">
              <div>
                <p className="card-head">Focused Tutorial</p>
                <h3 style={{ marginTop: "0.3rem", marginBottom: "0.3rem" }}>{activeStep.title}</h3>
                <p className="metric-sub" style={{ margin: 0 }}>
                  {activeStep.summary}
                </p>
              </div>
              <button className="icon-btn" type="button" aria-label="Dismiss tutorial" onClick={dismissTutorial}>
                <X size={16} />
              </button>
            </div>

            <div className="tutorial-overlay-progress" aria-label="Tutorial progress">
              {TUTORIAL_STEPS.map((step, index) => {
                const completed = guideState.completed_tutorial_step_ids.includes(step.id);
                const active = index === currentStepIndex;
                return (
                  <button
                    key={step.id}
                    type="button"
                    className={`tutorial-progress-dot ${active ? "active" : ""} ${completed ? "complete" : ""}`.trim()}
                    onClick={() => setCurrentStepIndex(index)}
                    aria-label={`Open tutorial step ${index + 1}: ${step.targetLabel}`}
                  />
                );
              })}
            </div>

            <div className="tutorial-overlay-card">
              <p className="metric-sub" style={{ marginTop: 0 }}>
                Focus area: <strong>{activeStep.targetLabel}</strong>
              </p>
              <p className="metric-sub" style={{ marginBottom: 0 }}>
                Use the highlighted section below. Keep the route quiet, review the example when you need it, and only jump to the next page when you understand the purpose of the step.
              </p>
            </div>

            <div className="tutorial-overlay-actions">
              <button className="btn" type="button" onClick={() => setCurrentStepIndex((index) => Math.max(index - 1, 0))} disabled={currentStepIndex === 0}>
                Back
              </button>
              {activeStep.actionLabel && activeStep.actionTo ? (
                <Link className="btn" to={activeStep.actionTo} style={{ textDecoration: "none" }}>
                  {activeStep.actionLabel}
                </Link>
              ) : null}
              <button className="btn primary" type="button" onClick={advanceTutorial}>
                {currentStepIndex >= TUTORIAL_STEPS.length - 1 ? "Finish Tutorial" : "Next Focus"}
              </button>
            </div>
          </motion.aside>
        ) : null}
      </AnimatePresence>

      <PageHero
        title="Quick Start"
        subtitle="Guided first-run onboarding for the current deploy flow. Learn the route order, preview a safe example, and keep the longer runbook as secondary help."
        eyebrow="Guided Setup"
        chips={
          <>
            <StatusChip tone="info">Linux-hosted companion</StatusChip>
            <StatusChip tone="success">Guided deploy path</StatusChip>
            <StatusChip tone={guideState.completed ? "success" : guideState.dismissed ? "info" : "warning"}>
              {guideState.completed ? "tutorial finished" : guideState.dismissed ? "tutorial dismissed" : "tutorial active"}
            </StatusChip>
          </>
        }
        actions={
          <>
            <button className="btn primary" type="button" onClick={startTutorial}>
              {guideState.completed ? "Review Tutorial" : guideState.dismissed ? "Resume Tutorial" : "Continue Tutorial"}
            </button>
            <Link className="btn" to="/deploy/map" style={{ textDecoration: "none" }}>
              Open Deploy Map
            </Link>
          </>
        }
      >
        <div className="page-hero-inline-grid">
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Execution Host</p>
            <p style={{ margin: "0.35rem 0 0" }}>{uiAccess?.execution_host_summary ?? "Assistant commands run on the Linux host that launched the harness."}</p>
          </div>
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Browser Access</p>
            <p style={{ margin: "0.35rem 0 0" }}>{uiAccess?.browser_access_summary ?? "Use localhost, WSL browser access, or SSH local port forwarding."}</p>
          </div>
          <div className="card card-pad page-hero-inline-card">
            <p className="card-head">Suggested Path</p>
            <p style={{ margin: "0.35rem 0 0" }}>Quick Start → Readiness → Deploy Map → Builder → Verify</p>
          </div>
        </div>
      </PageHero>

      <section
        id="tutorial-access"
        className={`card card-pad tutorial-scene ${tutorialOpen && activeStep.targetId === "tutorial-access" ? "spotlight" : ""}`.trim()}
        style={{ gridColumn: "span 12" }}
      >
        <div className="quick-start-guide-head">
          <div>
            <p className="card-head">Access Mode</p>
            <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Start with host and browser access, not execution.</h3>
            <p className="metric-sub" style={{ margin: 0 }}>
              Confirm the host, browser path, and tunnel setup before walking into Deploy Map or Builder.
            </p>
          </div>
          <Sparkles size={22} style={{ color: "var(--cyan)" }} />
        </div>
        <div className="guide-callout-grid" style={{ marginTop: "0.9rem" }}>
          <article className="guide-callout-card">
            <Monitor size={20} />
            <strong>Linux Local</strong>
            <p>Run `./harness_devops.sh --port 5273` and browse on `localhost`.</p>
          </article>
          <article className="guide-callout-card">
            <Network size={20} />
            <strong>WSL</strong>
            <p>Launch in WSL, then use `localhost` from Windows first and fall back to the WSL IPv4 address if needed.</p>
          </article>
          <article className="guide-callout-card">
            <ServerCog size={20} />
            <strong>Remote Linux</strong>
            <p>Keep the UI loopback-only and use `ssh -L 5273:127.0.0.1:5273 &lt;linux-host&gt;`.</p>
          </article>
        </div>
      </section>

      <section className="quick-start-stage-grid" style={{ gridColumn: "span 12" }}>
        <article
          id="tutorial-readiness"
          className={`card card-pad tutorial-scene tutorial-stage-card ${tutorialOpen && activeStep.targetId === "tutorial-readiness" ? "spotlight" : ""}`.trim()}
        >
          <p className="card-head">Step 2</p>
          <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Readiness</h3>
          <p className="metric-sub" style={{ margin: 0 }}>
            Host tooling checks, request-only install artifacts, and repo registry state.
          </p>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
            <StatusChip tone="info">request only</StatusChip>
            <StatusChip tone="warning">missing tools</StatusChip>
            <StatusChip tone="success">repo registry</StatusChip>
          </div>
          <Link className="btn" to="/deploy/readiness" style={{ marginTop: "0.9rem", textDecoration: "none" }}>
            Open Readiness
          </Link>
        </article>

        <article
          id="tutorial-map"
          className={`card card-pad tutorial-scene tutorial-stage-card ${tutorialOpen && activeStep.targetId === "tutorial-map" ? "spotlight" : ""}`.trim()}
        >
          <p className="card-head">Step 3</p>
          <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Deploy Map</h3>
          <p className="metric-sub" style={{ margin: 0 }}>
            Visual explanation layer for fill sources, guarded writes, and latest captured output.
          </p>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
            <StatusChip tone="info">Moradin payload</StatusChip>
            <StatusChip tone="success">profile overlay</StatusChip>
            <StatusChip tone="warning">user filled</StatusChip>
            <StatusChip tone="error">scan derived</StatusChip>
          </div>
          <Link className="btn" to="/deploy/map" style={{ marginTop: "0.9rem", textDecoration: "none" }}>
            Open Deploy Map
          </Link>
        </article>

        <article
          id="tutorial-builder"
          className={`card card-pad tutorial-scene tutorial-stage-card ${tutorialOpen && activeStep.targetId === "tutorial-builder" ? "spotlight" : ""}`.trim()}
        >
          <p className="card-head">Step 4</p>
          <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Builder</h3>
          <p className="metric-sub" style={{ margin: 0 }}>
            Target repo, project context, deploy harness, build phases, then run an explicit prompt.
          </p>
          <div className="quick-start-stage-list">
            <span>1. Target repo</span>
            <span>2. Project context</span>
            <span>3. Deploy harness</span>
            <span>4. Build project phases</span>
            <span>5. Run phase prompt</span>
          </div>
          <Link className="btn" to="/deploy/builder" style={{ marginTop: "0.9rem", textDecoration: "none" }}>
            Open Builder
          </Link>
        </article>

        <article
          id="tutorial-verify"
          className={`card card-pad tutorial-scene tutorial-stage-card ${tutorialOpen && activeStep.targetId === "tutorial-verify" ? "spotlight" : ""}`.trim()}
        >
          <p className="card-head">Step 5</p>
          <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Verify</h3>
          <p className="metric-sub" style={{ margin: 0 }}>
            Canonical status page for approval state, alignment gaps, action queue, and the next manual action.
          </p>
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
            <StatusChip tone="warning">approval visible</StatusChip>
            <StatusChip tone="warning">alignment gaps</StatusChip>
            <StatusChip tone="info">next action</StatusChip>
          </div>
          <Link className="btn" to="/deploy/status" style={{ marginTop: "0.9rem", textDecoration: "none" }}>
            Open Verify
          </Link>
        </article>
      </section>

      <section
        id="tutorial-example"
        className={`tutorial-scene ${tutorialOpen && activeStep.targetId === "tutorial-example" ? "spotlight" : ""}`.trim()}
        style={{ gridColumn: "span 12" }}
      >
        <SeededDeployExamplePanel surface="quick-start" />
      </section>

      <section className="card card-pad quick-start-runbook-card" style={{ gridColumn: "span 12" }}>
        <div className="quick-start-guide-head">
          <div>
            <p className="card-head">Runbook Content</p>
            <h3 style={{ marginTop: "0.35rem", marginBottom: "0.35rem" }}>Long-form operator detail</h3>
            <p className="metric-sub" style={{ margin: 0 }}>
              Keep the runbook as secondary help. Use it when you need the detail, not as the first-run primary experience.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button className="btn" type="button" onClick={() => setRunbookExpanded((value) => !value)}>
              {runbookExpanded ? "Collapse Runbook" : "Expand Runbook"}
            </button>
            {quickStartDoc ? (
              <Link to={`/docs/${quickStartDoc.id}`} className="btn" style={{ textDecoration: "none" }}>
                Open Raw Doc
              </Link>
            ) : null}
          </div>
        </div>
        {runbookExpanded ? (
          <ScrollSurface className="quick-start-runbook markdown">
            <article>
              <ReactMarkdown>{quickStartMarkdown}</ReactMarkdown>
            </article>
          </ScrollSurface>
        ) : (
          <p className="metric-sub" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
            Expand the runbook when you need the exact Markdown instructions, host notes, or operational detail.
          </p>
        )}
      </section>

      {tutorialReadyToFinish && !guideState.completed && !tutorialOpen ? (
        <section className="card card-pad" style={{ gridColumn: "span 12" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.9rem", flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <p className="card-head">Tutorial Ready To Close</p>
              <p className="metric-sub" style={{ margin: "0.35rem 0 0" }}>
                Every guided card has been reviewed. Remove the tutorial when you are ready to operate the deploy flow without it.
              </p>
            </div>
            <button
              className="btn primary"
              type="button"
              onClick={() => {
                setGuideCompleted(true);
                setGuideDismissed(true);
              }}
            >
              Remove Tutorial
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
