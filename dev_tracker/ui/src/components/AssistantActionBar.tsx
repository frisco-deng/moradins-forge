import { useState } from "react";

import type { AssistantRuntimeStatusV1 } from "../lib/contracts";
import { openAssistantActivity } from "../lib/assistant-activity";

export interface AssistantArtifactLink {
  label: string;
  path: string;
}

interface AssistantActionBarProps {
  assistant: "codex_cli" | "claude_code";
  prompt: string;
  sourceMode: "builder" | "review" | "project_status" | "docs";
  artifactLinks?: AssistantArtifactLink[];
  disabled?: boolean;
  busy?: boolean;
  statusText?: string;
  assistantRuntime?: AssistantRuntimeStatusV1 | null;
  executionHostSummary?: string;
  browserAccessSummary?: string;
  onPreviewPrompt: () => void;
  onRunAssistant: () => Promise<void> | void;
}

export function AssistantActionBar({
  assistant,
  prompt,
  artifactLinks = [],
  disabled = false,
  busy = false,
  statusText = "",
  assistantRuntime = null,
  executionHostSummary = "Assistant commands run on the Linux host that launched this harness.",
  browserAccessSummary = "Open the web UI locally or through SSH local port forwarding.",
  onPreviewPrompt,
  onRunAssistant,
}: AssistantActionBarProps) {
  const [copyMessage, setCopyMessage] = useState("");
  const assistantBlocked = assistantRuntime?.availability_status === "unavailable";
  const terminalCommand =
    assistantRuntime?.terminal_command_template ??
    `printf '%s\\n' '<paste prompt here>' | ${
      assistant === "claude_code"
        ? "claude --print"
        : "codex exec --color never --sandbox read-only"
    }`;

  async function onCopyPrompt() {
    if (!prompt.trim()) {
      setCopyMessage("No prompt available.");
      return;
    }

    try {
      await navigator.clipboard.writeText(prompt);
      setCopyMessage("Prompt copied.");
    } catch {
      setCopyMessage("Clipboard unavailable.");
    }
  }

  async function onCopyTerminalCommand() {
    try {
      await navigator.clipboard.writeText(terminalCommand);
      setCopyMessage("Terminal command copied.");
    } catch {
      setCopyMessage("Clipboard unavailable.");
    }
  }

  return (
    <section className="card card-pad" style={{ gridColumn: "span 12" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0 }}>Assistant Actions</h3>
          <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
            Selected assistant: {assistant === "claude_code" ? "Claude Code CLI" : "Codex CLI"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button className="btn" type="button" onClick={onPreviewPrompt} disabled={disabled}>
            Preview Prompt
          </button>
          <button className="btn primary" type="button" onClick={() => void onRunAssistant()} disabled={disabled || busy || assistantBlocked}>
            {busy ? "Running..." : "Run Selected Assistant"}
          </button>
          <button className="btn" type="button" onClick={() => void onCopyPrompt()} disabled={disabled}>
            Copy Prompt
          </button>
          <button className="btn" type="button" onClick={() => void onCopyTerminalCommand()} disabled={disabled}>
            Copy Terminal Command
          </button>
          <button className="btn" type="button" onClick={() => openAssistantActivity()} disabled={disabled}>
            Open Activity
          </button>
          {artifactLinks.length > 0 ? (
            <a
              className="btn"
              href={artifactLinks[0]?.path || "#"}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => {
                if (!artifactLinks[0]?.path) {
                  event.preventDefault();
                }
              }}
              style={{ textDecoration: "none" }}
            >
              Open Artifacts
            </a>
          ) : (
            <button className="btn" type="button" disabled>
              Open Artifacts
            </button>
          )}
        </div>
      </div>
      <p className="metric-sub" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
        {executionHostSummary}
      </p>
      <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
        Browser access: {browserAccessSummary}
      </p>
      <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
        Assistant runtime:{" "}
        {assistantRuntime ? `${assistantRuntime.availability_status} | ${assistantRuntime.detail}` : "availability not loaded yet"}
      </p>
      <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
        Live progress appears in Assistant Activity. Use run artifacts for the full persisted record after completion.
      </p>
      <label className="field-block" style={{ marginTop: "0.8rem" }}>
        <span className="field-label">Terminal Command</span>
        <textarea className="input mono" rows={2} value={terminalCommand} readOnly />
      </label>
      {assistantBlocked ? (
        <p className="metric-sub" style={{ marginTop: "0.5rem", marginBottom: 0, color: "var(--warning)" }}>
          Run Selected Assistant is disabled until the configured CLI is available on the Linux host running the harness.
        </p>
      ) : null}
      {statusText ? (
        <p className="metric-sub" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
          {statusText}
        </p>
      ) : null}
      {copyMessage ? (
        <p className="metric-sub" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
          {copyMessage}
        </p>
      ) : null}
      {artifactLinks.length > 1 ? (
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
          {artifactLinks.map((artifact) => (
            <a
              key={`${artifact.label}:${artifact.path}`}
              className="btn"
              href={artifact.path}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              {artifact.label}
            </a>
          ))}
        </div>
      ) : null}
    </section>
  );
}
