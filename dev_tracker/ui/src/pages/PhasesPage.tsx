import { PageHero } from "../components/PageHero";
import { StatusChip } from "../components/StatusChip";
import { formatPercent } from "../lib/loaders";
import { useTracker } from "../lib/tracker-context";

export function PhasesPage() {
  const { snapshot } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No phase data available.</div>;
  }

  return (
    <div className="page-grid">
      <PageHero
        title="Phases"
        subtitle="Phase and stage backlog parsed from implementation phases with checklist-level completion and done-when criteria."
        eyebrow="Execution Plan"
      />

      {snapshot.phases.phases.map((phase) => (
        <section key={phase.phase_number} className="card card-pad" style={{ gridColumn: "span 12" }}>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: "0.6rem" }}>
            <div>
              <h3 style={{ margin: 0 }}>{`Phase ${phase.phase_number} — ${phase.title}`}</h3>
              <p className="muted" style={{ margin: "0.2rem 0 0" }}>
                {phase.checklist_done}/{phase.checklist_total} tasks complete ({formatPercent(phase.completion)})
              </p>
            </div>
            <div>
              {phase.phase_status === "completed" ? (
                <StatusChip tone="success">Completed</StatusChip>
              ) : phase.phase_status === "pending" ? (
                <StatusChip tone="info">Pending</StatusChip>
              ) : (
                <StatusChip tone="warning">{phase.phase_status}</StatusChip>
              )}
            </div>
          </div>

          <div style={{ marginTop: "0.75rem", height: "8px", borderRadius: "999px", background: "rgba(255,255,255,0.08)" }}>
            <div
              style={{
                width: `${Math.round(phase.completion * 100)}%`,
                height: "100%",
                borderRadius: "999px",
                background: "linear-gradient(90deg, rgba(59,130,246,0.95), rgba(34,211,238,0.95))",
              }}
            />
          </div>

          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.9rem", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {phase.stages.map((stage) => (
              <article key={stage.stage_id} className="card card-pad" style={{ padding: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                  <strong>{`Stage ${stage.stage_id}`}</strong>
                  {stage.is_complete ? <StatusChip tone="success">Done</StatusChip> : <StatusChip tone="warning">Open</StatusChip>}
                </div>
                <p style={{ margin: "0.3rem 0 0.45rem" }}>{stage.title}</p>
                <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
                  {stage.checklist_done}/{stage.checklist_total} complete
                </p>
                <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1rem" }}>
                  {stage.checklist.map((item) => (
                    <li key={item.text} className="muted" style={{ marginBottom: "0.24rem" }}>
                      {item.done ? "[x]" : "[ ]"} {item.text}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          {phase.done_when.length > 0 ? (
            <div style={{ marginTop: "0.8rem" }}>
              <p className="card-head" style={{ marginBottom: "0.4rem" }}>
                Done When
              </p>
              <ul style={{ margin: 0, paddingLeft: "1rem" }}>
                {phase.done_when.map((criterion) => (
                  <li key={criterion} className="muted">
                    {criterion}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}
