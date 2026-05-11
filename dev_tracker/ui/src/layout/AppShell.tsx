import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { matchPath, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  BookOpenText,
  ChevronsLeft,
  ChevronsRight,
  ChevronDown,
  FolderPlus,
  Hammer,
  LoaderCircle,
  Menu,
  Search,
  X,
} from "lucide-react";

import { AssistantActivityDrawer } from "../components/AssistantActivityDrawer";
import { AttentionChip } from "../components/AttentionChip";
import { CommandPalette } from "../components/CommandPalette";
import { GlassPopover } from "../components/GlassPopover";
import { ParallaxStarsBackground } from "../components/ParallaxStarsBackground";
import type { AssistantRunResponseV1, AssistantRunSummaryV1, DocRecordV1 } from "../lib/contracts";
import { getDocByPath } from "../lib/doc-helpers";
import { ASSISTANT_ACTIVITY_EVENT, type AssistantActivityEventDetail } from "../lib/assistant-activity";
import { loadAssistantRun, loadAssistantRuns } from "../lib/loaders";
import {
  decodeProjectRouteId,
  encodeProjectRouteId,
  isOverviewManagerProject,
  OVERVIEW_MANAGER_PROJECT_ID,
  OVERVIEW_MANAGER_PROJECT_LABEL,
  OVERVIEW_PROJECT_CHANGE_EVENT,
  readOverviewActiveProject,
  resolveSelectedProjectLabel,
  writeOverviewActiveProject,
} from "../lib/overview-project";
import { findActivePrimaryNavId, findWorkspaceSecondaryItems, isNavPathActive, NAV_ITEMS, PRIMARY_NAV_ITEMS, PROJECT_WORKSPACE_ITEMS } from "../lib/nav";
import { PRODUCT_METADATA } from "../lib/product-metadata";
import { ROUTE_CONTEXT_INVENTORY } from "../lib/route-context";
import { useTracker } from "../lib/tracker-context";

interface CommandItem {
  id: string;
  label: string;
  subtitle: string;
  description?: string;
  badge?: string;
  to: string;
}

const SIDEBAR_COLLAPSED_STORAGE_KEY = "mh-control-plane-sidebar-collapsed-v1";

function readSidebarCollapsed() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true";
}

function writeSidebarCollapsed(value: boolean) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, value ? "true" : "false");
}

const WORKSPACE_DOC_MAP: Record<string, string[]> = {
  home: [
    "docs/00_overview/engineer_entrypoint.md",
    "docs/00_overview/implementation_phases.md",
    "docs/11_ops/codex_run_loop.md",
  ],
  projects: [
    "docs/11_ops/project_builder_runbook.md",
    "docs/11_ops/project_builder_ssh_operator_guide.md",
    "docs/15_checklists/project_builder_beta_checklist.md",
  ],
  deploy: [
    "docs/11_ops/quick_start.md",
    "docs/11_ops/project_builder_runbook.md",
    "docs/design_docs/project_builder_visual_reference.md",
  ],
  payload: [
    "docs/product_specs/template_profiles.md",
    "docs/design_docs/project_builder_control_api.md",
    "docs/exec_plans/tech-debt-tracker.md",
  ],
  reviews: [
    "docs/11_ops/codex_run_loop.md",
    "docs/15_checklists/project_builder_beta_checklist.md",
    "docs/exec_plans/tech-debt-tracker.md",
  ],
  docs: [
    "docs/index.md",
    "docs/00_overview/engineer_entrypoint.md",
    "docs/00_overview/implementation_phases.md",
  ],
  settings: [
    "docs/11_ops/quick_start.md",
    "docs/11_ops/project_builder_ssh_operator_guide.md",
    "docs/11_ops/codex_run_loop.md",
  ],
};

const PATH_ONLY_HEADER_WORKSPACES = new Set(["home", "deploy", "payload", "reviews", "docs"]);

function normalize(input: string) {
  return input.toLowerCase();
}

function compactText(input: string) {
  return input.replace(/\s+/g, " ").trim();
}

