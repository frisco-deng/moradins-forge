import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { TrackerSshProfile } from "../lib/tracker-context";
import { useTracker } from "../lib/tracker-context";

function buildEmptyProfile(): TrackerSshProfile {
  return {
    id: "",
    label: "",
    target_id: "",
    connection_mode: "ssh",
    host: "",
    user: "",
    port: 22,
    allowlisted_root: "",
    profile_label: "",
    auth_method: "ssh_agent",
    pem_path: "",
    known_hosts_mode: "strict",
  };
}

function profileIdFromLabel(label: string): string {
  return label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || `ssh-profile-${Date.now()}`;
}

export function SettingsPage() {
  const { settings, setSettings, status } = useTracker();
  const [editingProfile, setEditingProfile] = useState<TrackerSshProfile>(() => buildEmptyProfile());

  const selectedProfile = useMemo(
    () => settings.sshProfiles.find((profile) => profile.id === settings.defaultSshProfileId) ?? null,
    [settings.defaultSshProfileId, settings.sshProfiles],
  );

  function saveProfile() {
    const label = editingProfile.label.trim();
    if (!label || !editingProfile.host.trim() || !editingProfile.user.trim() || !editingProfile.allowlisted_root.trim()) {
      return;
    }

    const nextProfile: TrackerSshProfile = {
      ...editingProfile,
      id: editingProfile.id || profileIdFromLabel(label),
      label,
      profile_label: label,
      connection_mode: "ssh",
      port: Number.isInteger(Number(editingProfile.port)) ? Number(editingProfile.port) : 22,
      auth_method: editingProfile.auth_method === "pem_path" ? "pem_path" : "ssh_agent",
      known_hosts_mode: editingProfile.known_hosts_mode === "accept_new" ? "accept_new" : "strict",
    };

    const remaining = settings.sshProfiles.filter((profile) => profile.id !== nextProfile.id);
    setSettings({
      ...settings,
      sshProfiles: [...remaining, nextProfile].sort((a, b) => a.label.localeCompare(b.label)),
      defaultSshProfileId: settings.defaultSshProfileId || nextProfile.id,
    });
    setEditingProfile(buildEmptyProfile());
  }

  function deleteProfile(profileId: string) {
    const remaining = settings.sshProfiles.filter((profile) => profile.id !== profileId);
    setSettings({
      ...settings,
      sshProfiles: remaining,
      defaultSshProfileId: settings.defaultSshProfileId === profileId ? "" : settings.defaultSshProfileId,
    });
    if (editingProfile.id === profileId) {
      setEditingProfile(buildEmptyProfile());
    }
  }

  return (
    <div className="page-grid">
      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Beta Access Model</h3>
        <p className="metric-sub" style={{ marginBottom: "0.7rem" }}>
          The harness is a Linux-hosted web companion for Codex or Claude. Beta does not ship a Windows-native desktop shell.
        </p>
        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Linux Local</p>
            <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              Run `./harness_devops.sh --port &lt;n&gt;` and browse on localhost.
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">WSL</p>
            <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              Launch in WSL and browse from Windows using localhost or the WSL IPv4 address.
            </p>
          </div>
          <div className="card card-pad" style={{ padding: "0.8rem" }}>
            <p className="card-head">Remote Linux</p>
            <p className="metric-sub mono" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
              {status?.ui_access?.remote_ssh_tunnel_example ?? "ssh -L <local_port>:127.0.0.1:<ui_port> <linux-host>"}
            </p>
          </div>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Visual Preferences</h3>
        <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginBottom: "0.6rem" }}>
          <span style={{ minWidth: "140px" }}>Theme</span>
          <select
            className="select"
            value={settings.theme}
            onChange={(event) => setSettings({ ...settings, theme: event.target.value === "light" ? "light" : "dark" })}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </label>

        <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginBottom: "0.6rem" }}>
          <input
            type="checkbox"
            checked={settings.ambientBackground}
            onChange={(event) => setSettings({ ...settings, ambientBackground: event.target.checked })}
          />
          <span>Ambient background</span>
        </label>

        <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginBottom: "0.6rem" }}>
          <input
            type="checkbox"
            checked={settings.reducedMotion}
            onChange={(event) => setSettings({ ...settings, reducedMotion: event.target.checked })}
          />
          <span>Reduced motion</span>
        </label>

        <label style={{ display: "flex", gap: "0.55rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={settings.tooltipsEnabled}
            onChange={(event) => setSettings({ ...settings, tooltipsEnabled: event.target.checked })}
          />
          <span>Show tooltips</span>
        </label>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 6" }}>
        <h3 style={{ marginTop: 0 }}>Operational Defaults</h3>
        <label className="field-block" style={{ marginBottom: "0.7rem" }}>
          <span className="field-label">Preferred Assistant</span>
          <select
            className="select"
            value={settings.preferredAssistant}
            onChange={(event) =>
              setSettings({
                ...settings,
                preferredAssistant: event.target.value === "claude_code" ? "claude_code" : "codex_cli",
              })
            }
          >
            <option value="codex_cli">Codex CLI</option>
            <option value="claude_code">Claude Code CLI</option>
          </select>
        </label>

        <label className="field-block" style={{ marginBottom: "0.7rem" }}>
          <span className="field-label">Default Discovery Provider</span>
          <select
            className="select"
            value={settings.defaultDiscoveryProvider}
            onChange={(event) =>
              setSettings({
                ...settings,
                defaultDiscoveryProvider:
                  event.target.value === "openai" || event.target.value === "codex_cli" || event.target.value === "claude_code"
                    ? event.target.value
                    : "none",
              })
            }
          >
            <option value="none">Deterministic Local</option>
            <option value="openai">OpenAI</option>
            <option value="codex_cli">Codex CLI</option>
            <option value="claude_code">Claude Code CLI</option>
          </select>
        </label>

        <label className="field-block">
          <span className="field-label">Default Discovery Model</span>
          <input
            className="input"
            value={settings.defaultDiscoveryModel}
            onChange={(event) => setSettings({ ...settings, defaultDiscoveryModel: event.target.value })}
            placeholder="gpt-5-mini / codex-cli-default / claude-code-default"
          />
        </label>

        <p className="metric-sub" style={{ marginTop: "0.8rem", marginBottom: 0 }}>
          PAT / HTTPS auth is intentionally deferred for the current-scope release. Use SSH agent or PEM-path profiles here.
        </p>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <h3 style={{ marginTop: 0 }}>Saved SSH Profiles</h3>
        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label className="field-block">
            <span className="field-label">Profile Label</span>
            <input
              className="input"
              value={editingProfile.label}
              onChange={(event) => setEditingProfile({ ...editingProfile, label: event.target.value })}
              placeholder="staging sidecar host"
            />
          </label>
          <label className="field-block">
            <span className="field-label">Host</span>
            <input
              className="input"
              value={editingProfile.host}
              onChange={(event) => setEditingProfile({ ...editingProfile, host: event.target.value })}
              placeholder="ops.example.internal"
            />
          </label>
          <label className="field-block">
            <span className="field-label">User</span>
            <input
              className="input"
              value={editingProfile.user}
              onChange={(event) => setEditingProfile({ ...editingProfile, user: event.target.value })}
              placeholder="deployer"
            />
          </label>
          <label className="field-block">
            <span className="field-label">Port</span>
            <input
              className="input"
              value={String(editingProfile.port ?? 22)}
              onChange={(event) => setEditingProfile({ ...editingProfile, port: Number(event.target.value) || 22 })}
              placeholder="22"
            />
          </label>
          <label className="field-block" style={{ gridColumn: "1 / -1" }}>
            <span className="field-label">Allowlisted Root</span>
            <input
              className="input mono"
              value={editingProfile.allowlisted_root}
              onChange={(event) => setEditingProfile({ ...editingProfile, allowlisted_root: event.target.value })}
              placeholder="/srv/projects"
            />
          </label>
          <label className="field-block">
            <span className="field-label">Auth Method</span>
            <select
              className="select"
              value={editingProfile.auth_method}
              onChange={(event) =>
                setEditingProfile({
                  ...editingProfile,
                  auth_method: event.target.value === "pem_path" ? "pem_path" : "ssh_agent",
                })
              }
            >
              <option value="ssh_agent">SSH Agent</option>
              <option value="pem_path">PEM Path</option>
            </select>
          </label>
          <label className="field-block">
            <span className="field-label">Known Hosts</span>
            <select
              className="select"
              value={editingProfile.known_hosts_mode}
              onChange={(event) =>
                setEditingProfile({
                  ...editingProfile,
                  known_hosts_mode: event.target.value === "accept_new" ? "accept_new" : "strict",
                })
              }
            >
              <option value="strict">Strict</option>
              <option value="accept_new">Accept New</option>
            </select>
          </label>
          {editingProfile.auth_method === "pem_path" ? (
            <label className="field-block" style={{ gridColumn: "1 / -1" }}>
              <span className="field-label">PEM Path</span>
              <input
                className="input mono"
                value={editingProfile.pem_path}
                onChange={(event) => setEditingProfile({ ...editingProfile, pem_path: event.target.value })}
                placeholder="/path/to/deploy.pem"
              />
            </label>
          ) : null}
        </div>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <button className="btn primary" type="button" onClick={saveProfile}>
            Save SSH Profile
          </button>
          <button className="btn" type="button" onClick={() => setEditingProfile(buildEmptyProfile())}>
            Clear Form
          </button>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <h3 style={{ marginTop: 0 }}>Assistant Runtimes</h3>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          {(["codex_cli", "claude_code"] as const).map((assistantId) => {
            const runtime = status?.assistant_runtimes?.[assistantId];
            return (
              <div key={assistantId} className="card card-pad" style={{ padding: "0.8rem" }}>
                <p className="card-head">{runtime?.label ?? assistantId}</p>
                <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                  {runtime ? `${runtime.availability_status} | ${runtime.detail}` : "Runtime metadata unavailable."}
                </p>
                <textarea
                  className="input mono"
                  rows={2}
                  readOnly
                  value={
                    runtime?.terminal_command_template ??
                    `printf '%s\\n' '<paste prompt here>' | ${
                      assistantId === "claude_code"
                        ? "claude --print"
                        : "codex exec --color never --sandbox read-only"
                    }`
                  }
                  style={{ marginTop: "0.55rem" }}
                />
              </div>
            );
          })}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <h3 style={{ marginTop: 0 }}>Default Profile</h3>
        <label className="field-block">
          <span className="field-label">Preferred SSH Profile</span>
          <select
            className="select"
            value={settings.defaultSshProfileId}
            onChange={(event) => setSettings({ ...settings, defaultSshProfileId: event.target.value })}
          >
            <option value="">No default profile</option>
            {settings.sshProfiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.label}
              </option>
            ))}
          </select>
        </label>
        <p className="metric-sub" style={{ marginTop: "0.75rem" }}>
          Selected: {selectedProfile ? `${selectedProfile.user}@${selectedProfile.host}:${selectedProfile.port}` : "none"}
        </p>
        <Link to="/settings/system" className="btn" style={{ textDecoration: "none", marginTop: "0.6rem" }}>
          Open System Status
        </Link>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <h3 style={{ marginTop: 0 }}>Stored Profiles</h3>
        {settings.sshProfiles.length > 0 ? (
          <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {settings.sshProfiles.map((profile) => (
              <article key={profile.id} className="card card-pad" style={{ padding: "0.8rem" }}>
                <p className="card-head" style={{ marginTop: 0 }}>
                  {profile.label}
                </p>
                <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
                  {profile.user}@{profile.host}:{profile.port}
                </p>
                <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
                  {profile.auth_method === "pem_path" ? `PEM: ${profile.pem_path || "missing"}` : "SSH agent"}
                </p>
                <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
                  <button className="btn" type="button" onClick={() => setEditingProfile(profile)}>
                    Edit
                  </button>
                  <button className="btn" type="button" onClick={() => deleteProfile(profile.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted" style={{ marginBottom: 0 }}>
            No SSH profiles saved yet.
          </p>
        )}
      </section>
    </div>
  );
}
