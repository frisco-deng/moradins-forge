import { lazy, Suspense, type ComponentType } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { DeployWorkspaceLayout } from "./pages/DeployWorkspaceLayout";
import { LegacyProjectRouteRedirect } from "./pages/LegacyProjectRouteRedirect";
import { ProjectWorkspaceLayout } from "./pages/ProjectWorkspaceLayout";
import { ReviewsWorkspaceLayout } from "./pages/ReviewsWorkspaceLayout";
import { SettingsWorkspaceLayout } from "./pages/SettingsWorkspaceLayout";

function lazyNamedPage<TModule extends Record<string, ComponentType<any>>>(
  loader: () => Promise<TModule>,
  exportName: keyof TModule,
) {
  return lazy(async () => {
    const module = await loader();
    return { default: module[exportName] as ComponentType<any> };
  });
}

const ArchivePage = lazyNamedPage(() => import("./pages/ArchivePage"), "ArchivePage");
const ChangesPage = lazyNamedPage(() => import("./pages/ChangesPage"), "ChangesPage");
const CyclesPage = lazyNamedPage(() => import("./pages/CyclesPage"), "CyclesPage");
const DeployMapPage = lazyNamedPage(() => import("./pages/DeployMapPage"), "DeployMapPage");
const DocDetailPage = lazyNamedPage(() => import("./pages/DocDetailPage"), "DocDetailPage");
const DocsPage = lazyNamedPage(() => import("./pages/DocsPage"), "DocsPage");
const ExchangePage = lazyNamedPage(() => import("./pages/ExchangePage"), "ExchangePage");
const FeaturesPage = lazyNamedPage(() => import("./pages/FeaturesPage"), "FeaturesPage");
const HarnessTopologyPage = lazyNamedPage(() => import("./pages/HarnessTopologyPage"), "HarnessTopologyPage");
const HelpPage = lazyNamedPage(() => import("./pages/HelpPage"), "HelpPage");
const HomePage = lazyNamedPage(() => import("./pages/HomePage"), "HomePage");
const OverviewPage = lazyNamedPage(() => import("./pages/OverviewPage"), "OverviewPage");
const PhasesPage = lazyNamedPage(() => import("./pages/PhasesPage"), "PhasesPage");
const PoliciesPage = lazyNamedPage(() => import("./pages/PoliciesPage"), "PoliciesPage");
const ProjectBuilderPage = lazyNamedPage(() => import("./pages/ProjectBuilderPage"), "ProjectBuilderPage");
const ProjectStatusPage = lazyNamedPage(() => import("./pages/ProjectStatusPage"), "ProjectStatusPage");
const ProjectTopologyPage = lazyNamedPage(() => import("./pages/ProjectTopologyPage"), "ProjectTopologyPage");
const ProjectsPage = lazyNamedPage(() => import("./pages/ProjectsPage"), "ProjectsPage");
const QuickStartPage = lazyNamedPage(() => import("./pages/QuickStartPage"), "QuickStartPage");
const ReadinessPage = lazyNamedPage(() => import("./pages/ReadinessPage"), "ReadinessPage");
const ReviewHubPage = lazyNamedPage(() => import("./pages/ReviewHubPage"), "ReviewHubPage");
const SettingsPage = lazyNamedPage(() => import("./pages/SettingsPage"), "SettingsPage");
const SystemStatusPage = lazyNamedPage(() => import("./pages/SystemStatusPage"), "SystemStatusPage");
const MoradinPayloadPage = lazyNamedPage(() => import("./pages/TemplateStudioPage"), "TemplateStudioPage");
const TopologyPage = lazyNamedPage(() => import("./pages/TopologyPage"), "TopologyPage");

function RouteLoadingFallback() {
  return (
    <div aria-live="polite" className="loading-screen">
      Loading workspace...
    </div>
  );
}