function buildSnippet(rawContent: string, query: string) {
  const compact = compactText(rawContent);
  const normalizedContent = normalize(compact);
  const index = normalizedContent.indexOf(query);
  if (index < 0) {
    return "";
  }

  const radius = 88;
  const start = Math.max(index - radius, 0);
  const end = Math.min(index + query.length + radius, compact.length);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < compact.length ? "..." : "";
  return `${prefix}${compact.slice(start, end)}${suffix}`;
}

function renderDocLink(doc: DocRecordV1) {
  return (
    <NavLink key={doc.id} className="context-rail-doc-link" to={`/docs/${doc.id}`}>
      <span>{doc.title}</span>
      <small>{doc.relative_path}</small>
    </NavLink>
  );
}

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { snapshot, status, builderStatus, templateStudio, loading, refreshing, error, settings, setSettings, refreshData, syncNow } = useTracker();

  const [commandOpen, setCommandOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeProject, setActiveProject] = useState(() => readOverviewActiveProject());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => readSidebarCollapsed());
  const [assistantActivityOpen, setAssistantActivityOpen] = useState(false);
  const [assistantActivityLoading, setAssistantActivityLoading] = useState(false);
  const [assistantRuns, setAssistantRuns] = useState<AssistantRunSummaryV1[]>([]);
  const [selectedAssistantRunId, setSelectedAssistantRunId] = useState("");
  const [selectedAssistantRun, setSelectedAssistantRun] = useState<AssistantRunResponseV1 | null>(null);
  const [topbarHeight, setTopbarHeight] = useState(92);
  const topbarRef = useRef<HTMLElement | null>(null);

  const activePrimaryId = findActivePrimaryNavId(location.pathname);
  const activePrimaryItem = PRIMARY_NAV_ITEMS.find((item) => item.id === activePrimaryId) ?? PRIMARY_NAV_ITEMS[0]!;
  const isDeployFocusRoute =
    location.pathname.startsWith("/deploy/") ||
    location.pathname === "/builder" ||
    location.pathname === "/deploy-map" ||
    location.pathname === "/quick-start" ||
    location.pathname === "/readiness" ||
    location.pathname === "/project-status";
  const activeRouteContext = [...ROUTE_CONTEXT_INVENTORY]
    .sort((left, right) => right.route.length - left.route.length)
    .find((entry) => matchPath({ path: entry.route, end: false }, location.pathname) ?? isNavPathActive(location.pathname, entry.route));

  const projectRouteMatch =
    matchPath("/project/:projectId/*", location.pathname) ?? matchPath("/project/:projectId", location.pathname);
  const projectRouteId = String(projectRouteMatch?.params.projectId ?? "").trim();
  const routeProject = projectRouteId ? decodeProjectRouteId(projectRouteId) : "";
  const effectiveProject = routeProject || activeProject;
  const projectLabel = resolveSelectedProjectLabel(effectiveProject);
  const activeSecondaryItems = useMemo(() => {
    if (projectRouteId) {
      return PROJECT_WORKSPACE_ITEMS.map((item) => ({
        id: item.id,
        path: `/project/${projectRouteId}/${item.path}`,
        label: item.label,
      }));
    }
    return findWorkspaceSecondaryItems(location.pathname);
  }, [location.pathname, projectRouteId]);

  const commands = useMemo<CommandItem[]>(() => {
    const routeCommands = NAV_ITEMS.map((item) => ({
      id: `route-${item.path}`,
      label: item.label,
      subtitle: "Workspace",
      badge: "route",
      to: item.path,
    }));
    const workflowCommands: CommandItem[] = [
      { id: "workflow-deploy", label: "Start Deploy Flow", subtitle: "Workflow", badge: "workflow", to: "/deploy/quick-start" },
      { id: "workflow-readiness", label: "Open Readiness", subtitle: "Workflow", badge: "workflow", to: "/deploy/readiness" },
      { id: "workflow-payload", label: "Open Moradin Payload", subtitle: "Workflow", badge: "workflow", to: "/payload" },
      { id: "workflow-projects", label: "Open Projects Portfolio", subtitle: "Workflow", badge: "workflow", to: "/projects" },
      { id: "workflow-reviews", label: "Open Review Queue", subtitle: "Workflow", badge: "workflow", to: "/reviews/queue" },
    ];
    const projectCommands = (builderStatus?.known_repos ?? []).map((repo) => ({
      id: `project-${repo.name}`,
      label: repo.name,
      subtitle: repo.path,
      badge: "project",
      description: repo.git_initialized ? "Tracked repo" : "Tracked repo without git metadata",
      to: `/project/${encodeProjectRouteId(repo.name)}/overview`,
    }));
    const docCommands = (snapshot?.docs ?? [])
      .slice(0, 220)
      .map((doc) => ({
        id: `doc-${doc.id}`,
        label: doc.title,
        subtitle: doc.relative_path,
        badge: "doc",
        to: `/docs/${doc.id}`,
      }));

    return [...routeCommands, ...workflowCommands, ...projectCommands, ...docCommands];
  }, [builderStatus?.known_repos, snapshot]);

  const filteredCommands = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return commands.slice(0, 24);
    }

    const routeMatches = commands
      .filter((item) => `${item.label} ${item.subtitle} ${item.description ?? ""}`.toLowerCase().includes(normalized))
      .slice(0, 10);

    const contextMatches: Array<{ item: CommandItem; score: number }> = [];
    for (const doc of snapshot?.docs ?? []) {
      const metadataText = `${doc.title} ${doc.relative_path} ${doc.section}`;
      const metadataMatch = normalize(metadataText).includes(normalized);
      const headingMatch = doc.headings.find((heading) => normalize(heading.text).includes(normalized))?.text ?? "";
      const snippet = buildSnippet(doc.content, normalized);
      const contentMatch = snippet.length > 0;

      if (!metadataMatch && !headingMatch && !contentMatch) {
        continue;
      }

      const matchedIn = [
        ...(metadataMatch ? ["metadata"] : []),
        ...(headingMatch ? ["heading"] : []),
        ...(contentMatch ? ["content"] : []),
      ];

      contextMatches.push({
        item: {
          id: `doc-context-${doc.id}`,
          label: doc.title,
          subtitle: `${doc.relative_path} | ${matchedIn.join(", ")}`,
          description: headingMatch ? `Heading: ${headingMatch}` : snippet,
          badge: "context",
          to: `/docs/${doc.id}`,
        },
        score: (metadataMatch ? 12 : 0) + (headingMatch ? 8 : 0) + (contentMatch ? 10 : 0),
      });
    }

    const docMatches = contextMatches
      .sort((left, right) => right.score - left.score)
      .slice(0, 18)
      .map((entry) => entry.item);

    return [...routeMatches, ...docMatches].slice(0, 32);
  }, [commands, query, snapshot]);

  const assistantRuntime = status?.assistant_runtimes?.[settings.preferredAssistant] ?? null;
  const activeAssistantRun = assistantRuns.find((run) => run.status === "queued" || run.status === "running") ?? null;
  const latestAssistantRun = assistantRuns[0] ?? null;

  const refreshAssistantActivity = useCallback(
    async (preferredRunId?: string, options?: { silent?: boolean }) => {
      const silent = options?.silent === true;
      if (!silent) {
        setAssistantActivityLoading(true);
      }
      const listResponse = await loadAssistantRuns(8);
      if (!listResponse) {
        if (!silent) {
          setAssistantActivityLoading(false);
        }
        return;
      }
      setAssistantRuns(listResponse.runs);
      const nextSelectedRunId =
        preferredRunId !== undefined
          ? preferredRunId
          : selectedAssistantRunId || listResponse.active_run_id || listResponse.runs[0]?.run_id || "";
      setSelectedAssistantRunId(nextSelectedRunId);
      if (!nextSelectedRunId) {
        setSelectedAssistantRun(null);
        if (!silent) {
          setAssistantActivityLoading(false);
        }
        return;
      }
      const detail = await loadAssistantRun(nextSelectedRunId);
      setSelectedAssistantRun(detail);
      if (!silent) {
        setAssistantActivityLoading(false);
      }
    },
    [selectedAssistantRunId],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const hotkey = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
      if (hotkey) {
        event.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setMenuOpen(false);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const syncProject = () => {
      setActiveProject(readOverviewActiveProject());
    };

    window.addEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
    window.addEventListener("storage", syncProject);
    return () => {
      window.removeEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
      window.removeEventListener("storage", syncProject);
    };
  }, []);

  useEffect(() => {
    if (routeProject && routeProject !== activeProject) {
      writeOverviewActiveProject(routeProject);
      setActiveProject(routeProject);
    }
  }, [routeProject, activeProject]);

  useEffect(() => {
    setCommandOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    writeSidebarCollapsed(sidebarCollapsed);
  }, [sidebarCollapsed]);

  useEffect(() => {
    const node = topbarRef.current;
    if (!node) {
      return;
    }

    const updateHeight = () => {
      setTopbarHeight(node.getBoundingClientRect().height || 92);
    };

    updateHeight();
    const resizeObserver = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateHeight) : null;
    resizeObserver?.observe(node);
    window.addEventListener("resize", updateHeight);
    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", updateHeight);
    };
  }, [location.pathname, activeProject, activePrimaryId]);

  useEffect(() => {
    void refreshAssistantActivity(undefined, { silent: true });
  }, [refreshAssistantActivity]);

  useEffect(() => {
    const handleAssistantActivity = (event: Event) => {
      const detail = (event as CustomEvent<AssistantActivityEventDetail>).detail;
      setAssistantActivityOpen(true);
      void refreshAssistantActivity(detail?.runId);
    };

    window.addEventListener(ASSISTANT_ACTIVITY_EVENT, handleAssistantActivity);
    return () => {
      window.removeEventListener(ASSISTANT_ACTIVITY_EVENT, handleAssistantActivity);
    };
  }, [refreshAssistantActivity]);

  useEffect(() => {
    if (!activeAssistantRun) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void refreshAssistantActivity(undefined, { silent: true });
    }, 1500);
    return () => window.clearInterval(intervalId);
  }, [activeAssistantRun, refreshAssistantActivity]);

  if (loading && !status) {
    return <div className="loading-screen">Loading harness shell...</div>;
  }

  const snapshotAvailable = Boolean(snapshot);

  const assistantActivityLabel = activeAssistantRun
    ? `${settings.preferredAssistant === "claude_code" ? "Claude" : "Codex"} active`
    : assistantRuntime?.availability_status === "unavailable"
      ? `${settings.preferredAssistant === "claude_code" ? "Claude" : "Codex"} unavailable`
      : latestAssistantRun?.needs_operator_input
        ? "Agent question waiting"
        : latestAssistantRun?.status === "fail"
          ? "Last run failed"
          : `${settings.preferredAssistant === "claude_code" ? "Claude" : "Codex"} ready`;
  const assistantActivityState = activeAssistantRun
    ? "running"
    : assistantRuntime?.availability_status === "unavailable"
      ? "unavailable"
      : latestAssistantRun?.needs_operator_input
        ? "question"
        : latestAssistantRun?.status === "fail"
          ? "error"
          : "ready";

  const primaryDocs = (WORKSPACE_DOC_MAP[activePrimaryId] ?? [])
    .map((path) => (snapshot ? getDocByPath(snapshot, path) : null))
    .filter((doc): doc is DocRecordV1 => doc !== null)
    .slice(0, 4);

  const currentObjective = snapshot?.project_overview.active_objectives[0] ?? null;
  const currentAlerts = (snapshot?.capability_gaps.open_count ?? 0) + (snapshot?.review_queue.pending_total ?? 0);
  const currentProjectPath = isOverviewManagerProject(effectiveProject)
    ? snapshot?.repo_root ?? "/repo"
    : builderStatus?.known_repos.find((repo) => repo.name === effectiveProject)?.path ?? "No repo selected";
  const usePathOnlyHeader = projectRouteId.length > 0 || PATH_ONLY_HEADER_WORKSPACES.has(activePrimaryId);
  const topbarTitle = usePathOnlyHeader ? "" : activeRouteContext?.title ?? activePrimaryItem.label;
  const topbarDescription = projectRouteId
    ? currentProjectPath
    : PATH_ONLY_HEADER_WORKSPACES.has(activePrimaryId)
      ? currentProjectPath
      : activeRouteContext?.purpose ?? activePrimaryItem.description;
  const currentProjectWorkspacePath = effectiveProject ? `/project/${encodeProjectRouteId(effectiveProject)}/overview` : "/projects";

  const navigateToProject = (projectValue: string) => {
    writeOverviewActiveProject(projectValue);
    setActiveProject(projectValue);

    if (!projectValue) {
      void navigate("/home");
      return;
    }

    const routeId = encodeProjectRouteId(projectValue);
    if (projectRouteId) {
      const suffix = location.pathname.replace(/^\/project\/[^/]+\/?/, "");
      void navigate(`/project/${routeId}/${suffix || "overview"}`);
      return;
    }
    void navigate(`/project/${routeId}/overview`);
  };

  const projectSwitcher = (
    <GlassPopover
      ariaLabel="Switch project"
      align="start"
      preferredWidth={340}
      triggerClassName="shell-context-trigger project"
      trigger={
        <>
          <Hammer size={14} strokeWidth={2.1} aria-hidden="true" />
          <span>{projectLabel}</span>
          <ChevronDown size={14} strokeWidth={2.1} aria-hidden="true" />
        </>
      }
    >
      {({ close }) => (
        <div className="shell-switcher-panel">
          <p className="card-head" style={{ marginTop: 0 }}>Current Project</p>
          <p className="metric-sub" style={{ marginTop: "0.3rem" }}>
            Choose the repo Builder, Verify, and project workspaces should inherit by default.
          </p>
          <div className="shell-switcher-list">
            <button
              type="button"
              className={`shell-switcher-option ${activeProject.length === 0 ? "active" : ""}`.trim()}
              onClick={() => {
                close();
                navigateToProject("");
              }}
            >
              <span className="shell-switcher-option-title">
                <Hammer size={14} strokeWidth={2.1} aria-hidden="true" />
                <span>No Project Selected</span>
              </span>
              <span className="shell-switcher-option-meta">Return to manager-level command center without a pinned project target.</span>
            </button>
            <button
              type="button"
              className={`shell-switcher-option ${isOverviewManagerProject(activeProject) ? "active" : ""}`.trim()}
              onClick={() => {
                close();
                navigateToProject(OVERVIEW_MANAGER_PROJECT_ID);
              }}
            >
              <span className="shell-switcher-option-title">
                <Hammer size={14} strokeWidth={2.1} aria-hidden="true" />
                <span>{OVERVIEW_MANAGER_PROJECT_LABEL}</span>
              </span>
              <span className="shell-switcher-option-meta">Operate the manager repo as the current project target.</span>
            </button>
            {(builderStatus?.known_repos ?? []).map((repo) => (
              <button
                key={repo.name}
                type="button"
                className={`shell-switcher-option ${repo.name === activeProject ? "active" : ""}`.trim()}
                onClick={() => {
                  close();
                  navigateToProject(repo.name);
                }}
              >
                <span className="shell-switcher-option-title">
                  <Hammer size={14} strokeWidth={2.1} aria-hidden="true" />
                  <span>{repo.name}</span>
                </span>
                <span className="shell-switcher-option-meta">
                  {repo.git_initialized ? "Git initialized" : "No git metadata"} · {repo.path}
                </span>
              </button>
            ))}
            <button
              type="button"
              className="shell-switcher-option"
              onClick={() => {
                close();
                void navigate("/deploy/builder");
              }}
            >
              <span className="shell-switcher-option-title">
                <FolderPlus size={14} strokeWidth={2.1} aria-hidden="true" />
                <span>+ Add Project</span>
              </span>
              <span className="shell-switcher-option-meta">Create or import a repo through the Builder workflow.</span>
            </button>
          </div>
        </div>
      )}
    </GlassPopover>
  );

  const renderSidebar = (mobile = false) => (
    <div className={`shell-sidebar-inner ${mobile ? "mobile" : "desktop"}`.trim()}>
      <div className={`shell-sidebar-brand ${sidebarCollapsed ? "collapsed" : ""}`.trim()}>
        <div className="shell-sidebar-brand-row">
          <div className="shell-sidebar-brand-copy">
            <p className="shell-menu-tag">Control Plane</p>
            <h1>Moradin Forge Workbench</h1>
            <small>{snapshot?.git.branch ?? "snapshot loading"}</small>
          </div>
          <button
            type="button"
            className={`shell-sidebar-toggle ${sidebarCollapsed ? "collapsed" : ""}`.trim()}
            aria-label={sidebarCollapsed ? "Expand control plane" : "Collapse control plane"}
            title={sidebarCollapsed ? "Expand control plane" : "Collapse control plane"}
            onClick={() => setSidebarCollapsed((value) => !value)}
          >
            {sidebarCollapsed ? (
              <ChevronsRight size={16} strokeWidth={2.1} aria-hidden="true" />
            ) : (
              <ChevronsLeft size={16} strokeWidth={2.1} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <nav className="shell-sidebar-nav" aria-label="Primary navigation">
        {PRIMARY_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const targetPath = item.id === "projects" ? currentProjectWorkspacePath : item.path;
          return (
            <NavLink
              key={item.id}
              className={({ isActive }) => `sidebar-link ${isActive || (item.id === activePrimaryId && location.pathname.startsWith("/project/")) ? "active" : ""}`.trim()}
              to={targetPath}
              title={item.label}
              aria-label={item.label}
              onClick={() => setMenuOpen(false)}
            >
              <span className="sidebar-link-icon">
                <Icon size={16} strokeWidth={2.1} aria-hidden="true" />
              </span>
              <span className="sidebar-link-copy">
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
            </NavLink>
          );
        })}
      </nav>

      {!sidebarCollapsed && activeSecondaryItems.length ? (
        <section className="shell-sidebar-section">
          <p className="shell-sidebar-section-label">{projectRouteId ? "Current Project" : "Workspace Views"}</p>
          <div className="shell-sidebar-secondary">
            {activeSecondaryItems.map((item) => (
              <NavLink key={item.path} className={({ isActive }) => `sidebar-secondary-link ${isActive ? "active" : ""}`.trim()} to={item.path} onClick={() => setMenuOpen(false)}>
                {item.label}
              </NavLink>
            ))}
          </div>
        </section>
      ) : null}

      {!sidebarCollapsed ? (
      <section className="card card-pad shell-sidebar-card">
        <p className="card-head">Quick Actions</p>
        <div className="shell-sidebar-actions">
          <button className="btn" type="button" onClick={() => setCommandOpen(true)}>
            Search
          </button>
          <button className="btn" type="button" onClick={() => void refreshData()} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button className="btn primary" type="button" onClick={() => void syncNow()} disabled={refreshing}>
            Sync Docs
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => setSettings({ ...settings, theme: settings.theme === "dark" ? "light" : "dark" })}
          >
            {settings.theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>
      </section>
      ) : null}

      {!sidebarCollapsed ? (
      <section className="card card-pad shell-sidebar-card">
        <p className="card-head">Runtime</p>
        <p className="metric mono" style={{ fontSize: "1rem", marginTop: "0.55rem" }}>
          {snapshot?.git.short_sha ?? "--"}
        </p>
        <p className="metric-sub mono">{snapshot?.git.last_commit ?? "No commit data"}</p>
      </section>
      ) : null}
    </div>
  );

  return (
    <div className={`app-root theme-${settings.theme}`}>
      <ParallaxStarsBackground enabled={settings.ambientBackground} reducedMotion={settings.reducedMotion} />
      <div className={`dashboard-shell control-plane-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`.trim()}>
        <aside className={`shell-sidebar ${sidebarCollapsed ? "collapsed" : ""}`.trim()} aria-label="Primary navigation">
          {renderSidebar(false)}
        </aside>

        <div className="shell-main" style={{ ["--topbar-offset" as string]: `${topbarHeight}px` }}>
          <header ref={topbarRef} className="topbar">
            <div className="topbar-left">
              <div className="topbar-context-row">
                <div className="topbar-switchers">
                  {projectSwitcher}
                </div>
                <div className="actions">
                  <button
                    className={`assistant-activity-trigger ${assistantActivityState}`.trim()}
                    type="button"
                    onClick={() => {
                      setAssistantActivityOpen(true);
                      void refreshAssistantActivity();
                    }}
                  >
                    <span className="assistant-activity-trigger-dot" aria-hidden="true">
                      {assistantActivityLoading ? <LoaderCircle className="assistant-spin" size={12} /> : <Activity size={12} />}
                    </span>
                    <span>{assistantActivityLabel}</span>
                  </button>
                  <button className="btn" type="button" onClick={() => setCommandOpen(true)}>
                    <Search size={14} strokeWidth={2.1} aria-hidden="true" />
                    <span>Command Palette</span>
                  </button>
                  <button className="icon-btn shell-menu-toggle" type="button" aria-label={menuOpen ? "Close navigation" : "Open navigation"} onClick={() => setMenuOpen((value) => !value)}>
                    {menuOpen ? <X size={16} /> : <Menu size={16} />}
                  </button>
                </div>
              </div>
              {topbarTitle ? <h1 className="topbar-heading">{topbarTitle}</h1> : null}
              <div className="muted topbar-description">{topbarDescription}</div>
              <div className="topbar-meta">
                <span className={`shell-badge ${activeRouteContext?.level ?? "manager"}`}>{activeRouteContext?.level ?? "manager"}</span>
                {isDeployFocusRoute ? (
                  <>
                    <span className="shell-badge">Deploy focus</span>
                    <span className="shell-badge">
                      {effectiveProject && !isOverviewManagerProject(effectiveProject) ? `Project ${projectLabel}` : "Choose project target"}
                    </span>
                    <span className="shell-badge">{activeAssistantRun ? "Run active" : "Agent ready"}</span>
                  </>
                ) : (
                  <>
                    <span className="shell-badge">Harness {PRODUCT_METADATA.managerVersion}</span>
                    <span className="shell-badge">Payload {PRODUCT_METADATA.templateVersion}</span>
                    <span className="shell-badge">Host {status?.ui_access?.runtime_mode ?? "unknown"}</span>
                    <span className="shell-badge">{activeAssistantRun ? "Run active" : "No active run"}</span>
                    {templateStudio?.validation.available ? (
                      templateStudio.validation.overall_ok ? (
                        <span className="shell-badge">Payload pass</span>
                      ) : (
                        <AttentionChip
                          label="Payload attention"
                          summary={
                            templateStudio.validation.messages?.[0] ??
                            "The payload validation state is not fully healthy. Open Moradin Payload to review the failing checks."
                          }
                          items={[
                            {
                              label: "Open Moradin Payload",
                              to: "/payload",
                              detail: "Inspect validation and dry-run results.",
                            },
                          ]}
                        />
                      )
                    ) : (
                      <span className="shell-badge">Payload pending</span>
                    )}
                    <span className="shell-badge">Alerts {currentAlerts}</span>
                    <span className="shell-badge">Snapshot {snapshot?.generated_at ? new Date(snapshot.generated_at).toLocaleTimeString() : "n/a"}</span>
                  </>
                )}
              </div>
            </div>
          </header>

          {error ? (
            <div className="card card-pad" style={{ margin: "0.9rem 1.1rem 0", borderColor: "rgba(239,68,68,0.4)" }}>
              <strong style={{ color: "var(--error)" }}>Data issue:</strong> <span className="muted">{error}</span>
            </div>
          ) : null}

          <div className={`content-shell ${isDeployFocusRoute ? "focus-route" : ""}`.trim()}>
            <main className="page-wrap">
              <Outlet />
            </main>

            {isDeployFocusRoute ? null : (
              <aside className="context-rail" aria-label="Context rail">
                <section className="card card-pad context-rail-card">
              <p className="card-head">Current Objective</p>
              {currentObjective ? (
                    <>
                      <p className="metric" style={{ fontSize: "1.1rem" }}>{currentObjective.goal}</p>
                      <p className="metric-sub">{currentObjective.in_scope}</p>
                    </>
                  ) : (
                    <p className="metric-sub" style={{ marginTop: "0.6rem" }}>
                      {snapshotAvailable ? "No active objective recorded." : "Snapshot details are still loading."}
                    </p>
                  )}
                </section>

                <section className="card card-pad context-rail-card">
                  <p className="card-head">Current Context</p>
                  <div className="context-rail-list">
                    <div>
                      <strong>Workspace</strong>
                      <small>{activePrimaryItem.label}</small>
                    </div>
                    <div>
                      <strong>Project</strong>
                      <small>{projectLabel}</small>
                    </div>
                    <div>
                      <strong>Path</strong>
                      <small className="mono">{currentProjectPath}</small>
                    </div>
                    <div>
                      <strong>Next action</strong>
                      <small>{snapshot?.loop_state.next_action || "snapshot loading"}</small>
                    </div>
                  </div>
                </section>

                <section className="card card-pad context-rail-card">
                  <p className="card-head">Blockers And Approvals</p>
                  <div className="context-rail-list">
                    <div>
                      <strong>Capability gaps</strong>
                      <small>{snapshot?.capability_gaps.open_count ?? 0}</small>
                    </div>
                    <div>
                      <strong>Pending approvals</strong>
                      <small>{snapshot?.review_queue.pending_approvals ?? 0}</small>
                    </div>
                    <div>
                      <strong>Review queue</strong>
                      <small>{snapshot?.review_queue.pending_total ?? 0}</small>
                    </div>
                    <div>
                      <strong>Guide state</strong>
                      <small>{snapshotAvailable ? (currentAlerts > 0 ? "Action needed" : "Stable") : "Loading"}</small>
                    </div>
                  </div>
                </section>

                <section className="card card-pad context-rail-card">
                  <p className="card-head">Assistant Run</p>
                  {latestAssistantRun ? (
                    <div className="context-rail-list">
                      <div>
                        <strong>Status</strong>
                        <small>{latestAssistantRun.status}</small>
                      </div>
                      <div>
                        <strong>Source</strong>
                        <small>{latestAssistantRun.source_mode}</small>
                      </div>
                      <div>
                        <strong>Target</strong>
                        <small>{latestAssistantRun.target_repo || "manager repo"}</small>
                      </div>
                    </div>
                  ) : (
                    <p className="metric-sub" style={{ marginTop: "0.6rem" }}>No assistant activity captured yet.</p>
                  )}
                </section>

                <section className="card card-pad context-rail-card">
                  <p className="card-head">Related Docs</p>
                  {primaryDocs.length ? (
                    <div className="context-rail-docs">{primaryDocs.map(renderDocLink)}</div>
                  ) : (
                    <p className="metric-sub" style={{ marginTop: "0.6rem" }}>
                      {snapshotAvailable ? "No linked docs found for this workspace." : "Workspace docs are loading."}
                    </p>
                  )}
                </section>
              </aside>
            )}
          </div>
        </div>
      </div>

      <button className={`shell-menu-overlay ${menuOpen ? "open" : ""}`} type="button" onClick={() => setMenuOpen(false)} aria-label="Close menu" />

      <aside className={`shell-menu ${menuOpen ? "open" : ""}`} aria-hidden={!menuOpen}>
        {renderSidebar(true)}
      </aside>

      <CommandPalette
        open={commandOpen}
        query={query}
        items={filteredCommands}
        onClose={() => {
          setCommandOpen(false);
          setQuery("");
        }}
        onQueryChange={setQuery}
        onSelect={(to) => navigate(to)}
      />
      <AssistantActivityDrawer
        open={assistantActivityOpen}
        loading={assistantActivityLoading}
        runs={assistantRuns}
        selectedRunId={selectedAssistantRunId}
        selectedRun={selectedAssistantRun}
        onClose={() => setAssistantActivityOpen(false)}
        onSelectRun={(runId) => {
          setSelectedAssistantRunId(runId);
          void refreshAssistantActivity(runId);
        }}
      />
    </div>
  );
}
