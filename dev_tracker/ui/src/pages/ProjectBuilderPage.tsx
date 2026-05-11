import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { AssistantActionBar } from "../components/AssistantActionBar";
import { HarnessFlowVisualizer } from "../components/HarnessFlowVisualizer";
import { SeededDeployExamplePanel } from "../components/SeededDeployExamplePanel";
import { StatusChip } from "../components/StatusChip";
import { TemplateFillTree } from "../components/TemplateFillTree";
import { notifyAssistantRunStarted } from "../lib/assistant-activity";
import { DEPLOY_MAP_PREVIEW_STORAGE_KEY, type DeployWorkflowId } from "../lib/deploy-map-model";
import { isOverviewManagerProject, resolveSelectedProjectLabel, writeOverviewActiveProject } from "../lib/overview-project";
import type {
  BuilderProviderListV1,
  BuilderRepoCompletenessResponseV1,
  BuilderStatusV1,
  DeployExistingProjectResponseV1,
  DiscoveryFollowOnPlanResponseV1,
  DiscoveryFollowOnPromptIdV1,
  DiscoveryIntakeV1,
  DiscoveryPromptBundleV1,
  DiscoverySessionV1,
  GenerateProjectRepoResponseV1,
  ImportHarnessResponseV1,
  ProjectScanResponseV1,
} from "../lib/contracts";
import {
  answerDiscoverySession,
  buildDiscoveryFollowOnPlan,
  buildDiscoveryPromptBundle,
  checkBuilderRepoCompleteness,
  createLocalRepo,
  deployExistingProject,
  executeRemoteSsh,
  generateDiscoverySession,
  generateProjectRepoFromDiscovery,
  importHarnessBundle,
  importHarnessPath,
  loadBuilderProviders,
  loadBuilderStatus,
  runAssistantAction,
  runProjectBaselineScan,
  startDiscoverySession,
  testRemoteSsh,
} from "../lib/loaders";
import { buildRemoteListCommand, buildRemoteSidecarCheckCommand } from "../lib/remote-command-utils";
import { useTracker } from "../lib/tracker-context";
import { useOverviewActiveProject } from "../lib/use-overview-active-project";

type BuilderWorkflow = DeployWorkflowId;

const WORKFLOW_OPTIONS = [
  {
    id: "new_project" as const,
    label: "New Project",
    detail: "Seed a fresh repo from discovery context and the Moradin payload.",
  },
  {
    id: "existing_project" as const,
    label: "Current Project",
    detail: "Deploy a guarded sidecar into a selected repo and plan the follow-on work.",
  },
  {
    id: "import_existing_harness" as const,
    label: "Import Existing Harness",
    detail: "Bring an existing harness in by local path or uploaded bundle.",
  },
];

const STRUCTURED_CONTEXT_FIELDS = [
  {
    key: "project_goal",
    label: "Project Goal",
    placeholder: "What should this harness deployment achieve?",
    fullWidth: true,
  },
  {
    key: "users",
    label: "Users",
    placeholder: "Who will use or operate this project?",
  },
  {
    key: "constraints",
    label: "Constraints",
    placeholder: "Boundaries, existing rules, or hard requirements",
  },
  {
    key: "timeline",
    label: "Timeline",
    placeholder: "Delivery window or rollout sequence",
  },
  {
    key: "integrations",
    label: "Integrations",
    placeholder: "External systems, APIs, or services",
  },
  {
    key: "compliance",
    label: "Compliance",
    placeholder: "Security, audit, or regulatory requirements",
  },
  {
    key: "deployment_target",
    label: "Deployment Target",
    placeholder: "Kubernetes, VM, local service, sidecar, etc.",
  },
  {
    key: "other_context",
    label: "Other Context",
    placeholder: "Anything important that does not fit the boxes above",
  },
] as const satisfies Array<{
  key: keyof DiscoveryIntakeV1;
  label: string;
  placeholder: string;
  fullWidth?: boolean;
}>;

const FOLLOW_ON_PROMPT_ORDER: DiscoveryFollowOnPromptIdV1[] = [
  "bootstrap_hydration",
  "phase_planning",
  "phase_1_execution",
  "run_all_phases",
];

function deriveOverwriteConfirmation(input: string): string {
  const normalized = input.trim().replaceAll("\\", "/");
  if (!normalized) {
    return "";
  }
  const parts = normalized.split("/").filter(Boolean);
  const last = parts[parts.length - 1] ?? normalized;
  return `overwrite:${last}`;
}

function deriveCriticalGapOverrideConfirmation(targetRepo: string): string {
  const normalized = targetRepo.trim().replaceAll("\\", "/").replace(/\/+$/g, "");
  const parts = normalized.split("/").filter(Boolean);
  const targetName = parts[parts.length - 1] ?? "target";
  return `override-critical-gaps:${targetName}`;
}

function formatDiscoveryStateLabel(session: DiscoverySessionV1 | null): string {
  if (!session) {
    return "not started";
  }
  return session.status.replaceAll("_", " ");
}

function toStepTone(ready: boolean): "success" | "warning" {
  return ready ? "success" : "warning";
}