function renderLazyRoute(Component: ComponentType) {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Component />
    </Suspense>
  );
}

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/home" element={renderLazyRoute(HomePage)} />
        <Route path="/projects" element={renderLazyRoute(ProjectsPage)} />
        <Route path="/deploy" element={<DeployWorkspaceLayout />}>
          <Route index element={<Navigate to="quick-start" replace />} />
          <Route path="quick-start" element={renderLazyRoute(QuickStartPage)} />
          <Route path="readiness" element={renderLazyRoute(ReadinessPage)} />
          <Route path="map" element={renderLazyRoute(DeployMapPage)} />
          <Route path="builder" element={renderLazyRoute(ProjectBuilderPage)} />
          <Route path="status" element={renderLazyRoute(ProjectStatusPage)} />
        </Route>
        <Route path="/payload" element={renderLazyRoute(MoradinPayloadPage)} />
        <Route path="/template" element={<Navigate to="/payload" replace />} />
        <Route path="/project/:projectId" element={<ProjectWorkspaceLayout />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={renderLazyRoute(OverviewPage)} />
          <Route path="delivery" element={<Navigate to="features" replace />} />
          <Route path="delivery/features" element={renderLazyRoute(FeaturesPage)} />
          <Route path="delivery/phases" element={renderLazyRoute(PhasesPage)} />
          <Route path="governance" element={renderLazyRoute(PoliciesPage)} />
          <Route path="topology" element={<Navigate to="project" replace />} />
          <Route path="topology/project" element={renderLazyRoute(ProjectTopologyPage)} />
          <Route path="topology/harness" element={renderLazyRoute(HarnessTopologyPage)} />
          <Route path="topology/combined" element={renderLazyRoute(TopologyPage)} />
          <Route path="docs" element={renderLazyRoute(DocsPage)} />
          <Route path="operations" element={<Navigate to="loops" replace />} />
          <Route path="operations/loops" element={renderLazyRoute(CyclesPage)} />
          <Route path="operations/status" element={renderLazyRoute(ProjectStatusPage)} />
        </Route>
        <Route path="/reviews" element={<ReviewsWorkspaceLayout />}>
          <Route index element={<Navigate to="queue" replace />} />
          <Route path="queue" element={renderLazyRoute(ReviewHubPage)} />
          <Route path="changes" element={renderLazyRoute(ChangesPage)} />
          <Route path="exchange" element={renderLazyRoute(ExchangePage)} />
          <Route path="archive" element={renderLazyRoute(ArchivePage)} />
        </Route>
        <Route path="/docs" element={renderLazyRoute(DocsPage)} />
        <Route path="/docs/:docId" element={renderLazyRoute(DocDetailPage)} />
        <Route path="/settings" element={<SettingsWorkspaceLayout />}>
          <Route index element={<Navigate to="preferences" replace />} />
          <Route path="preferences" element={renderLazyRoute(SettingsPage)} />
          <Route path="system" element={renderLazyRoute(SystemStatusPage)} />
          <Route path="help" element={renderLazyRoute(HelpPage)} />
        </Route>

        <Route path="/quick-start" element={<Navigate to="/deploy/quick-start" replace />} />
        <Route path="/readiness" element={<Navigate to="/deploy/readiness" replace />} />
        <Route path="/deploy-map" element={<Navigate to="/deploy/map" replace />} />
        <Route path="/builder" element={<Navigate to="/deploy/builder" replace />} />
        <Route path="/project-status" element={<Navigate to="/deploy/status" replace />} />
        <Route path="/system-status" element={<Navigate to="/settings/system" replace />} />
        <Route path="/help" element={<Navigate to="/settings/help" replace />} />
        <Route path="/review" element={<Navigate to="/reviews/queue" replace />} />
        <Route path="/changes" element={<Navigate to="/reviews/changes" replace />} />
        <Route path="/exchange" element={<Navigate to="/reviews/exchange" replace />} />
        <Route path="/archive" element={<Navigate to="/reviews/archive" replace />} />
        <Route path="/effects" element={<Navigate to="/reviews/exchange" replace />} />
        <Route path="/features" element={<LegacyProjectRouteRedirect suffix="delivery/features" />} />
        <Route path="/phases" element={<LegacyProjectRouteRedirect suffix="delivery/phases" />} />
        <Route path="/policies" element={<LegacyProjectRouteRedirect suffix="governance" />} />
        <Route path="/project-topology" element={<LegacyProjectRouteRedirect suffix="topology/project" />} />
        <Route path="/harness-topology" element={<LegacyProjectRouteRedirect suffix="topology/harness" />} />
        <Route path="/topology" element={<LegacyProjectRouteRedirect suffix="topology/combined" />} />
        <Route path="/cycles" element={<LegacyProjectRouteRedirect suffix="operations/loops" />} />
        <Route path="/loop-processes" element={<LegacyProjectRouteRedirect suffix="operations/loops" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
