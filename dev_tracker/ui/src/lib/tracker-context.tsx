import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { BuilderStatusV1, ControlStatusV1, RemoteTargetConfigV1, TemplateStudioV1, TrackerSnapshotV6 } from "./contracts";
import { loadBuilderStatus, loadControlStatus, loadTemplateStudio, loadTrackerSnapshot, triggerSync } from "./loaders";

export interface TrackerSshProfile extends RemoteTargetConfigV1 {
  id: string;
  label: string;
}

export interface TrackerSettings {
  ambientBackground: boolean;
  reducedMotion: boolean;
  theme: "dark" | "light";
  tooltipsEnabled: boolean;
  preferredAssistant: "codex_cli" | "claude_code";
  defaultDiscoveryProvider: "none" | "openai" | "codex_cli" | "claude_code";
  defaultDiscoveryModel: string;
  defaultSshProfileId: string;
  sshProfiles: TrackerSshProfile[];
}

interface TrackerContextValue {
  snapshot: TrackerSnapshotV6 | null;
  status: ControlStatusV1 | null;
  builderStatus: BuilderStatusV1 | null;
  templateStudio: TemplateStudioV1 | null;
  loading: boolean;
  snapshotLoading: boolean;
  builderStatusLoading: boolean;
  templateStudioLoading: boolean;
  refreshing: boolean;
  error: string;
  settings: TrackerSettings;
  setSettings: (next: TrackerSettings) => void;
  refreshData: () => Promise<void>;
  syncNow: () => Promise<void>;
}

const SETTINGS_KEY = "moradin_forge_workbench_settings_v1";

const TrackerContext = createContext<TrackerContextValue | undefined>(undefined);

function readInitialSettings(): TrackerSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return {
        ambientBackground: true,
        reducedMotion: false,
        theme: "dark",
        tooltipsEnabled: true,
        preferredAssistant: "codex_cli",
        defaultDiscoveryProvider: "none",
        defaultDiscoveryModel: "",
        defaultSshProfileId: "",
        sshProfiles: [],
      };
    }

    const parsed = JSON.parse(raw) as Partial<TrackerSettings>;
    const sshProfiles = Array.isArray(parsed.sshProfiles)
      ? parsed.sshProfiles.reduce<TrackerSshProfile[]>((acc, profile) => {
          if (!profile || typeof profile !== "object") {
            return acc;
          }
          const source = profile as TrackerSshProfile;
          const nextProfile: TrackerSshProfile = {
            id: String(source.id ?? "").trim(),
            label: String(source.label ?? "").trim() || String(source.profile_label ?? "").trim() || "SSH Profile",
            target_id: String(source.target_id ?? "").trim(),
            connection_mode: "ssh",
            host: String(source.host ?? "").trim(),
            user: String(source.user ?? "").trim(),
            port: Number.isInteger(Number(source.port)) ? Number(source.port) : 22,
            allowlisted_root: String(source.allowlisted_root ?? "").trim(),
            profile_label: String(source.profile_label ?? "").trim(),
            auth_method: source.auth_method === "pem_path" ? "pem_path" : "ssh_agent",
            pem_path: String(source.pem_path ?? "").trim(),
            known_hosts_mode: source.known_hosts_mode === "accept_new" ? "accept_new" : "strict",
          };
          if (!nextProfile.id) {
            return acc;
          }
          acc.push(nextProfile);
          return acc;
        }, [])
      : [];
    return {
      ambientBackground: Boolean(parsed.ambientBackground),
      reducedMotion: Boolean(parsed.reducedMotion),
      theme: parsed.theme === "light" ? "light" : "dark",
      tooltipsEnabled: parsed.tooltipsEnabled !== false,
      preferredAssistant: parsed.preferredAssistant === "claude_code" ? "claude_code" : "codex_cli",
      defaultDiscoveryProvider:
        parsed.defaultDiscoveryProvider === "openai" ||
        parsed.defaultDiscoveryProvider === "codex_cli" ||
        parsed.defaultDiscoveryProvider === "claude_code"
          ? parsed.defaultDiscoveryProvider
          : "none",
      defaultDiscoveryModel: String(parsed.defaultDiscoveryModel ?? "").trim(),
      defaultSshProfileId: String(parsed.defaultSshProfileId ?? "").trim(),
      sshProfiles,
    };
  } catch {
    return {
      ambientBackground: true,
      reducedMotion: false,
      theme: "dark",
      tooltipsEnabled: true,
      preferredAssistant: "codex_cli",
      defaultDiscoveryProvider: "none",
      defaultDiscoveryModel: "",
      defaultSshProfileId: "",
      sshProfiles: [],
    };
  }
}