async function toBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export function ProjectBuilderPage() {
  const location = useLocation();
  const { settings, status } = useTracker();
  const activeProject = useOverviewActiveProject();
  const demoMode = useMemo(() => new URLSearchParams(location.search).get("demo") === "seeded", [location.search]);
  const [builderStatus, setBuilderStatus] = useState<BuilderStatusV1 | null>(null);
  const [builderProviders, setBuilderProviders] = useState<BuilderProviderListV1 | null>(null);
  const [workflow, setWorkflow] = useState<BuilderWorkflow>("new_project");
  const [targetMode, setTargetMode] = useState<"local" | "remote_ssh">("local");
  const [selectedRepo, setSelectedRepo] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState(settings.defaultSshProfileId);
  const [newRepoName, setNewRepoName] = useState("");
  const [repoOverwrite, setRepoOverwrite] = useState(false);
  const [repoOverwriteConfirmation, setRepoOverwriteConfirmation] = useState("");
  const [importSourcePath, setImportSourcePath] = useState("");
  const [importDestination, setImportDestination] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importOverwrite, setImportOverwrite] = useState(false);
  const [importOverwriteConfirmation, setImportOverwriteConfirmation] = useState("");
  const [repoCompleteness, setRepoCompleteness] = useState<BuilderRepoCompletenessResponseV1 | null>(null);
  const [projectScan, setProjectScan] = useState<ProjectScanResponseV1 | null>(null);
  const [discoverySession, setDiscoverySession] = useState<DiscoverySessionV1 | null>(null);
  const [discoveryAnswers, setDiscoveryAnswers] = useState<Record<string, string>>({});
  const [discoveryProvider, setDiscoveryProvider] = useState<"none" | "openai" | "codex_cli" | "claude_code">(settings.defaultDiscoveryProvider);
  const [discoveryModel, setDiscoveryModel] = useState(settings.defaultDiscoveryModel);
  const [promptBundlePreview, setPromptBundlePreview] = useState<DiscoveryPromptBundleV1 | null>(null);
  const [followOnPlan, setFollowOnPlan] = useState<DiscoveryFollowOnPlanResponseV1 | null>(null);
  const [selectedFollowOnPromptId, setSelectedFollowOnPromptId] = useState<DiscoveryFollowOnPromptIdV1 | "">("");
  const [generateProfile, setGenerateProfile] = useState<"web_app" | "data_pipeline" | "agent_platform" | "internal_tooling">("web_app");
  const [generateDestination, setGenerateDestination] = useState("");
  const [generateOverwrite, setGenerateOverwrite] = useState(false);
  const [generateOverwriteConfirmation, setGenerateOverwriteConfirmation] = useState("");
  const [sidecarDir, setSidecarDir] = useState(".moradins-harness");
  const [sidecarOverwrite, setSidecarOverwrite] = useState(false);
  const [sidecarOverwriteConfirmation, setSidecarOverwriteConfirmation] = useState("");
  const [criticalGapPolicy, setCriticalGapPolicy] = useState<"block_with_override" | "warn_only" | "hard_block">("block_with_override");
  const [criticalGapOverrideReason, setCriticalGapOverrideReason] = useState("");
  const [criticalGapOverrideConfirmation, setCriticalGapOverrideConfirmation] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sshResult, setSshResult] = useState("");
  const [assistantStatus, setAssistantStatus] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [latestGenerateResult, setLatestGenerateResult] = useState<GenerateProjectRepoResponseV1 | null>(null);
  const [latestDeployResult, setLatestDeployResult] = useState<DeployExistingProjectResponseV1 | null>(null);
  const [latestImportResult, setLatestImportResult] = useState<ImportHarnessResponseV1 | null>(null);
  const [intake, setIntake] = useState<DiscoveryIntakeV1>({
    input_mode: "onboarding",
    project_prompt: "",
    project_goal: "",
    users: "",
    constraints: "",
    timeline: "",
    integrations: "",
    compliance: "",
    deployment_target: "",
    other_context: "",
  });

  const selectedProfile = settings.sshProfiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const knownRepos = builderStatus?.known_repos ?? [];
  const currentSelectedProjectRepo = useMemo(
    () => knownRepos.find((repo) => repo.name === activeProject) ?? null,
    [activeProject, knownRepos],
  );
  const currentSelectedProjectTarget = currentSelectedProjectRepo?.name ?? (!isOverviewManagerProject(activeProject) ? activeProject.trim() : "");
  const currentSelectedProjectLabel = currentSelectedProjectRepo?.name ?? resolveSelectedProjectLabel(activeProject);
  const currentSelectedProjectDetail = currentSelectedProjectRepo
    ? currentSelectedProjectRepo.path
    : isOverviewManagerProject(activeProject)
      ? "The manager repo is pinned. Choose a tracked project to deploy into a sidecar."
      : activeProject
        ? "The pinned project is not in the tracked repo list yet."
        : "Choose a project from the header switcher or Projects workspace to pin it here.";
  const isBusy = busyAction.length > 0;
  const currentTargetRepo = useMemo(() => {
    if (workflow === "new_project") {
      return generateDestination.trim();
    }
    if (workflow === "existing_project") {
      return selectedRepo.trim();
    }
    return importDestination.trim();
  }, [generateDestination, importDestination, selectedRepo, workflow]);
  const selectedFollowOnPrompt = useMemo(
    () => followOnPlan?.prompts.find((prompt) => prompt.prompt_id === selectedFollowOnPromptId) ?? null,
    [followOnPlan?.prompts, selectedFollowOnPromptId],
  );
  const expectedCreateOverwrite = useMemo(() => deriveOverwriteConfirmation(newRepoName), [newRepoName]);
  const expectedImportOverwrite = useMemo(() => deriveOverwriteConfirmation(importDestination), [importDestination]);
  const expectedGenerateOverwrite = useMemo(() => deriveOverwriteConfirmation(generateDestination), [generateDestination]);
  const expectedSidecarOverwrite = useMemo(
    () => deriveOverwriteConfirmation(`${selectedRepo.trim().replace(/\/+$/g, "")}/${sidecarDir.trim() || ".moradins-harness"}`),
    [selectedRepo, sidecarDir],
  );
  const expectedCriticalGapOverride = useMemo(() => deriveCriticalGapOverrideConfirmation(selectedRepo), [selectedRepo]);
  const activeGeneratedFiles = latestDeployResult?.generated_files ?? latestGenerateResult?.generated_files ?? [];
  const deploymentReady =
    workflow === "new_project"
      ? Boolean(latestGenerateResult)
      : workflow === "existing_project"
        ? Boolean(latestDeployResult)
        : Boolean(latestImportResult);
  const followOnPlanReady =
    Boolean(discoverySession?.synthesis) &&
    Boolean(currentTargetRepo) &&
    deploymentReady &&
    (workflow !== "existing_project" || Boolean(projectScan));
  const assistantRuntime = status?.assistant_runtimes?.[settings.preferredAssistant] ?? null;
  const browserAccessSummary = status?.ui_access?.browser_access_summary ?? "Open the web UI locally or through SSH local port forwarding.";
  const executionHostSummary = status?.ui_access?.execution_host_summary ?? "Assistant commands run on the Linux host that launched this harness.";
  const alignmentSummary = followOnPlan?.alignment_state ?? null;
  const assistantExecutionScope =
    targetMode === "local" &&
    ((workflow === "existing_project" && Boolean(selectedRepo.trim())) ||
      (workflow === "new_project" && Boolean(latestGenerateResult && generateDestination.trim())) ||
      (workflow === "import_existing_harness" && Boolean(latestImportResult && importDestination.trim())))
      ? "local_repo"
      : "manager_repo";
  const artifactLinks = useMemo(
    () =>
      [
        promptBundlePreview?.prompt_context_artifact_path
          ? { label: "Prompt Context", path: promptBundlePreview.prompt_context_artifact_path }
          : null,
        promptBundlePreview?.context_pack_artifact_path
          ? { label: "Context Pack", path: promptBundlePreview.context_pack_artifact_path }
          : null,
        latestDeployResult?.template_fill_map_artifact_paths?.markdown
          ? { label: "Payload Fill Map", path: latestDeployResult.template_fill_map_artifact_paths.markdown }
          : null,
        latestGenerateResult?.template_fill_map_artifact_paths?.markdown
          ? { label: "Payload Fill Map", path: latestGenerateResult.template_fill_map_artifact_paths.markdown }
          : null,
        followOnPlan?.artifact_paths.bootstrap_prompt_markdown
          ? { label: "Bootstrap Prompt", path: followOnPlan.artifact_paths.bootstrap_prompt_markdown }
          : null,
        followOnPlan?.artifact_paths.phase_plan_markdown
          ? { label: "Phase Plan", path: followOnPlan.artifact_paths.phase_plan_markdown }
          : null,
        followOnPlan?.artifact_paths.execution_prompts_markdown
          ? { label: "Execution Prompts", path: followOnPlan.artifact_paths.execution_prompts_markdown }
          : null,
        followOnPlan?.artifact_paths.alignment_state_markdown
          ? { label: "Alignment State", path: followOnPlan.artifact_paths.alignment_state_markdown }
          : null,
        discoverySession?.approval?.approval_artifact_path
          ? { label: "Approval Artifact", path: discoverySession.approval.approval_artifact_path }
          : null,
      ].filter((row): row is { label: string; path: string } => Boolean(row?.path)),
    [
      discoverySession?.approval?.approval_artifact_path,
      followOnPlan?.artifact_paths.alignment_state_markdown,
      followOnPlan?.artifact_paths.bootstrap_prompt_markdown,
      followOnPlan?.artifact_paths.execution_prompts_markdown,
      followOnPlan?.artifact_paths.phase_plan_markdown,
      latestDeployResult?.template_fill_map_artifact_paths?.markdown,
      latestGenerateResult?.template_fill_map_artifact_paths?.markdown,
      promptBundlePreview?.context_pack_artifact_path,
      promptBundlePreview?.prompt_context_artifact_path,
    ],
  );
  const assistantPrompt = useMemo(() => {
    if (selectedFollowOnPrompt?.prompt) {
      return selectedFollowOnPrompt.prompt;
    }
    if (promptBundlePreview?.assembled_prompt) {
      return promptBundlePreview.assembled_prompt;
    }
    const lines = [
      `workflow=${workflow}`,
      `target_mode=${targetMode}`,
      `target_repo=${currentTargetRepo || "unselected"}`,
      `approval=${discoverySession?.approval?.approved ? "approved" : "pending"}`,
      `critical_gap_count=${projectScan?.critical_gaps.length ?? 0}`,
      `follow_on_prompt=${selectedFollowOnPromptId || "none"}`,
      `alignment_overall=${alignmentSummary?.summary.overall_status ?? "unavailable"}`,
      `alignment_manual_required=${alignmentSummary?.summary.manual_required_count ?? 0}`,
      `alignment_missing=${alignmentSummary?.summary.missing_count ?? 0}`,
      `alignment_next_action=${alignmentSummary?.next_recommended_action?.next_action ?? "none"}`,
      `alignment_artifact=${followOnPlan?.artifact_paths.alignment_state_markdown ?? "unset"}`,
    ];
    return [
      "Review the Moradins Harness builder state and recommend the next operator action.",
      "Do not apply changes automatically.",
      "",
      ...lines,
    ].join("\n");
  }, [
    currentTargetRepo,
    discoverySession?.approval?.approved,
    alignmentSummary?.next_recommended_action?.next_action,
    alignmentSummary?.summary.manual_required_count,
    alignmentSummary?.summary.missing_count,
    alignmentSummary?.summary.overall_status,
    followOnPlan?.artifact_paths.alignment_state_markdown,
    projectScan?.critical_gaps.length,
    promptBundlePreview?.assembled_prompt,
    selectedFollowOnPrompt?.prompt,
    selectedFollowOnPromptId,
    targetMode,
    workflow,
  ]);
  const stepRows = [
    {
      label: "1. Target Repo",
      value: currentTargetRepo || "choose repo",
      ready: Boolean(currentTargetRepo),
    },
    {
      label: "2. Project Context",
      value: formatDiscoveryStateLabel(discoverySession),
      ready: Boolean(discoverySession),
    },
    {
      label: "3. Deploy Harness",
      value: deploymentReady ? "artifacts ready" : "waiting for deploy",
      ready: deploymentReady,
    },
    {
      label: "4. Build Project Phases",
      value: followOnPlan?.phase_plan.next_recommended_phase_id ?? "phase plan pending",
      ready: Boolean(followOnPlan),
    },
    {
      label: "5. Run Phase Prompt",
      value: selectedFollowOnPrompt?.title ?? "choose a prompt",
      ready: Boolean(selectedFollowOnPrompt),
    },
  ];

  useEffect(() => {
    void refreshBuilderStatus();
  }, []);

  useEffect(() => {
    if (workflow === "existing_project" && !selectedRepo && currentSelectedProjectTarget) {
      setSelectedRepo(currentSelectedProjectTarget);
    }
  }, [currentSelectedProjectTarget, selectedRepo, workflow]);

  useEffect(() => {
    const generatedFiles = latestDeployResult?.generated_files ?? latestGenerateResult?.generated_files ?? [];
    if (generatedFiles.length === 0) {
      return;
    }
    localStorage.setItem(
      DEPLOY_MAP_PREVIEW_STORAGE_KEY,
      JSON.stringify({
        version: "DeployMapPreviewV1",
        generated_at: new Date().toISOString(),
        workflow,
        generated_files: generatedFiles,
      }),
    );
  }, [latestDeployResult?.generated_files, latestGenerateResult?.generated_files, workflow]);

  function clearRunState() {
    setMessage("");
    setError("");
  }

  function clearPlanningOutputs() {
    setPromptBundlePreview(null);
    setFollowOnPlan(null);
    setSelectedFollowOnPromptId("");
    setAssistantStatus("");
  }

  function resetWorkflowOutputs(nextWorkflow: BuilderWorkflow) {
    setWorkflow(nextWorkflow);
    clearRunState();
    clearPlanningOutputs();
    setRepoCompleteness(null);
    setProjectScan(null);
    setLatestGenerateResult(null);
    setLatestDeployResult(null);
    setLatestImportResult(null);
    setSshResult("");
  }

  function updateIntakeField<Key extends keyof DiscoveryIntakeV1>(key: Key, value: DiscoveryIntakeV1[Key]) {
    setIntake((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function refreshBuilderStatus() {
    const [nextStatus, providers] = await Promise.all([loadBuilderStatus(), loadBuilderProviders()]);
    setBuilderStatus(nextStatus);
    setBuilderProviders(providers);
    const preferredPinnedRepo =
      !isOverviewManagerProject(activeProject) && activeProject
        ? nextStatus?.known_repos.find((repo) => repo.name === activeProject)?.name ?? ""
        : "";
    if (!selectedRepo && preferredPinnedRepo) {
      setSelectedRepo(preferredPinnedRepo);
    } else if (!selectedRepo && nextStatus?.known_repos[0]?.name) {
      setSelectedRepo(nextStatus.known_repos[0].name);
    }
    if (!discoveryModel.trim()) {
      const providerDefault = providers?.providers.find((provider) => provider.provider_id === discoveryProvider)?.default_model ?? "";
      setDiscoveryModel(providerDefault);
    }
  }

  function selectTrackedProject(repoName: string, options?: { pinCurrent?: boolean }) {
    const normalized = repoName.trim();
    setSelectedRepo(normalized);
    if (options?.pinCurrent && normalized) {
      writeOverviewActiveProject(normalized);
    }
  }

  function onUseCurrentSelectedProject() {
    if (!currentSelectedProjectTarget) {
      return;
    }
    if (workflow !== "existing_project") {
      resetWorkflowOutputs("existing_project");
    }
    selectTrackedProject(currentSelectedProjectTarget, { pinCurrent: true });
  }

  async function onTestRemote(command: string) {
    if (!selectedProfile) {
      setSshResult("Select an SSH profile.");
      return;
    }
    const response =
      command === "pwd"
        ? await testRemoteSsh({ target: selectedProfile })
        : await executeRemoteSsh({ target: selectedProfile, command });
    setSshResult(response ? ("detail" in response ? response.detail : [response.status, response.stdout, response.stderr].filter(Boolean).join(" | ")) : "SSH request failed.");
  }

  async function onCreateRepo() {
    if (!newRepoName.trim()) {
      return;
    }
    setBusyAction("create_repo");
    clearRunState();
    const response = await createLocalRepo({
      repo_name: newRepoName.trim(),
      overwrite: repoOverwrite,
      overwrite_confirmation: repoOverwrite ? repoOverwriteConfirmation : undefined,
    });
    setBusyAction("");
    if (!response) {
      setError("Create repo failed.");
      return;
    }
    setMessage(`Created ${response.repo_path}`);
    selectTrackedProject(newRepoName.trim(), { pinCurrent: true });
    await refreshBuilderStatus();
  }

  async function onCheckCompleteness() {
    if (!selectedRepo.trim()) {
      return;
    }
    setBusyAction("repo_completeness");
    clearRunState();
    const response = await checkBuilderRepoCompleteness({
      target_repo: selectedRepo.trim(),
      profile: "harness_core",
    });
    setBusyAction("");
    if (!response) {
      setError("Repo completeness check failed.");
      return;
    }
    setRepoCompleteness(response);
    setMessage(`Repo completeness ${response.summary.pass_count}/${response.summary.total}`);
  }

  async function onStartDiscovery() {
    setBusyAction("start_discovery");
    clearRunState();
    clearPlanningOutputs();
    const response = await startDiscoverySession({
      intake,
      provider: discoveryProvider,
      model: discoveryModel.trim() || undefined,
    });
    setBusyAction("");
    if (!response) {
      setError("Discovery session start failed.");
      return;
    }
    setDiscoverySession(response);
    setDiscoveryAnswers(response.answers ?? {});
    setLatestGenerateResult(null);
    setLatestDeployResult(null);
    setLatestImportResult(null);
    setMessage(`Session started: ${response.session_id}`);
  }

  async function onGenerateDiscovery() {
    if (!discoverySession) {
      return;
    }
    setBusyAction("generate_discovery");
    clearRunState();
    clearPlanningOutputs();
    let session = discoverySession;
    if (Object.keys(discoveryAnswers).length > 0) {
      const answered = await answerDiscoverySession({
        session_id: discoverySession.session_id,
        answers: discoveryAnswers,
      });
      if (answered) {
        session = answered;
        setDiscoverySession(answered);
      }
    }
    const generated = await generateDiscoverySession(session.session_id);
    setBusyAction("");
    if (!generated) {
      setError("Discovery generation failed.");
      return;
    }
    setDiscoverySession(generated);
    setMessage(`Discovery state: ${generated.status}`);
  }

  async function onPreviewPrompt() {
    if (selectedFollowOnPrompt) {
      setAssistantStatus(`Prompt ready: ${selectedFollowOnPrompt.title}`);
      return;
    }
    if (!discoverySession) {
      setAssistantStatus("Start discovery first.");
      return;
    }
    const stage = discoverySession.status === "synthesized" ? "synthesis" : "questions";
    const response = await buildDiscoveryPromptBundle({
      session_id: discoverySession.session_id,
      stage,
      selected_profile: generateProfile,
    });
    if (!response) {
      setAssistantStatus("Prompt preview failed.");
      return;
    }
    setPromptBundlePreview(response);
    setAssistantStatus(`Prompt preview ready: ${response.prompt_template_id ?? response.stage}`);
  }

  async function onRunAssistant() {
    setAssistantBusy(true);
    setAssistantStatus("");
    const response = await runAssistantAction({
      assistant: settings.preferredAssistant,
      source_mode: "builder",
      execution_scope: assistantExecutionScope,
      prompt: assistantPrompt,
      session_id: discoverySession?.session_id,
      target_repo: currentTargetRepo || undefined,
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

  async function onRunProjectScan() {
    if (!selectedRepo.trim()) {
      return;
    }
    setBusyAction("project_scan");
    clearRunState();
    clearPlanningOutputs();
    const response = await runProjectBaselineScan({
      target_repo: selectedRepo.trim(),
      target_mode: targetMode,
      remote_target: targetMode === "remote_ssh" ? selectedProfile ?? undefined : undefined,
      session_id: discoverySession?.session_id,
    });
    setBusyAction("");
    if (!response) {
      setError("Project scan failed.");
      return;
    }
    setProjectScan(response);
    setMessage(`Project scan complete with ${response.critical_gaps.length} critical gaps.`);
  }

  async function onGenerateProject() {
    if (!discoverySession || !generateDestination.trim()) {
      return;
    }
    setBusyAction("generate_project");
    clearRunState();
    clearPlanningOutputs();
    const response = await generateProjectRepoFromDiscovery({
      session_id: discoverySession.session_id,
      profile: generateProfile,
      destination_repo: generateDestination.trim(),
      overwrite: generateOverwrite,
      overwrite_confirmation: generateOverwrite ? generateOverwriteConfirmation : undefined,
    });
    setBusyAction("");
    if (!response) {
      setError("Generate project repo failed.");
      return;
    }
    setLatestGenerateResult(response);
    setLatestDeployResult(null);
    setLatestImportResult(null);
    setMessage(`Generated repo at ${response.destination_path}`);
  }

  async function onDeploySidecar() {
    if (!discoverySession || !selectedRepo.trim()) {
      return;
    }
    setBusyAction("deploy_sidecar");
    clearRunState();
    clearPlanningOutputs();
    const response = await deployExistingProject({
      session_id: discoverySession.session_id,
      target_repo: selectedRepo.trim(),
      target_mode: targetMode,
      remote_target: targetMode === "remote_ssh" ? selectedProfile ?? undefined : undefined,
      mode: "sidecar",
      sidecar_dir: sidecarDir,
      overwrite_sidecar: sidecarOverwrite,
      overwrite_confirmation: sidecarOverwrite ? sidecarOverwriteConfirmation : undefined,
      critical_gap_policy: criticalGapPolicy,
      critical_gap_override_reason: criticalGapOverrideReason,
      critical_gap_override_confirmation: criticalGapOverrideConfirmation,
    });
    setBusyAction("");
    if (!response) {
      setError("Deploy sidecar failed.");
      return;
    }
    setLatestDeployResult(response);
    setLatestGenerateResult(null);
    setLatestImportResult(null);
    setMessage(`Sidecar deployed to ${response.sidecar_path}`);
  }

  async function onImportHarness(mode: "path" | "bundle") {
    if (!importDestination.trim()) {
      return;
    }
    setBusyAction(`import_${mode}`);
    clearRunState();
    clearPlanningOutputs();
    const response =
      mode === "path"
        ? await importHarnessPath({
            source_path: importSourcePath.trim(),
            destination_repo: importDestination.trim(),
            overwrite: importOverwrite,
            overwrite_confirmation: importOverwrite ? importOverwriteConfirmation : undefined,
          })
        : await importHarnessBundle({
            destination_repo: importDestination.trim(),
            filename: importFile?.name,
            bundle_base64: importFile ? await toBase64(importFile) : "",
            overwrite: importOverwrite,
            overwrite_confirmation: importOverwrite ? importOverwriteConfirmation : undefined,
          });
    setBusyAction("");
    if (!response) {
      setError(`Import by ${mode} failed.`);
      return;
    }
    setLatestImportResult(response);
    setLatestGenerateResult(null);
    setLatestDeployResult(null);
    setMessage(`Imported harness to ${response.destination_path}`);
  }

  async function onBuildFollowOnPhasePlan() {
    if (!discoverySession || !currentTargetRepo) {
      return;
    }
    setBusyAction("build_follow_on_plan");
    clearRunState();
    const response = await buildDiscoveryFollowOnPlan({
      session_id: discoverySession.session_id,
      target_repo: currentTargetRepo,
      selected_profile: generateProfile,
    });
    setBusyAction("");
    if (!response) {
      setError("Build project phases failed.");
      return;
    }
    setFollowOnPlan(response);
    setSelectedFollowOnPromptId("bootstrap_hydration");
    setAssistantStatus("Follow-on prompts are ready in the assistant surface.");
    setMessage(`Phase plan ready with ${response.phase_plan.phases.length} phases.`);
  }

  return (
    <div className="page-grid">
      {demoMode ? (
        <section style={{ gridColumn: "span 12" }}>
          <SeededDeployExamplePanel surface="builder" />
          <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
            Preview mode is read-only. Review the staged Builder shape here, then return to Quick Start or open the live Builder without the demo query to work for real.
          </p>
        </section>
      ) : null}

      <section className="card card-pad workspace-header-card compact" style={{ gridColumn: "span 12" }}>
        <div className="workspace-header-copy">
          <div>
            <p className="card-head">Deploy Builder</p>
            <h2 className="workspace-header-title">Methodical multi-repo harness control</h2>
            <p className="workspace-header-description">
              Keep the deploy loop intact while making the operator path obvious: target a repo, capture context, deploy the harness, then move into phase prompts.
            </p>
            <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
              {executionHostSummary}
            </p>
            <p className="metric-sub" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
              Browser access: {browserAccessSummary}
            </p>
            <p className="metric-sub" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
              Allowlisted root: {builderStatus?.allowlisted_root ?? "loading"} | current-project mode {builderStatus?.existing_project_mode_enabled ? "enabled" : "disabled"}
            </p>
            {status?.ui_access?.remote_ssh_tunnel_example ? (
              <p className="metric-sub mono" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
                Remote harness host: {status.ui_access.remote_ssh_tunnel_example}
              </p>
            ) : null}
          </div>
          <div className="workspace-header-actions">
            <Link className="btn primary" to="/deploy/map">
              Open Deploy Map
            </Link>
            <Link className="btn" to="/deploy/status">
              Open Verify
            </Link>
            <Link className="btn" to="/settings/system">
              System Status
            </Link>
          </div>
        </div>
        <div className="workspace-header-chips">
          <StatusChip tone={currentTargetRepo ? "success" : "info"}>{currentTargetRepo ? `target ${currentTargetRepo}` : "choose target repo"}</StatusChip>
          <StatusChip tone={currentSelectedProjectTarget ? "success" : activeProject ? "warning" : "info"}>{`current project ${currentSelectedProjectLabel}`}</StatusChip>
          <StatusChip tone={workflow === "existing_project" && targetMode === "remote_ssh" ? "warning" : "success"}>
            {`deploy mode ${workflow === "existing_project" ? targetMode : "local"}`}
          </StatusChip>
          <StatusChip tone={discoverySession?.approval?.approved ? "success" : "warning"}>
            {`approval ${discoverySession?.approval?.approved ? "approved" : "pending"}`}
          </StatusChip>
          <StatusChip tone={assistantRuntime?.availability_status === "available" ? "success" : "warning"}>
            {`assistant ${assistantRuntime?.availability_status ?? "unknown"}`}
          </StatusChip>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 8" }}>
        <p className="card-head">Primary Route</p>
        <div style={{ display: "grid", gap: "0.85rem", marginTop: "0.8rem" }}>
          {[
            ["1", "Target Repo", currentSelectedProjectTarget ? `Reuse ${currentSelectedProjectLabel} from the current project switcher or choose another tracked repo.` : "Choose the workflow and the repo destination before anything writes."],
            ["2", "Project Context", "Use the structured boxes first, with freeform prompt mode tucked into advanced settings."],
            ["3", "Deploy Harness", "Generate, deploy, or import the harness without changing the core guarded loop."],
            ["4", "Build Project Phases", "Create a typed phase plan and follow-on prompts from the deployed context."],
            ["5", "Run Phase Prompt", "Select the next prompt, then use assistant actions to copy or run it explicitly."],
          ].map(([step, title, detail]) => (
            <div key={step} style={{ display: "grid", gridTemplateColumns: "2rem minmax(0, 1fr)", gap: "0.75rem", alignItems: "start" }}>
              <span className="shell-badge" style={{ justifyContent: "center" }}>
                {step}
              </span>
              <div>
                <strong style={{ display: "block" }}>{title}</strong>
                <p className="metric-sub" style={{ marginTop: "0.25rem", marginBottom: 0 }}>
                  {detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 4" }}>
        <p className="card-head">Progress</p>
        <div style={{ display: "grid", gap: "0.7rem", marginTop: "0.8rem" }}>
          {stepRows.map((row) => (
            <div key={row.label} style={{ display: "grid", gap: "0.3rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center" }}>
                <span className="metric-sub">{row.label}</span>
                <StatusChip tone={toStepTone(row.ready)}>{row.ready ? "ready" : "pending"}</StatusChip>
              </div>
              <span className="mono" style={{ fontSize: "0.85rem" }}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
        {artifactLinks.length > 0 ? (
          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.9rem" }}>
            {artifactLinks.map((artifact) => (
              <a key={`${artifact.label}:${artifact.path}`} className="btn" href={artifact.path} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
                {artifact.label}
              </a>
            ))}
          </div>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Step 1</p>
        <h3 style={{ marginTop: "0.25rem" }}>Target Repo</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          Pick the target path first. The builder can inherit the current project from the top-bar switcher so the rest of the flow stays focused on one repo.
        </p>

        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
          {WORKFLOW_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className="btn"
              onClick={() => {
                resetWorkflowOutputs(option.id);
                if (option.id === "existing_project" && currentSelectedProjectTarget) {
                  selectTrackedProject(currentSelectedProjectTarget, { pinCurrent: true });
                }
              }}
              disabled={demoMode}
              style={{
                textAlign: "left",
                borderColor: workflow === option.id ? "var(--cyan)" : undefined,
              }}
            >
              <strong>{option.label}</strong>
              <span style={{ display: "block", marginTop: "0.35rem", fontSize: "0.82rem", opacity: 0.82 }}>{option.detail}</span>
            </button>
          ))}
        </div>

        {workflow === "new_project" ? (
          <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
            <label className="field-block">
              <span className="field-label">Destination Repo</span>
              <input className="input" value={generateDestination} onChange={(event) => setGenerateDestination(event.target.value)} placeholder="new-harness-project" />
            </label>
            <label className="field-block">
              <span className="field-label">Template Profile</span>
              <select className="select" value={generateProfile} onChange={(event) => setGenerateProfile(event.target.value as typeof generateProfile)}>
                <option value="web_app">web_app</option>
                <option value="data_pipeline">data_pipeline</option>
                <option value="agent_platform">agent_platform</option>
                <option value="internal_tooling">internal_tooling</option>
              </select>
            </label>
          </div>
        ) : null}

        {workflow === "existing_project" ? (
          <>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", marginTop: "0.85rem" }}>
              <div className="builder-help-panel">
                <strong style={{ display: "block" }}>Current Selected Project</strong>
                <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                  {currentSelectedProjectLabel}
                </p>
                <p className="metric-sub mono" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
                  {currentSelectedProjectDetail}
                </p>
              </div>
              <div className="builder-help-panel">
                <strong style={{ display: "block" }}>Current-Project Shortcut</strong>
                <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
                  Reuse the pinned project instead of starting from a generic existing-project selector every time.
                </p>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
                  <button className="btn" type="button" onClick={onUseCurrentSelectedProject} disabled={demoMode || !currentSelectedProjectTarget}>
                    Use Current Selected Project
                  </button>
                  <Link className="btn" to="/projects">
                    Open Projects
                  </Link>
                </div>
              </div>
            </div>
            <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
              <label className="field-block">
                <span className="field-label">Project Target</span>
                <select className="select" value={selectedRepo} onChange={(event) => selectTrackedProject(event.target.value, { pinCurrent: Boolean(event.target.value) })}>
                  <option value="">Select a tracked project</option>
                  {knownRepos.map((repo) => (
                    <option key={repo.name} value={repo.name}>
                      {repo.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-block">
                <span className="field-label">Deploy Location</span>
                <select className="select" value={targetMode} onChange={(event) => setTargetMode(event.target.value === "remote_ssh" ? "remote_ssh" : "local")}>
                  <option value="local">Local</option>
                  <option value="remote_ssh">Remote SSH</option>
                </select>
              </label>
              {targetMode === "remote_ssh" ? (
                <label className="field-block">
                  <span className="field-label">SSH Profile</span>
                  <select className="select" value={selectedProfileId} onChange={(event) => setSelectedProfileId(event.target.value)}>
                    <option value="">Select SSH profile</option>
                    {settings.sshProfiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="field-block">
                <span className="field-label">Sidecar Dir</span>
                <input className="input" value={sidecarDir} onChange={(event) => setSidecarDir(event.target.value)} />
              </label>
            </div>
            {targetMode === "remote_ssh" ? (
              <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
                Remote project actions use the saved SSH profile below and stay inside the selected allowlisted root.
              </p>
            ) : null}
          </>
        ) : null}

        {workflow === "import_existing_harness" ? (
          <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
            <label className="field-block" style={{ gridColumn: "1 / -1" }}>
              <span className="field-label">Import Destination</span>
              <input className="input" value={importDestination} onChange={(event) => setImportDestination(event.target.value)} placeholder="imported-harness" />
            </label>
            <label className="field-block" style={{ gridColumn: "1 / -1" }}>
              <span className="field-label">Local Harness Path</span>
              <input className="input mono" value={importSourcePath} onChange={(event) => setImportSourcePath(event.target.value)} placeholder="/path/to/existing-harness" />
            </label>
            <label className="field-block" style={{ gridColumn: "1 / -1" }}>
              <span className="field-label">Harness Bundle</span>
              <input className="input" type="file" onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} />
            </label>
          </div>
        ) : null}

            <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <StatusChip tone={currentTargetRepo ? "success" : "warning"}>{currentTargetRepo ? `target ${currentTargetRepo}` : "target not selected"}</StatusChip>
          {workflow === "existing_project" ? (
            <StatusChip tone={selectedRepo && currentSelectedProjectTarget === selectedRepo ? "success" : "info"}>
              {selectedRepo && currentSelectedProjectTarget === selectedRepo ? "using pinned project" : "manual project selection"}
            </StatusChip>
          ) : null}
          <StatusChip tone="info">{`assistant ${settings.preferredAssistant === "claude_code" ? "Claude Code CLI" : "Codex CLI"}`}</StatusChip>
        </div>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Step 2</p>
        <h3 style={{ marginTop: "0.25rem" }}>Project Context</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          Structured intake is the default. Freeform prompt mode is still available, but it now lives in advanced settings instead of leading the page.
        </p>

        <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
          {STRUCTURED_CONTEXT_FIELDS.map((field) => (
            <label key={field.key} className="field-block" style={"fullWidth" in field && field.fullWidth ? { gridColumn: "1 / -1" } : undefined}>
              <span className="field-label">{field.label}</span>
              {field.key === "other_context" ? (
                <textarea
                  className="input"
                  rows={3}
                  value={intake[field.key] ?? ""}
                  onChange={(event) => updateIntakeField(field.key, event.target.value)}
                  placeholder={field.placeholder}
                />
              ) : (
                <input
                  className="input"
                  value={intake[field.key] ?? ""}
                  onChange={(event) => updateIntakeField(field.key, event.target.value)}
                  placeholder={field.placeholder}
                />
              )}
            </label>
          ))}
        </div>

        <details className="builder-advanced" style={{ marginTop: "0.85rem" }}>
          <summary>Advanced: Discovery Prompting And Model Settings</summary>
          <div className="builder-advanced-grid">
            <label className="field-block">
              <span className="field-label">Input Mode</span>
              <select className="select" value={intake.input_mode} onChange={(event) => updateIntakeField("input_mode", event.target.value === "prompt" ? "prompt" : "onboarding")}>
                <option value="onboarding">onboarding</option>
                <option value="prompt">prompt</option>
              </select>
            </label>
            <label className="field-block">
              <span className="field-label">Discovery Provider</span>
              <select className="select" value={discoveryProvider} onChange={(event) => setDiscoveryProvider(event.target.value as typeof discoveryProvider)}>
                {(builderProviders?.providers ?? []).map((provider) => (
                  <option key={provider.provider_id} value={provider.provider_id}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-block">
              <span className="field-label">Discovery Model</span>
              <input className="input" value={discoveryModel} onChange={(event) => setDiscoveryModel(event.target.value)} placeholder="provider default" />
            </label>
            {intake.input_mode === "prompt" ? (
              <label className="field-block" style={{ gridColumn: "1 / -1" }}>
                <span className="field-label">Project Prompt</span>
                <textarea
                  className="input"
                  rows={5}
                  value={intake.project_prompt ?? ""}
                  onChange={(event) => updateIntakeField("project_prompt", event.target.value)}
                  placeholder="Describe the project directly when you want discovery to start from freeform context."
                />
              </label>
            ) : null}
          </div>
        </details>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <button className="btn" type="button" onClick={() => void onStartDiscovery()} disabled={demoMode || isBusy}>
            Start Discovery Session
          </button>
          <button className="btn primary" type="button" onClick={() => void onGenerateDiscovery()} disabled={demoMode || !discoverySession || isBusy}>
            Generate Questions / Synthesis
          </button>
          {workflow === "existing_project" ? (
            <button className="btn" type="button" onClick={() => void onRunProjectScan()} disabled={demoMode || isBusy || !selectedRepo.trim()}>
              Run Project Scan
            </button>
          ) : null}
        </div>

        {discoverySession ? (
          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.9rem" }}>
            <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
              <StatusChip tone="info">{`session ${discoverySession.session_id}`}</StatusChip>
              <StatusChip tone={discoverySession.status === "synthesized" ? "success" : "warning"}>{`state ${formatDiscoveryStateLabel(discoverySession)}`}</StatusChip>
              <StatusChip tone={discoverySession.approval?.approved ? "success" : "warning"}>{`approval ${discoverySession.approval?.approved ? "approved" : "pending"}`}</StatusChip>
              {workflow === "existing_project" && projectScan ? (
                <StatusChip tone={projectScan.critical_gaps.length > 0 ? "warning" : "success"}>{`critical gaps ${projectScan.critical_gaps.length}`}</StatusChip>
              ) : null}
            </div>

            {discoverySession.questions.length > 0 ? (
              <div style={{ display: "grid", gap: "0.65rem" }}>
                {discoverySession.questions.map((question) => (
                  <label key={question.question_id} className="field-block">
                    <span className="field-label">{question.prompt}</span>
                    <textarea
                      className="input"
                      rows={2}
                      value={discoveryAnswers[question.question_id] ?? ""}
                      onChange={(event) =>
                        setDiscoveryAnswers({
                          ...discoveryAnswers,
                          [question.question_id]: event.target.value,
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            ) : null}

            {discoverySession.synthesis ? (
              <div className="builder-help-panel">
                <strong style={{ display: "block" }}>Synthesis Summary</strong>
                <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                  {discoverySession.synthesis.summary}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Step 3</p>
        <h3 style={{ marginTop: "0.25rem" }}>Deploy Harness</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          Deploy stays human-triggered and explicit. This surface only makes the next guarded action obvious for the selected workflow.
        </p>

        {workflow === "new_project" ? (
          <>
            <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginTop: "0.85rem", marginBottom: "0.6rem" }}>
              <input type="checkbox" checked={generateOverwrite} onChange={(event) => setGenerateOverwrite(event.target.checked)} />
              <span>Overwrite destination if it already exists</span>
            </label>
            {generateOverwrite ? (
              <label className="field-block" style={{ marginBottom: "0.7rem" }}>
                <span className="field-label">Overwrite Confirmation</span>
                <input className="input mono" value={generateOverwriteConfirmation} onChange={(event) => setGenerateOverwriteConfirmation(event.target.value)} placeholder={expectedGenerateOverwrite} />
              </label>
            ) : null}
            <button className="btn primary" type="button" onClick={() => void onGenerateProject()} disabled={demoMode || isBusy || !discoverySession || !generateDestination.trim()}>
              Generate Project Repo
            </button>
            {latestGenerateResult ? (
              <p className="metric-sub" style={{ marginTop: "0.7rem", marginBottom: 0 }}>
                Generated {latestGenerateResult.destination_path} with {latestGenerateResult.generated_files.length} tracked scaffold paths.
              </p>
            ) : null}
          </>
        ) : null}

        {workflow === "existing_project" ? (
          <>
            {projectScan?.critical_gaps.length ? (
              <div style={{ marginTop: "0.85rem" }}>
                <p className="card-head" style={{ marginBottom: "0.45rem" }}>
                  Critical Gaps
                </p>
                <ul style={{ margin: 0, paddingLeft: "1rem" }}>
                  {projectScan.critical_gaps.map((gap) => (
                    <li key={gap}>{gap}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {projectScan?.critical_gaps.length ? (
              <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.75rem" }}>
                <label className="field-block">
                  <span className="field-label">Critical Gap Policy</span>
                  <select className="select" value={criticalGapPolicy} onChange={(event) => setCriticalGapPolicy(event.target.value as typeof criticalGapPolicy)}>
                    <option value="block_with_override">block_with_override</option>
                    <option value="warn_only">warn_only</option>
                    <option value="hard_block">hard_block</option>
                  </select>
                </label>
                <label className="field-block" style={{ gridColumn: "1 / -1" }}>
                  <span className="field-label">Override Reason</span>
                  <textarea className="input" rows={2} value={criticalGapOverrideReason} onChange={(event) => setCriticalGapOverrideReason(event.target.value)} />
                </label>
                <label className="field-block" style={{ gridColumn: "1 / -1" }}>
                  <span className="field-label">Override Confirmation</span>
                  <input className="input mono" value={criticalGapOverrideConfirmation} onChange={(event) => setCriticalGapOverrideConfirmation(event.target.value)} placeholder={expectedCriticalGapOverride} />
                </label>
              </div>
            ) : null}

            <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginTop: "0.85rem", marginBottom: "0.6rem" }}>
              <input type="checkbox" checked={sidecarOverwrite} onChange={(event) => setSidecarOverwrite(event.target.checked)} />
              <span>Overwrite existing sidecar directory</span>
            </label>
            {sidecarOverwrite ? (
              <label className="field-block" style={{ marginBottom: "0.7rem" }}>
                <span className="field-label">Overwrite Confirmation</span>
                <input className="input mono" value={sidecarOverwriteConfirmation} onChange={(event) => setSidecarOverwriteConfirmation(event.target.value)} placeholder={expectedSidecarOverwrite} />
              </label>
            ) : null}
            <button className="btn primary" type="button" onClick={() => void onDeploySidecar()} disabled={demoMode || isBusy || !discoverySession || !selectedRepo.trim()}>
              Deploy Harness Sidecar
            </button>
            <p className="metric-sub" style={{ marginTop: "0.7rem", marginBottom: 0 }}>
              Current-project mode is methodical when discovery, scan, and sidecar deploy happen in order. The loop stays unchanged; the page is just quieter about it.
            </p>
            {latestDeployResult ? (
              <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                Sidecar deployed to {latestDeployResult.sidecar_path}
              </p>
            ) : null}
          </>
        ) : null}

        {workflow === "import_existing_harness" ? (
          <>
            <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", marginTop: "0.85rem", marginBottom: "0.6rem" }}>
              <input type="checkbox" checked={importOverwrite} onChange={(event) => setImportOverwrite(event.target.checked)} />
              <span>Overwrite import destination</span>
            </label>
            {importOverwrite ? (
              <label className="field-block" style={{ marginBottom: "0.7rem" }}>
                <span className="field-label">Overwrite Confirmation</span>
                <input className="input mono" value={importOverwriteConfirmation} onChange={(event) => setImportOverwriteConfirmation(event.target.value)} placeholder={expectedImportOverwrite} />
              </label>
            ) : null}
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn" type="button" onClick={() => void onImportHarness("path")} disabled={demoMode || isBusy || !importSourcePath.trim()}>
                Import From Path
              </button>
              <button className="btn primary" type="button" onClick={() => void onImportHarness("bundle")} disabled={demoMode || isBusy || !importFile}>
                Import Bundle
              </button>
            </div>
            {latestImportResult ? (
              <p className="metric-sub" style={{ marginTop: "0.7rem", marginBottom: 0 }}>
                Imported harness to {latestImportResult.destination_path}
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Step 4</p>
        <h3 style={{ marginTop: "0.25rem" }}>Build Project Phases</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          Once the harness is in place, generate typed phase artifacts and execution prompts so follow-on work stays legible and reviewable.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
          <button className="btn primary" type="button" onClick={() => void onBuildFollowOnPhasePlan()} disabled={demoMode || isBusy || !followOnPlanReady}>
            Build Project Phases
          </button>
          {followOnPlan ? (
            <StatusChip tone="success">{`${followOnPlan.phase_plan.phases.length} phases ready`}</StatusChip>
          ) : (
            <StatusChip tone="warning">deploy and synthesis required first</StatusChip>
          )}
        </div>

        {!followOnPlanReady ? (
          <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>
            Required before phase planning: target repo, discovery synthesis, harness deploy, and for current-project flows a repo scan so the workflow stays grounded in the current codebase.
          </p>
        ) : null}

        {followOnPlan ? (
          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.9rem" }}>
            <div className="builder-help-panel">
              <strong style={{ display: "block" }}>Phase Plan Summary</strong>
              <p className="metric-sub" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                {followOnPlan.phase_plan.summary}
              </p>
            </div>
            {alignmentSummary ? (
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                <article className="builder-help-panel">
                  <strong style={{ display: "block" }}>Alignment Summary</strong>
                  <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.55rem" }}>
                    <StatusChip tone={alignmentSummary.summary.overall_status === "critical" ? "error" : alignmentSummary.summary.overall_status === "attention" ? "warning" : "success"}>
                      {`overall ${alignmentSummary.summary.overall_status}`}
                    </StatusChip>
                    <StatusChip tone="warning">{`manual ${alignmentSummary.summary.manual_required_count}`}</StatusChip>
                    <StatusChip tone="warning">{`missing ${alignmentSummary.summary.missing_count}`}</StatusChip>
                    <StatusChip tone="info">{`next ${alignmentSummary.next_recommended_phase_id}`}</StatusChip>
                  </div>
                  <p className="metric-sub" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
                    {alignmentSummary.next_recommended_action?.next_action ?? "The harness is aligned enough to continue to the next reviewed step."}
                  </p>
                </article>
                <article className="builder-help-panel">
                  <strong style={{ display: "block" }}>Source Breakdown</strong>
                  <div style={{ display: "grid", gap: "0.3rem", marginTop: "0.55rem" }}>
                    {Object.entries(alignmentSummary.source_breakdown).map(([key, value]) => (
                      <span key={key} className="metric-sub">{`${key}: ${value}`}</span>
                    ))}
                  </div>
                </article>
              </div>
            ) : null}
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              {followOnPlan.phase_plan.phases.map((phase) => (
                <article key={phase.phase_id} className="card card-pad" style={{ padding: "0.9rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", alignItems: "start" }}>
                    <div>
                      <p className="card-head" style={{ marginTop: 0 }}>
                        {phase.title}
                      </p>
                      <p className="metric-sub" style={{ marginTop: "0.3rem", marginBottom: 0 }}>
                        {phase.objective}
                      </p>
                    </div>
                    <StatusChip tone={phase.phase_id === followOnPlan.phase_plan.next_recommended_phase_id ? "success" : "info"}>{phase.phase_id}</StatusChip>
                  </div>
                  <p className="metric-sub" style={{ marginTop: "0.65rem", marginBottom: "0.35rem" }}>
                    Focus: {phase.execution_focus}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: "1rem" }}>
                    {phase.deliverables.map((deliverable) => (
                      <li key={deliverable}>{deliverable}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <p className="card-head">Step 5</p>
        <h3 style={{ marginTop: "0.25rem" }}>Run Phase Prompt</h3>
        <p className="metric-sub" style={{ marginTop: "0.35rem" }}>
          Prompt selection stays explicit. Nothing auto-runs here; pick the next prompt, then use the assistant action bar to preview, copy, or run it on purpose.
        </p>

        {followOnPlan ? (
          <>
            <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "0.85rem" }}>
              {FOLLOW_ON_PROMPT_ORDER.map((promptId) => {
                const prompt = followOnPlan.prompts.find((item) => item.prompt_id === promptId);
                if (!prompt) {
                  return null;
                }
                const selected = selectedFollowOnPromptId === prompt.prompt_id;
                return (
                  <button
                    key={prompt.prompt_id}
                    type="button"
                    className="btn"
                    onClick={() => setSelectedFollowOnPromptId(prompt.prompt_id)}
                    disabled={demoMode}
                    style={{
                      textAlign: "left",
                      borderColor: selected ? "var(--cyan)" : undefined,
                    }}
                  >
                    <strong>{prompt.title}</strong>
                    <span style={{ display: "block", marginTop: "0.35rem", fontSize: "0.82rem", opacity: 0.82 }}>{prompt.summary}</span>
                  </button>
                );
              })}
            </div>

            {selectedFollowOnPrompt ? (
              <label className="field-block" style={{ marginTop: "0.9rem" }}>
                <span className="field-label">Selected Prompt</span>
                <textarea className="input mono" rows={12} value={selectedFollowOnPrompt.prompt} readOnly />
              </label>
            ) : null}
          </>
        ) : (
          <p className="metric-sub" style={{ marginTop: "0.85rem", marginBottom: 0 }}>
            Build the phase plan first to load Bootstrap Hydration, Build Project Phases, Implement Phase 1, and Run All Phases prompts.
          </p>
        )}
      </section>

      <AssistantActionBar
        assistant={settings.preferredAssistant}
        sourceMode="builder"
        prompt={assistantPrompt}
        artifactLinks={artifactLinks}
        disabled={demoMode || !assistantPrompt.trim()}
        busy={assistantBusy}
        statusText={assistantStatus}
        assistantRuntime={assistantRuntime}
        executionHostSummary={executionHostSummary}
        browserAccessSummary={browserAccessSummary}
        onPreviewPrompt={() => void onPreviewPrompt()}
        onRunAssistant={onRunAssistant}
      />

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <details className="builder-advanced">
          <summary>Explainability: Flow Map And Payload Fill</summary>
          <div style={{ display: "grid", gap: "0.9rem", marginTop: "0.9rem" }}>
            <HarnessFlowVisualizer workflow={workflow} subtitle="The deploy loop stays visible here when you want to inspect how discovery, payload fill, and guarded deploy actions connect." />
            <TemplateFillTree
              generatedFiles={activeGeneratedFiles}
              title="Payload Fill Tree"
              description="The seed tree stays available for reference, but it no longer competes with the main staged route."
            />
          </div>
        </details>
      </section>

      <section className="card card-pad" style={{ gridColumn: "span 12" }}>
        <details className="builder-advanced">
          <summary>Advanced: Repo Utilities And Remote Checks</summary>
          <div style={{ display: "grid", gap: "0.9rem", marginTop: "0.9rem" }}>
            <div style={{ display: "grid", gap: "0.65rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              <label className="field-block">
                <span className="field-label">Repo Name</span>
                <input className="input" value={newRepoName} onChange={(event) => setNewRepoName(event.target.value)} />
              </label>
              <label style={{ display: "flex", gap: "0.55rem", alignItems: "center", alignSelf: "end" }}>
                <input type="checkbox" checked={repoOverwrite} onChange={(event) => setRepoOverwrite(event.target.checked)} />
                <span>Overwrite Repo</span>
              </label>
              {repoOverwrite ? (
                <label className="field-block">
                  <span className="field-label">Overwrite Confirmation</span>
                  <input className="input mono" value={repoOverwriteConfirmation} onChange={(event) => setRepoOverwriteConfirmation(event.target.value)} placeholder={expectedCreateOverwrite} />
                </label>
              ) : null}
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button className="btn" type="button" onClick={() => void onCreateRepo()} disabled={demoMode || isBusy || !newRepoName.trim()}>
                Create Repo
              </button>
              <button className="btn" type="button" onClick={() => void onCheckCompleteness()} disabled={demoMode || isBusy || !selectedRepo.trim()}>
                Check Missing Rules
              </button>
              {workflow === "existing_project" && targetMode === "remote_ssh" ? (
                <>
                  <button className="btn" type="button" onClick={() => void onTestRemote("pwd")} disabled={demoMode || !selectedProfile}>
                    Test Connection
                  </button>
                  <button className="btn" type="button" onClick={() => void onTestRemote(buildRemoteListCommand(selectedRepo))} disabled={demoMode || !selectedProfile || !selectedRepo.trim()}>
                    List Target Root
                  </button>
                  <button
                    className="btn"
                    type="button"
                    onClick={() => void onTestRemote(buildRemoteSidecarCheckCommand(selectedRepo, sidecarDir))}
                    disabled={demoMode || !selectedProfile || !selectedRepo.trim()}
                  >
                    Check Sidecar
                  </button>
                </>
              ) : null}
            </div>

            {sshResult ? (
              <p className="metric-sub mono" style={{ margin: 0 }}>
                {sshResult}
              </p>
            ) : null}

            {repoCompleteness ? (
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                {repoCompleteness.groups.map((group) => (
                  <article key={group.group_id} className="card card-pad" style={{ padding: "0.8rem" }}>
                    <p className="card-head" style={{ marginTop: 0 }}>
                      {group.label}
                    </p>
                    <ul style={{ margin: "0.55rem 0 0", paddingLeft: "1rem" }}>
                      {group.checks.map((check) => (
                        <li key={check.check_id}>
                          {check.label}: {check.status}
                        </li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
        </details>
      </section>

      {message ? <section className="card card-pad" style={{ gridColumn: "span 12", color: "var(--success)" }}>{message}</section> : null}
      {error ? <section className="card card-pad" style={{ gridColumn: "span 12", color: "var(--error)" }}>{error}</section> : null}
    </div>
  );
}
