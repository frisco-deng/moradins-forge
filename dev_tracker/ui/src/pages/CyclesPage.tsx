import { PageHero } from "../components/PageHero";
import { RoutingSurfacesCard } from "../components/RoutingSurfacesCard";
import { ScrollSurface } from "../components/ScrollSurface";
import { StatusChip } from "../components/StatusChip";
import { StatusPillButton } from "../components/StatusPillButton";
import { TooltipHint } from "../components/TooltipHint";
import { useTracker } from "../lib/tracker-context";

export function CyclesPage() {
  const { snapshot, status } = useTracker();

  if (!snapshot) {
    return <div className="card card-pad">No cycle data available.</div>;
  }

  const loop = snapshot.loop_state;
  const gateStats = snapshot.human_gate_stats?.latest;
  const stagesRemaining = gateStats?.stages_remaining ?? Math.max(snapshot.phases.stage_count - snapshot.phases.stage_done_count, 0);
  const estimatedCyclesRemaining = gateStats?.estimated_cycles_remaining ?? snapshot.summary.estimated_cycles_remaining ?? stagesRemaining;
  const estimatedLoopsRemaining = gateStats?.estimated_loops_remaining ?? snapshot.summary.estimated_loops_remaining ?? 0;
  const pendingApprovals = gateStats?.pending_approvals ?? snapshot.changelog.awaiting_human_review_count;
  const pendingFeatures = gateStats?.pending_features ?? snapshot.current_features.pending_count;
  const archiveRows = snapshot.archive_register?.row_count ?? 0;

  return (
    <div className="page-grid">
      <PageHero
        title="Loop Processes"
        subtitle="Estimated loop runway, blockers, and execution readiness captured at cycle closeout."
        eyebrow="Loop Telemetry"
        chips={
          <>
            <StatusPillButton
              tone="warning"
              preferredWidth={280}
              popoverContent={() => (
                <div>
                  <p className="card-head" style={{ marginTop: 0 }}>Blocker Breakdown</p>
                  <p style={{ margin: "0.4rem 0 0" }}>Approvals: {pendingApprovals}</p>
                  <p style={{ margin: "0.2rem 0 0" }}>Pending Features: {pendingFeatures}</p>
                  <p style={{ margin: "0.2rem 0 0" }}>Capability Gaps: {snapshot.capability_gaps.open_count}</p>
                </div>
              )}
            >
              {`Gate Blockers ${pendingApprovals + pendingFeatures + snapshot.capability_gaps.open_count}`}
            </StatusPillButton>
            <StatusChip tone="info">{`Estimated cycles left ${estimatedCyclesRemaining}`}</StatusChip>
            <StatusChip tone="success">{`Archive rows ${archiveRows}`}</StatusChip>
          </>
        }
      >
        <div className="card card-pad" style={{ padding: "0.8rem" }}>
          <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <span>Quick Stats</span>
            <TooltipHint text="Human-gated loop process runway, blockers, and execution readiness telemetry." />
          </h3>
          <p className="metric-sub" style={{ marginBottom: 0 }}>
            Estimated loop runway and outstanding gates captured at cycle closeout.
          </p>
        </div>
      </PageHero>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <div style={{ display: "grid", gap: "0.8rem", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", marginTop: "0.8rem" }}>
          <div className="card card-pad">
            <p className="card-head">Estimated Cycles Left</p>
            <p className="metric">{estimatedCyclesRemaining}</p>
            <p className="metric-sub">from latest human-gate stats</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Estimated Loops Left</p>
            <p className="metric">{estimatedLoopsRemaining}</p>
            <p className="metric-sub">high-level objective loops</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Stages Remaining</p>
            <p className="metric">{stagesRemaining}</p>
            <p className="metric-sub">
              {snapshot.phases.stage_done_count}/{snapshot.phases.stage_count} done
            </p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Gate Blockers</p>
            <p className="metric">{pendingApprovals + pendingFeatures + snapshot.capability_gaps.open_count}</p>
            <p className="metric-sub">
              approvals {pendingApprovals} | features {pendingFeatures} | gaps {snapshot.capability_gaps.open_count}
            </p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Archive Coverage</p>
            <p className="metric">{archiveRows}</p>
            <p className="metric-sub">archive register rows</p>
          </div>
        </div>
      </section>

      <RoutingSurfacesCard
        links={[
          { to: "/reviews/exchange", label: "Activity: Approval Routing" },
          { to: "/help", label: "Help: Loop Playbooks" },
          { to: "/project-topology", label: "Project Topology" },
          { to: "/harness-topology", label: "Harness Topology" },
        ]}
        subtitle="Loop-process cross-links for approvals, routing, and artifact evidence."
      />

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h2 className="section-title">Agent Loop Process State</h2>
        <p className="section-subtitle">Planner/implementer cycle state with human continuation gate visibility.</p>
        <div
          className="cycles-loop-grid"
          style={{ display: "grid", gap: "0.8rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.8rem" }}
        >
          <div className="card card-pad">
            <p className="card-head">Run Count</p>
            <p className="metric">{loop.run_count}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Last Run</p>
            <p className="metric mono" style={{ fontSize: "1rem" }}>
              {loop.last_run_id}
            </p>
            <p className="metric-sub">{loop.last_result}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Next Action</p>
            <p className="metric" style={{ fontSize: "1rem" }}>
              {loop.next_action}
            </p>
            <p className="metric-sub">{gateStats?.reviewer_action_required ?? "review_required"}</p>
          </div>
          <div className="card card-pad">
            <p className="card-head">Sync Runtime</p>
            <p className="metric" style={{ fontSize: "1rem" }}>
              {status?.runtime_state.last_sync_result ?? "n/a"}
            </p>
            <p className="metric-sub">{status?.runtime_state.last_sync_at ?? "--"}</p>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <h3 style={{ marginTop: 0 }}>Cycle History</h3>
        <ScrollSurface className="effects-table-wrap">
        <table className="table effects-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Date</th>
              <th>Result</th>
              <th>Human Decision</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {loop.history.map((row) => (
              <tr key={row.run_id}>
                <td className="mono">{row.run_id}</td>
                <td>{row.date}</td>
                <td>{row.result}</td>
                <td>{row.human_decision}</td>
                <td style={{ whiteSpace: "normal", minWidth: "220px" }}>
                  {row.notes.length > 110 ? (
                    <StatusPillButton
                      tone="info"
                      preferredWidth={340}
                      popoverContent={<p style={{ margin: 0, lineHeight: 1.55 }}>{row.notes}</p>}
                    >
                      {`${row.notes.slice(0, 90)}...`}
                    </StatusPillButton>
                  ) : (
                    row.notes
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </ScrollSurface>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <h3 style={{ marginTop: 0 }}>Capability Register</h3>
        <div style={{ display: "grid", gap: "0.45rem" }}>
          <div>
            <StatusChip tone={snapshot.capability_gaps.open_count > 0 ? "warning" : "success"}>
              {`Open ${snapshot.capability_gaps.open_count}`}
            </StatusChip>
          </div>
          <div>
            <StatusChip tone={snapshot.capability_gaps.in_progress_count > 0 ? "info" : "success"}>
              {`In Progress ${snapshot.capability_gaps.in_progress_count}`}
            </StatusChip>
          </div>
          <div>
            <StatusChip tone={snapshot.capability_gaps.blocked_count > 0 ? "error" : "success"}>
              {`Blocked ${snapshot.capability_gaps.blocked_count}`}
            </StatusChip>
          </div>
        </div>

        <ScrollSurface className="effects-table-wrap" style={{ marginTop: "0.75rem" }}>
        <table className="table effects-table">
          <thead>
            <tr>
              <th>Gap</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.capability_gaps.rows.map((row) => (
              <tr key={row.gap_id}>
                <td className="mono">{row.gap_id}</td>
                <td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </ScrollSurface>
      </section>
    </div>
  );
}
