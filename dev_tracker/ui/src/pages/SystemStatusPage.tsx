import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AssistantActionBar } from "../components/AssistantActionBar";
import { PageHero } from "../components/PageHero";
import { StatusChip } from "../components/StatusChip";
import { TooltipHint } from "../components/TooltipHint";
import { notifyAssistantRunStarted } from "../lib/assistant-activity";
import { executeRemoteSsh, runAssistantAction, testRemoteSsh } from "../lib/loaders";
import { buildRemoteListCommand, buildRemoteSidecarCheckCommand } from "../lib/remote-command-utils";
import { useTracker } from "../lib/tracker-context";

function buildSystemStatusPrompt(statusSummary: string): string {
  return [
    "Review the following Moradins Harness system status summary.",
    "Recommend the next operator actions in priority order.",
    "Keep the answer read-only and do not propose file edits.",
    "",
    statusSummary,
  ].join("\n");
}

export function SystemStatusPage() {
  const { snapshot, status, settings, syncNow, refreshData, refreshing } = useTracker();
  const [selectedProfileId, setSelectedProfileId] = useState(settings.defaultSshProfileId);
  const [remoteTargetRepo, setRemoteTargetRepo] = useState("");
  const [remoteSidecarDir, setRemoteSidecarDir] = useState(".moradins-harness");
  const [sshResult, setSshResult] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("");

  const qaSignals = snapshot?.qa_signals;
  const engineerGuardStatus = qaSignals?.engineer_entry_guard.status ?? "fail";
  const branchHygieneStatus = qaSignals?.branch_hygiene.status ?? "fail";
  const documentationReviewStatus = qaSignals?.documentation_review?.status ?? "fail";
  const queueZeroState =
    snapshot?.review_queue?.zero_state.updates &&
    snapshot?.review_queue?.zero_state.upgrades &&
    snapshot?.review_queue?.zero_state.tooling &&
    snapshot?.review_queue?.zero_state.suggestions;
  const builderFlags = status?.builder_feature_flags;
  const remoteSshStatus = status?.remote_ssh;
  const remoteSshEnabled = Boolean(remoteSshStatus?.feature_flag_enabled);
  const remoteCommandPrefixes = remoteSshStatus?.allowed_command_prefixes ?? [];
  const selectedProfile = settings.sshProfiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const assistantRuntime = status?.assistant_runtimes?.[settings.preferredAssistant] ?? null;
  const uiAccess = status?.ui_access;

  const systemSummary = useMemo(
    () =>
      [
        `last_sync_result=${status?.runtime_state.last_sync_result ?? "unknown"}`,
        `sync_count=${status?.runtime_state.sync_count ?? 0}`,
        `engineer_entry_guard=${engineerGuardStatus}`,
        `branch_hygiene=${branchHygieneStatus}`,
        `documentation_review=${documentationReviewStatus}`,
        `remote_ssh_enabled=${remoteSshEnabled ? "yes" : "no"}`,
        `queue_zero_state=${queueZeroState ? "yes" : "no"}`,
      ].join("\n"),
    [branchHygieneStatus, documentationReviewStatus, engineerGuardStatus, queueZeroState, remoteSshEnabled, status?.runtime_state.last_sync_result, status?.runtime_state.sync_count],
  );

  async function runRemoteAction(command: string) {
    if (!selectedProfile) {
      setSshResult("Select an SSH profile first.");
      return;
    }
    const response =
      command === "pwd"
        ? await testRemoteSsh({ target: selectedProfile })
        : await executeRemoteSsh({ target: selectedProfile, command });
    if (!response) {
      setSshResult("Remote SSH request failed.");
      return;
    }
    if ("detail" in response) {
      setSshResult(response.detail);
      return;
    }
    setSshResult([response.status, response.stdout.trim(), response.stderr.trim()].filter(Boolean).join(" | "));
  }

  async function onRunAssistant() {
    setAssistantBusy(true);
    setAssistantStatus("");
    const response = await runAssistantAction({
      assistant: settings.preferredAssistant,
      source_mode: "docs",
      execution_scope: "manager_repo",
      prompt: buildSystemStatusPrompt(systemSummary),
    });
    setAssistantBusy(false);
    if (!response) {
      setAssistantStatus("Assistant run failed.");
      return;
    }
    notifyAssistantRunStarted(response.run_id);
    setAssistantStatus(
      response.status === "queued" || response.status === "running"
        ? `${response.assistant} started. Follow progress in Assistant Activity.`
        : `${response.assistant} exit=${response.exit_code ?? "pending"} status=${response.status}`,
    );
  }

  return (
    <div className="page-grid">
      <PageHero
        title="System Status"
        subtitle="Operational diagnostics and connection checks before builder or deploy work starts."
        eyebrow="Runtime Readiness"
        chips={
          <>
            <StatusChip tone={engineerGuardStatus === "pass" ? "success" : "error"}>{`Engineer Guard ${engineerGuardStatus}`}</StatusChip>
            <StatusChip tone={branchHygieneStatus === "pass" ? "success" : "warning"}>{`Branch Hygiene ${branchHygieneStatus}`}</StatusChip>
            <StatusChip tone={remoteSshEnabled ? "success" : "warning"}>{remoteSshEnabled ? "SSH enabled" : "SSH disabled"}</StatusChip>
          </>
        }
        actions={
          <>
            <Link className="btn" to="/deploy/quick-start" style={{ textDecoration: "none" }}>
              Quick Start
            </Link>
            <Link className="btn" to="/deploy/map" style={{ textDecoration: "none" }}>
              Deploy Map
            </Link>
            <Link className="btn" to="/deploy/builder" style={{ textDecoration: "none" }}>
              Builder
            </Link>
          </>
        }
      >
        <div className="card card-pad" style={{ padding: "0.8rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <strong>Companion Runtime</strong>
            <TooltipHint text="Runtime health, guardrail enforcement, SSH reachability, and assistant-trigger controls for the harness control plane." />
          </div>
          <p className="metric-sub" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
            {uiAccess?.execution_host_summary ?? "Assistant commands run on the Linux host that launched this harness."}
          </p>
          <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
            {uiAccess?.browser_access_summary ?? "Open the web UI locally or through SSH local port forwarding."}
          </p>
        </div>
      </PageHero>

      <section className="card card-pad" style={{ gridColumn: "span 7" }}>
        <h3 style={{ marginTop: 0 }}>Control API Runtime</h3>
        <table className="table">
          <tbody>
            <tr>
              <th>Last Sync Result</th>
              <td>{status?.runtime_state.last_sync_result ?? "n/a"}</td>
            </tr>
            <tr>
              <th>Last Sync Time</th>
              <td>{status?.runtime_state.last_sync_at ?? "n/a"}</td>
            </tr>
            <tr>
              <th>Sync Duration</th>
              <td>{status?.runtime_state.last_sync_duration_ms ?? 0} ms</td>
            </tr>
            <tr>
              <th>Sync Count</th>
              <td>{status?.runtime_state.sync_count ?? 0}</td>
            </tr>
            <tr>
              <th>Last Error</th>
              <td>{status?.runtime_state.last_error || "none"}</td>
            </tr>
          </tbody>
        </table>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
          <button className="btn" type="button" onClick={() => void refreshData()} disabled={refreshing}>
            Refresh Snapshot
          </button>
          <button className="btn primary" type="button" onClick={() => void syncNow()} disabled={refreshing}>
            Manual Sync
          </button>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 5" }}>
        <h3 style={{ marginTop: 0 }}>Guardrails</h3>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          <div>
            <p className="card-head">Engineer Entry Guard</p>
            <StatusChip tone={engineerGuardStatus === "pass" ? "success" : "error"}>{engineerGuardStatus}</StatusChip>
          </div>
          <div>
            <p className="card-head">Branch Hygiene</p>
            <StatusChip tone={branchHygieneStatus === "pass" ? "success" : "warning"}>{branchHygieneStatus}</StatusChip>
          </div>
          <div>
            <p className="card-head">Documentation Review</p>
            <StatusChip tone={documentationReviewStatus === "pass" ? "success" : documentationReviewStatus === "warn" ? "warning" : "error"}>
              {documentationReviewStatus}
            </StatusChip>
          </div>
          <div>
            <p className="card-head">Queue Zero-State</p>
            <StatusChip tone={queueZeroState ? "success" : "warning"}>{queueZeroState ? "clean" : "work pending"}</StatusChip>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>SSH Profiles and Connection Checks</h3>
        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label className="field-block">
            <span className="field-label">Saved Profile</span>
            <select className="select" value={selectedProfileId} onChange={(event) => setSelectedProfileId(event.target.value)}>
              <option value="">No profile selected</option>
              {settings.sshProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-block">
            <span className="field-label">Target Repo</span>
            <input
              className="input mono"
              value={remoteTargetRepo}
              onChange={(event) => setRemoteTargetRepo(event.target.value)}
              placeholder="repo-under-allowlisted-root"
            />
          </label>
          <label className="field-block">
            <span className="field-label">Sidecar Dir</span>
            <input className="input mono" value={remoteSidecarDir} onChange={(event) => setRemoteSidecarDir(event.target.value)} />
          </label>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">SSH Runtime</p>
            <div style={{ marginTop: "0.35rem" }}>
              <StatusChip tone={remoteSshEnabled ? "success" : "warning"}>{remoteSshEnabled ? "enabled" : "disabled"}</StatusChip>
            </div>
            <p className="metric-sub" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
              ssh binary: {remoteSshStatus?.ssh_binary_available ? "available" : "missing"}
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Allowlisted Commands</p>
            <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              {remoteCommandPrefixes.join(", ") || "none"}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <button className="btn" type="button" onClick={() => void runRemoteAction("pwd")} disabled={!selectedProfile || !remoteSshEnabled}>
            Test Connection
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => void runRemoteAction(buildRemoteListCommand(remoteTargetRepo))}
            disabled={!selectedProfile || !remoteSshEnabled}
          >
            List Target Root
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => void runRemoteAction(buildRemoteSidecarCheckCommand(remoteTargetRepo, remoteSidecarDir))}
            disabled={!selectedProfile || !remoteSshEnabled || !remoteTargetRepo.trim()}
          >
            Check Sidecar
          </button>
        </div>
        <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
          Enter a repo under the allowlisted root when checking a deployed sidecar path.
        </p>

        {selectedProfile ? (
          <p className="metric-sub" style={{ marginTop: "0.75rem" }}>
            Active: {selectedProfile.user}@{selectedProfile.host}:{selectedProfile.port} | auth {selectedProfile.auth_method}
          </p>
        ) : null}
        {sshResult ? (
          <p className="metric-sub mono" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
            {sshResult}
          </p>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>UI Access and Companion Runtime</h3>
        <p className="metric-sub" style={{ marginBottom: "0.7rem" }}>
          {uiAccess?.execution_host_summary ?? "Assistant commands run on the Linux host that launched this harness."}
        </p>
        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Browser Access</p>
            <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              {uiAccess?.browser_access_summary ?? "Open the web UI locally or through SSH local port forwarding."}
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Preferred URLs</p>
            <p className="metric-sub mono" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              {(uiAccess?.preferred_urls ?? []).join(" | ") || "loading"}
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Remote Tunnel</p>
            <p className="metric-sub mono" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              {uiAccess?.remote_ssh_tunnel_example ?? "ssh -L <local_port>:127.0.0.1:<ui_port> <linux-host>"}
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Selected Assistant Runtime</p>
            <div style={{ marginTop: "0.35rem" }}>
              <StatusChip tone={assistantRuntime?.availability_status === "available" ? "success" : "warning"}>
                {assistantRuntime?.availability_status ?? "unknown"}
              </StatusChip>
            </div>
            <p className="metric-sub" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
              {assistantRuntime?.detail ?? "Runtime metadata loads from the control API status response."}
            </p>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Builder Flags</h3>
        <p className="metric-sub" style={{ marginBottom: "0.7rem" }}>
          allowlisted root: {builderFlags?.allowlisted_root ?? "n/a"} | scan depth {builderFlags?.scan_limits_defaults?.max_depth ?? "n/a"} | scan files{" "}
          {builderFlags?.scan_limits_defaults?.max_files ?? "n/a"}
        </p>
        <p className="metric-sub" style={{ marginBottom: 0 }}>
          Existing project mode: {builderFlags?.existing_project_mode_enabled ? "enabled" : "disabled"} | history retention{" "}
          {builderFlags?.project_status_history_retention ?? "n/a"}
        </p>
      </section>

      <AssistantActionBar
        assistant={settings.preferredAssistant}
        sourceMode="docs"
        prompt={buildSystemStatusPrompt(systemSummary)}
        disabled={!systemSummary.trim()}
        busy={assistantBusy}
        statusText={assistantStatus}
        assistantRuntime={assistantRuntime}
        executionHostSummary={uiAccess?.execution_host_summary}
        browserAccessSummary={uiAccess?.browser_access_summary}
        onPreviewPrompt={() => setAssistantStatus(buildSystemStatusPrompt(systemSummary))}
        onRunAssistant={onRunAssistant}
      />
    </div>
  );
}