export function TrackerProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<TrackerSnapshotV6 | null>(null);
  const [status, setStatus] = useState<ControlStatusV1 | null>(null);
  const [builderStatus, setBuilderStatus] = useState<BuilderStatusV1 | null>(null);
  const [templateStudio, setTemplateStudio] = useState<TemplateStudioV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshotLoading, setSnapshotLoading] = useState(true);
  const [builderStatusLoading, setBuilderStatusLoading] = useState(true);
  const [templateStudioLoading, setTemplateStudioLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [settings, setSettingsState] = useState<TrackerSettings>(() => readInitialSettings());

  const refreshData = useCallback(async () => {
    setRefreshing(true);
    setSnapshotLoading(true);
    setBuilderStatusLoading(true);
    setTemplateStudioLoading(true);
    setError("");

    const [nextSnapshot, nextStatus, nextBuilderStatus, nextTemplateStudio] = await Promise.all([
      loadTrackerSnapshot(),
      loadControlStatus(),
      loadBuilderStatus(),
      loadTemplateStudio(),
    ]);
    if (!nextSnapshot) {
      setError("Tracker snapshot is unavailable. Run `npm run sync-docs` or `npm run dev:ops`.");
    }

    setSnapshot(nextSnapshot);
    setStatus(nextStatus);
    setBuilderStatus(nextBuilderStatus);
    setTemplateStudio(nextTemplateStudio);
    setSnapshotLoading(false);
    setBuilderStatusLoading(false);
    setTemplateStudioLoading(false);
    setRefreshing(false);
    setLoading(false);
  }, []);

  const syncNow = useCallback(async () => {
    setRefreshing(true);
    setError("");

    const syncResponse = await triggerSync();
    if (!syncResponse) {
      setError("Manual sync failed. Ensure `npm run control-api` is running.");
      setRefreshing(false);
      return;
    }

    setStatus(syncResponse);
    setSnapshotLoading(true);
    setBuilderStatusLoading(true);
    setTemplateStudioLoading(true);
    const [nextSnapshot, nextBuilderStatus, nextTemplateStudio] = await Promise.all([
      loadTrackerSnapshot(),
      loadBuilderStatus(),
      loadTemplateStudio(),
    ]);
    setSnapshot(nextSnapshot);
    setBuilderStatus(nextBuilderStatus);
    setTemplateStudio(nextTemplateStudio);
    setSnapshotLoading(false);
    setBuilderStatusLoading(false);
    setTemplateStudioLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const scheduleDeferredLoads = () => {
      const runner = async () => {
        setBuilderStatusLoading(true);
        const nextBuilderStatus = await loadBuilderStatus();
        if (!cancelled) {
          setBuilderStatus(nextBuilderStatus);
          setBuilderStatusLoading(false);
        }

        setSnapshotLoading(true);
        setTemplateStudioLoading(true);
        const [nextSnapshot, nextTemplateStudio] = await Promise.all([loadTrackerSnapshot(), loadTemplateStudio()]);
        if (cancelled) {
          return;
        }
        if (!nextSnapshot) {
          setError("Tracker snapshot is unavailable. Run `npm run sync-docs` or `npm run dev:ops`.");
        }
        setSnapshot(nextSnapshot);
        setTemplateStudio(nextTemplateStudio);
        setSnapshotLoading(false);
        setTemplateStudioLoading(false);
      };

      if (typeof window !== "undefined" && "requestIdleCallback" in window) {
        const requestIdleCallback = window.requestIdleCallback as (callback: IdleRequestCallback) => number;
        requestIdleCallback(() => {
          void runner();
        });
        return;
      }
      globalThis.setTimeout(() => {
        void runner();
      }, 0);
    };

    void (async () => {
      setError("");
      setLoading(true);
      const nextStatus = await loadControlStatus();
      if (cancelled) {
        return;
      }
      setStatus(nextStatus);
      setLoading(false);
      scheduleDeferredLoads();
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const setSettings = useCallback((next: TrackerSettings) => {
    setSettingsState(next);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
  }, []);

  const value = useMemo<TrackerContextValue>(
    () => ({
      snapshot,
      status,
      builderStatus,
      templateStudio,
      loading,
      snapshotLoading,
      builderStatusLoading,
      templateStudioLoading,
      refreshing,
      error,
      settings,
      setSettings,
      refreshData,
      syncNow,
    }),
    [
      snapshot,
      status,
      builderStatus,
      templateStudio,
      loading,
      snapshotLoading,
      builderStatusLoading,
      templateStudioLoading,
      refreshing,
      error,
      settings,
      setSettings,
      refreshData,
      syncNow,
    ],
  );

  return <TrackerContext.Provider value={value}>{children}</TrackerContext.Provider>;
}

export function useTracker() {
  const context = useContext(TrackerContext);
  if (!context) {
    throw new Error("useTracker must be used within TrackerProvider");
  }
  return context;
}
