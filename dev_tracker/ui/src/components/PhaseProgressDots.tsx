interface PhaseProgressDotsProps {
  phases: Array<{
    phase_number: number;
    title: string;
    phase_status: string;
    completion: number;
  }>;
  showLabels?: boolean;
}

interface StageProgressDotsProps {
  completed: number;
  total: number;
  percentLabel: string;
}

function resolvePhaseTone(status: string, index: number, currentOpenIndex: number) {
  if (status === "completed") {
    return "completed";
  }
  if (index === currentOpenIndex || currentOpenIndex < 0) {
    return "current";
  }
  return "pending";
}

export function PhaseProgressDots({ phases, showLabels = false }: PhaseProgressDotsProps) {
  const currentOpenIndex = phases.findIndex((phase) => phase.phase_status !== "completed");

  return (
    <div className="phase-progress-strip" role="img" aria-label="Phase progress overview">
      {phases.map((phase, index) => {
        const tone = resolvePhaseTone(phase.phase_status, index, currentOpenIndex);
        return (
          <div key={phase.phase_number} className={`phase-progress-dot ${tone}`.trim()} title={`Phase ${phase.phase_number}: ${phase.title}`}>
            <span className="phase-progress-dot-core" />
            {showLabels ? <span className="phase-progress-dot-label">{phase.phase_number}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

export function StageProgressDots({ completed, total, percentLabel }: StageProgressDotsProps) {
  const normalizedTotal = Math.max(total, 1);
  const clampedCompleted = Math.max(0, Math.min(completed, total));
  const currentIndex = clampedCompleted < total ? clampedCompleted : -1;

  return (
    <div className="stage-progress-group">
      <div className="stage-progress-strip" role="img" aria-label={`Stage progress ${completed} of ${total}`}>
        {Array.from({ length: normalizedTotal }, (_, index) => {
          const tone = index < clampedCompleted ? "completed" : index === currentIndex ? "current" : "pending";
          return <span key={`stage-${index + 1}`} className={`stage-progress-dot ${tone}`.trim()} aria-hidden="true" />;
        })}
      </div>
      <p className="stage-progress-percent">{percentLabel} complete</p>
    </div>
  );
}
