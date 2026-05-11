export interface HeadingRecordV1 {
  level: number;
  text: string;
  line: number;
}

export interface DocRecordV1 {
  version: "DocRecordV1";
  id: string;
  relative_path: string;
  section: string;
  title: string;
  status: string;
  owner: string;
  last_reviewed: string;
  related_docs: string[];
  source_refs: string[];
  heading_count: number;
  headings: HeadingRecordV1[];
  checklist_total: number;
  checklist_done: number;
  word_count: number;
  has_frontmatter: boolean;
  classification?: DocClassificationV1;
  content: string;
}

export type DocClassificationV1 = "human_owned_context" | "system_managed" | "generated";

export interface StageChecklistItemV1 {
  text: string;
  done: boolean;
}

export interface StageRecordV1 {
  stage_id: string;
  title: string;
  checklist: StageChecklistItemV1[];
  checklist_total: number;
  checklist_done: number;
  completion: number;
  is_complete: boolean;
}

export interface PhaseRecordV1 {
  phase_number: number;
  title: string;
  phase_status: string;
  stages: StageRecordV1[];
  done_when: string[];
  checklist_total: number;
  checklist_done: number;
  completion: number;
}

export interface PhaseBoardV1 {
  version: "PhaseBoardV1";
  phase_count: number;
  stage_count: number;
  stage_done_count: number;
  phases: PhaseRecordV1[];
}

export interface LoopHistoryRecordV1 {
  run_id: string;
  date: string;
  result: string;
  human_decision: string;
  notes: string;
}

export interface LoopStateV1 {
  version: "LoopStateV1";
  run_count: number;
  last_run_id: string;
  last_plan_file: string;
  last_result: string;
  halt_reason: string;
  next_action: string;
  history: LoopHistoryRecordV1[];
}

export interface CapabilityGapRecordV1 {
  gap_id: string;
  opened_on: string;
  status: string;
  class: string;
  owner: string;
  enforcement_target: string;
  evidence_link: string;
}

export interface CapabilityGapV1 {
  version: "CapabilityGapV1";
  open_count: number;
  in_progress_count: number;
  blocked_count: number;
  rows: CapabilityGapRecordV1[];
}

export interface ChangelogEntryV1 {
  entry_id: string;
  date: string;
  cycle_id: string;
  phase_stage: string;
  change_type: string;
  summary: string;
  docs_updated: string;
  human_gate_decision: string;
  approval_ref: string;
  approval_status: string;
}

export interface ChangelogV1 {
  version: "ChangelogV1";
  entry_count: number;
  awaiting_human_review_count: number;
  approved_count: number;
  rows: ChangelogEntryV1[];
}

export interface FeatureRecordV1 {
  feature_id: string;
  capability: string;
  status: string;
  source_phase_stage: string;
  owner: string;
  evidence_link: string;
  last_updated: string;
}

export interface CurrentFeaturesV1 {
  version: "CurrentFeaturesV1";
  implemented_count: number;
  pending_count: number;
  rows: FeatureRecordV1[];
}

export interface GuidanceRecordV1 {
  guidance_id: string;
  rule: string;
  enforcement_anchor: string;
  operator_action: string;
  status: string;
}

export interface CurrentGuidanceV1 {
  version: "CurrentGuidanceV1";
  active_count: number;
  rows: GuidanceRecordV1[];
}

export interface LoopProcessRecordV1 {
  process_id: string;
  process_type: string;
  trigger: string;
  steps_summary: string;
  required_artifacts: string;
  human_gate: string;
  next_cycle_rule: string;
}

export interface LoopProcessesV1 {
  version: "LoopProcessesV1";
  row_count: number;
  rows: LoopProcessRecordV1[];
}

export interface HumanGateStatsRowV1 {
  gate_id: string;
  date: string;
  cycle_id: string;
  loop_id: string;
  cycles_completed: number;
  estimated_cycles_remaining: number;
  estimated_loops_remaining: number;
  stages_remaining: number;
  pending_approvals: number;
  pending_features: number;
  open_capability_gaps: number;
  open_harness_upgrades: number;
  completion_percent: number;
  next_cycle_type: string;
  reviewer_action_required: string;
  notes: string;
}

export interface HumanGateStatsV1 {
  version: "HumanGateStatsV1";
  row_count: number;
  latest_estimated_cycles_remaining: number;
  latest_estimated_loops_remaining: number;
  latest: HumanGateStatsRowV1;
  rows: HumanGateStatsRowV1[];
}

export interface ArchiveRegisterRowV1 {
  archive_id: string;
  archived_on: string;
  record_type: string;
  source_cycle: string;
  title: string;
  status: string;
  archive_path: string;
  upgrade_review: string;
  notes: string;
}

export interface ArchiveRegisterV1 {
  version: "ArchiveRegisterV1";
  row_count: number;
  update_count: number;
  upgrade_review_count: number;
  suggestion_count: number;
  rows: ArchiveRegisterRowV1[];
}

export interface PolicyDomainEntryV1 {
  domain: string;
  doc_count: number;
  missing_owner_count: number;
  missing_status_count: number;
  stale_review_count: number;
  doc_ids: string[];
}

export interface PolicyDomainSummaryV1 {
  version: "PolicyDomainSummaryV1";
  domains: PolicyDomainEntryV1[];
}

export interface NamespaceRecordV1 {
  namespace: string;
  containers_services: string;
  intent: string;
}

export interface ServiceBoundaryRecordV1 {
  service: string;
  primary_role: string;
  owns: string;
  does_not_own: string;
  key_contracts: string;
}

export interface TopologySnapshotV1 {
  version: "TopologySnapshotV1";
  namespaces: NamespaceRecordV1[];
  boundaries: ServiceBoundaryRecordV1[];
}

export interface ProjectObjectiveRecordV1 {
  objective_id: string;
  goal: string;
  in_scope: string;
  out_of_scope: string;
  stop_conditions: string;
}

export interface ProjectOverviewV1 {
  version: "ProjectOverviewV1";
  mission: string;
  architecture_goals: string[];
  active_objective_count: number;
  active_objectives: ProjectObjectiveRecordV1[];
  phase_status_summary: {
    completed: number;
    pending: number;
    other: number;
  };
}

export interface ServiceInventoryRowV1 {
  service: string;
  domain: string;
  phase_target: string;
  implementation_surface: string;
  status: "implemented" | "planned_only" | "unmapped_implementation";
}

export interface ServiceInventoryV1 {
  version: "ServiceInventoryV1";
  planned_count: number;
  implemented_count: number;
  planned_only_count: number;
  unmapped_implementation_count: number;
  rows: ServiceInventoryRowV1[];
}

export interface HarnessFlowV1 {
  flow_id: string;
  title: string;
  trigger: string;
  steps: string[];
  required_artifacts: string[];
  human_gates: string[];
  source_docs: string[];
}

export interface HarnessSkillItemV1 {
  label: string;
  path: string;
}

export interface HarnessSkillV1 {
  skill_id: string;
  title: string;
  purpose: string;
  source_doc: string;
  current_items: HarnessSkillItemV1[];
}

export interface HarnessConventionV1 {
  convention_id: string;
  category: string;
  rule: string;
  enforcement_command: string;
  source_doc: string;
}

export interface HarnessGuidelineLinkV1 {
  label: string;
  path: string;
  description: string;
}

export interface HarnessProposalV1 {
  title: string;
  path: string;
  guard_text: string;
}

export interface HarnessRepoSkillV1 {
  skill_id: string;
  title: string;
  path: string;
  mode: string;
  owner: string;
  status: string;
}

export interface HarnessCompatibilityWindowV1 {
  window_start_date: string;
  required_approved_cycles: number;
  approved_cycles_completed: number;
  current_slot: string;
  legacy_pointers_enabled: boolean;
  legacy_fallbacks_enabled: boolean;
  cycle_028_ready: boolean;
  blocking_issues: string[];
}

export interface HarnessHelpV1 {
  version: "HarnessHelpV1";
  flows: HarnessFlowV1[];
  skills: HarnessSkillV1[];
  conventions: HarnessConventionV1[];
  guidelines: HarnessGuidelineLinkV1[];
  proposal: HarnessProposalV1;
  repo_skills?: HarnessRepoSkillV1[];
  compatibility_window?: HarnessCompatibilityWindowV1 | null;
}

export interface GitStateV1 {
  version: "GitStateV1";
  branch: string;
  short_sha: string;
  last_commit: string;
  dirty: boolean;
  markdown_changed_count: number;
  markdown_changed_files: string[];
  grouped_by_section: Record<string, string[]>;
}

export interface TrackerSummaryV1 {
  docs_total: number;
  docs_non_generated: number;
  docs_generated: number;
  phase_count: number;
  stage_count: number;
  stage_done_count: number;
  loop_run_count: number;
  open_gap_count: number;
  changelog_entry_count: number;
  awaiting_human_review_count: number;
  implemented_feature_count: number;
  active_guidance_count: number;
  estimated_cycles_remaining: number;
  estimated_loops_remaining: number;
  archive_entry_count: number;
  markdown_changed_count: number;
  compatibility_mode?: string;
}

export interface TrackerSummaryV2 {
  docs_total: number;
  docs_human_owned_context: number;
  docs_system_managed: number;
  docs_generated: number;
  phase_count: number;
  stage_count: number;
  stage_done_count: number;
  loop_run_count: number;
  open_gap_count: number;
  changelog_entry_count: number;
  awaiting_human_review_count: number;
  implemented_feature_count: number;
  active_guidance_count: number;
  estimated_cycles_remaining: number;
  estimated_loops_remaining: number;
  archive_entry_count: number;
  markdown_changed_count: number;
  compatibility_mode?: string;
}

export interface QaSignalsV1 {
  version: "QaSignalsV1";
  generated_at: string;
  engineer_entry_guard: {
    status: "pass" | "fail";
    detail: unknown;
  };
  branch_hygiene: {
    status: "pass" | "fail";
    detail: unknown;
  };
  documentation_review?: {
    status: "pass" | "warn" | "fail";
    detail: unknown;
  };
}

export interface ReviewQueueItemV1 {
  doc_id: string;
  relative_path: string;
  title: string;
  status: string;
  owner: string;
  actionable: boolean;
}

export interface ReviewQueueBucketV1 {
  queue_id: "updates" | "upgrades" | "tooling" | "suggestions" | "governance";
  label: string;
  active_docs: number;
  actionable_docs: number;
  implemented_docs: number;
  rows: ReviewQueueItemV1[];
}

export interface ReviewQueueV1 {
  version: "ReviewQueueV1";
  generated_at: string;
  pending_approvals: number;
  pending_total: number;
  queues: ReviewQueueBucketV1[];
  zero_state: {
    updates: boolean;
    upgrades: boolean;
    tooling: boolean;
    suggestions: boolean;
  };
  reconciliation: {
    status: "pass" | "warn";
    issues: string[];
  };
}

export interface RouteContextCoverageRowV1 {
  route: string;
  router_present: boolean;
  context_present: boolean;
  status: "covered" | "missing_context" | "orphan_context";
}

export interface RouteContextCoverageV1 {
  version: "RouteContextCoverageV1";
  router_route_count: number;
  context_route_count: number;
  coverage_percent: number;
  missing_in_context: string[];
  extra_in_context: string[];
  rows: RouteContextCoverageRowV1[];
}

export interface HumanReviewRowV1 {
  review_id: string;
  label: string;
  pending_count: number;
  severity: "none" | "low" | "medium" | "high";
  route: string;
  source: string;
}

export interface HumanReviewSummaryV1 {
  version: "HumanReviewSummaryV1";
  generated_at: string;
  next_action: "continue" | "pause" | "stop";
  pending_total: number;
  project_review: HumanReviewRowV1[];
  harness_review: HumanReviewRowV1[];
  notes: string[];
}

export interface BuilderRepoRecordV1 {
  name: string;
  path: string;
  git_initialized: boolean;
}

export interface BuilderOperationRecordV1 {
  timestamp: string;
  action: string;
  status: string;
  target_repo?: string;
  destination_path: string;
  sidecar_path?: string;
  detail: string;
}

export interface BuilderStatusV1 {
  version: "BuilderStatusV1";
  existing_project_mode_enabled?: boolean;
  allowlisted_root: string;
  path_disclosure_mode?: "masked" | "full";
  scan_limits_defaults?: {
    max_depth: number;
    max_files: number;
  };
  project_status_history_retention?: number;
  known_repos: BuilderRepoRecordV1[];
  recent_operations: BuilderOperationRecordV1[];
}

export type MoradinReadinessStatusV1 = "present" | "missing" | "manual";

export interface MoradinReadinessCheckV1 {
  tool_id: string;
  label: string;
  required: boolean;
  status: MoradinReadinessStatusV1;
  command: string;
  detected_path: string;
  version: string;
  detail: string;
  install_commands: string[];
  verify_command: string;
  runbook_refs: string[];
}

export interface MoradinReadinessGroupV1 {
  group_id: string;
  label: string;
  required: boolean;
  summary: {
    total: number;
    present_count: number;
    missing_count: number;
    manual_count: number;
  };
  checks: MoradinReadinessCheckV1[];
}

export interface MoradinToolingReadinessV1 {
  version: "MoradinToolingReadinessV1";
  generated_at: string;
  request_only: boolean;
  payload_manifest: {
    manifest_path: string;
    payload_id: string;
    payload_version: string;
    include_count: number;
    exclude_count: number;
    sidecar_default_dir: string;
  };
  summary: {
    total: number;
    present_count: number;
    missing_count: number;
    manual_count: number;
    required_missing_count: number;
    optional_missing_count: number;
    overall_status: "ready" | "optional_attention" | "action_required";
  };
  groups: MoradinReadinessGroupV1[];
  install_guidance: Array<{
    tool_id: string;
    label: string;
    required: boolean;
    install_commands: string[];
    verify_command: string;
    runbook_refs: string[];
    note: string;
  }>;
  artifact_roots: {
    install_requests: string;
    repo_registry: string;
  };
}

export interface MoradinInstallRequestV1 {
  version: "MoradinInstallRequestV1";
  request_id: string;
  created_at: string;
  request_only: boolean;
  assistant_mode: "codex_cli" | "codex_app_manual_handoff" | "claude_code" | "manual_handoff";
  operator_note: string;
  status: "requested" | "no_missing_tools";
  selected_tools: Array<{
    tool_id: string;
    label: string;
    status: MoradinReadinessStatusV1;
    required: boolean;
    install_commands: string[];
    verify_command: string;
    runbook_refs: string[];
  }>;
  commands: Array<{
    tool_id: string;
    label: string;
    command: string;
    verify_command: string;
    required: boolean;
  }>;
  safety: string;
  artifact_paths: {
    json: string;
    markdown: string;
  };
}

export interface MoradinRepoRegistryRecordV1 {
  repo_id: string;
  name: string;
  scope: "manager" | "tracked";
  path: string;
  git_initialized: boolean;
  agents_present: boolean;
  moradin_sidecar_present: boolean;
  moradin_sidecar_path: string;
  package_managers: string[];
  make_targets: string[];
  adapter_surfaces: {
    makefile_present: boolean;
    generated_tooling_present: boolean;
    repo_brief_target: boolean;
    verify_fast_target: boolean;
    review_ready_target: boolean;
  };
  artifact_reuse: {
    latest_status_report: string;
    latest_status_generated_at: string;
    project_status_slug: string;
  };
  brief: string;
  rerun_advice: string;
}

export interface MoradinRepoRegistryV1 {
  version: "MoradinRepoRegistryV1";
  generated_at: string;
  allowlisted_root: string;
  path_disclosure_mode: "masked" | "full";
  summary: {
    total_repos: number;
    tracked_repos: number;
    git_initialized_count: number;
    moradin_sidecar_count: number;
    reusable_artifact_count: number;
  };
  repositories: MoradinRepoRegistryRecordV1[];
  adapter_contract: {
    source_pattern: string;
    preferred_commands: string[];
    artifact_root: string;
  };
}

export interface TemplateManifestSummaryV1 {
  name: string;
  kind: string;
  project_type: string;
  docs_truth_root: string;
  control_plane_root: string;
  entrypoint: string;
  template_id: string;
  template_version: string;
  path_convention: string;
  release_stage: string;
  compatibility_mode: string;
}

export interface TemplateSectionRecordV1 {
  section: string;
  relative_path: string;
  title: string;
  status: string;
  owner: string;
  placeholder: boolean;
  question_count: number;
}

export interface TemplateValidationSummaryV1 {
  available: boolean;
  overall_ok: boolean;
  manager_ok: boolean;
  template_ok: boolean;
  messages: string[];
}

export interface TemplateDryRunSummaryV1 {
  available: boolean;
  blank_ok: boolean;
  existing_ok: boolean;
  blank_target: string;
  existing_target: string;
  messages: string[];
}

export interface TemplateStudioV1 {
  version: "TemplateStudioV1";
  generated_at: string;
  manager_manifest: TemplateManifestSummaryV1;
  template_manifest: TemplateManifestSummaryV1;
  required_sections: string[];
  sections: TemplateSectionRecordV1[];
  inventory: {
    total_files: number;
    docs_markdown_count: number;
    harness_markdown_count: number;
    placeholder_count: number;
  };
  validation: TemplateValidationSummaryV1;
  dry_run: TemplateDryRunSummaryV1;
}

export interface BuilderProviderV1 {
  provider_id: "none" | "openai" | "codex_cli" | "claude_code";
  label: string;
  capabilities: string[];
  availability_status: "available" | "unavailable";
  detail: string;
  default_model: string;
}

export interface BuilderProviderListV1 {
  version: "BuilderProviderListV1";
  providers: BuilderProviderV1[];
}

export interface BuilderRepoCompletenessCheckV1 {
  check_id: string;
  label: string;
  status: "pass" | "missing";
  detail: string;
  path?: string;
}

export interface BuilderRepoCompletenessGroupV1 {
  group_id: string;
  label: string;
  checks: BuilderRepoCompletenessCheckV1[];
}

export interface BuilderRepoCompletenessRequestV1 {
  target_repo: string;
  profile: "harness_core" | "minimal";
}

export interface BuilderRepoCompletenessResponseV1 {
  version: "BuilderRepoCompletenessResponseV1";
  target_repo: string;
  profile: "harness_core" | "minimal";
  checked_at: string;
  summary: {
    total: number;
    pass_count: number;
    missing_count: number;
  };
  groups: BuilderRepoCompletenessGroupV1[];
}

export interface CreateLocalRepoRequestV1 {
  repo_name: string;
  overwrite?: boolean;
  overwrite_confirmation?: string;
  initialize_git?: boolean;
}

export interface CreateLocalRepoResponseV1 {
  version: "CreateLocalRepoResponseV1";
  status: "created" | "overwritten";
  repo_path: string;
  message: string;
}

export interface ImportHarnessRequestV1 {
  destination_repo: string;
  source_path?: string;
  bundle_path?: string;
  bundle_base64?: string;
  filename?: string;
  overwrite?: boolean;
  overwrite_confirmation?: string;
}

export interface ImportHarnessResponseV1 {
  version: "ImportHarnessResponseV1";
  status: "imported" | "overwritten";
  destination_path: string;
  source: string;
  mode: "path" | "bundle";
}

export interface GenerateProjectRepoRequestV1 {
  session_id: string;
  profile: "web_app" | "data_pipeline" | "agent_platform" | "internal_tooling";
  destination_repo: string;
  overwrite?: boolean;
  overwrite_confirmation?: string;
}

export interface GenerateProjectRepoResponseV1 {
  version: "GenerateProjectRepoResponseV1";
  status: "created" | "overwritten";
  destination_path: string;
  profile: string;
  session_id: string;
  harness_seed_version: string;
  generated_files: string[];
  template_fill_map_artifact_paths?: {
    json: string;
    markdown: string;
  };
  validation: {
    status: "pass" | "fail";
    checks: Array<{
      name: string;
      status: "pass" | "fail";
      detail: string;
    }>;
  };
}

export interface ProjectBaselineScanV1 {
  version: "ProjectBaselineScanV1";
  scanned_at: string;
  target_repo: string;
  target_path: string;
  file_count: number;
  scan_limits_effective?: {
    max_depth: number;
    max_files: number;
  };
  scan_truncated?: boolean;
  scan_truncation_reason?: string;
  detected: {
    languages: string[];
    package_managers: string[];
    lockfiles: string[];
    ci_surfaces: string[];
    test_surfaces: string[];
    deployment_surfaces: string[];
    infra_surfaces: string[];
    governance_surfaces: string[];
  };
  critical_gaps: string[];
  summary: {
    language_count: number;
    package_manager_count: number;
    ci_surface_count: number;
    test_surface_count: number;
    critical_gap_count: number;
  };
}

export interface ProjectScanResponseV1 extends ProjectBaselineScanV1 {
  session_id: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetV1 | null;
  artifact_paths: {
    json: string;
    markdown: string;
  } | null;
}

export interface ProjectScanRequestV1 {
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetConfigV1;
  session_id?: string;
  scan_limits?: {
    max_depth?: number;
    max_files?: number;
  };
}

export interface DeployExistingProjectRequestV1 {
  session_id: string;
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetConfigV1;
  mode: "sidecar";
  sidecar_dir?: string;
  overwrite_sidecar?: boolean;
  overwrite_confirmation?: string;
  critical_gap_policy?: "block_with_override" | "warn_only" | "hard_block";
  critical_gap_override_reason?: string;
  critical_gap_override_confirmation?: string;
}

export interface DeployExistingProjectResponseV1 {
  version: "DeployExistingProjectResponseV1";
  status: "created" | "overwritten";
  mode: "sidecar";
  session_id: string;
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetV1 | null;
  destination_path: string;
  sidecar_path: string;
  profile: string;
  harness_seed_version: string;
  generated_files: string[];
  template_fill_map_artifact_paths?: {
    json: string;
    markdown: string;
  };
  validation: {
    status: "pass" | "fail";
    checks: Array<{
      name: string;
      status: "pass" | "fail";
      detail: string;
    }>;
  };
  critical_gap_policy?: "block_with_override" | "warn_only" | "hard_block";
  critical_gap_count?: number;
  critical_gap_override_applied?: boolean;
  status_route: string;
}

export interface ProjectStatusActionV1 {
  action_id: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  description: string;
  route: string;
  depends_on: string[];
  source: string;
}

export interface ProjectStatusDomainV1 {
  domain_id: string;
  label: string;
  status: "healthy" | "attention" | "risk";
  summary: string;
}

export type AlignmentItemStatusV1 =
  | "satisfied"
  | "manual_required"
  | "missing"
  | "deferred";

export type AlignmentSeverityV1 = "critical" | "high" | "medium" | "low";

export type AlignmentSourceTypeV1 =
  | "seed_template"
  | "profile_overlay"
  | "user_filled"
  | "scan_derived"
  | "manual_required";

export interface AlignmentStateItemV1 {
  item_id: string;
  label: string;
  status: AlignmentItemStatusV1;
  severity: AlignmentSeverityV1;
  source_type: AlignmentSourceTypeV1;
  owner: "harness" | "operator" | "assistant";
  recommended_route: string;
  evidence_paths: string[];
  next_action: string;
}

export interface AlignmentStateV1 {
  version: "AlignmentStateV1";
  generated_at: string;
  session_id: string;
  target_repo: string;
  workflow_type: "new_project" | "existing_project";
  selected_profile: string;
  target_mode?: "local" | "remote_ssh";
  target_path?: string;
  locked_project_goal: string;
  approval_state: "approved" | "pending";
  next_recommended_phase_id: string;
  source_breakdown: Record<AlignmentSourceTypeV1, number>;
  summary: {
    satisfied_count: number;
    manual_required_count: number;
    missing_count: number;
    deferred_count: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
    overall_status: "critical" | "attention" | "ready";
  };
  next_recommended_action: {
    item_id: string;
    label: string;
    route: string;
    next_action: string;
  } | null;
  items: AlignmentStateItemV1[];
}

export interface ProjectStatusReportV1 {
  version: "ProjectStatusReportV1";
  generated_at: string;
  target_repo: string;
  session_id: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetV1 | null;
  target_path?: string;
  summary: {
    overall_status: "critical" | "attention" | "ready";
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
    action_total: number;
  };
  critical_focus: string[];
  domain_health: ProjectStatusDomainV1[];
  actions: ProjectStatusActionV1[];
  project_scan: ProjectBaselineScanV1;
  alignment_state?: AlignmentStateV1 | null;
  status_history?: {
    target_slug: string;
    entry_path: string;
    latest_path: string;
    retained_entries: number;
    retention_max_entries: number;
    target_repo: string;
  };
}

export interface ProjectStatusHistoryEntryV1 {
  history_id: string;
  generated_at: string;
  overall_status: "critical" | "attention" | "ready";
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  action_total: number;
  storage_path: string;
  trend: {
    critical_delta: number;
    high_delta: number;
  };
}

export interface ProjectStatusHistoryResponseV1 {
  version: "ProjectStatusHistoryResponseV1";
  generated_at: string;
  target_repo: string;
  target_mode?: "local" | "remote_ssh";
  remote_target?: RemoteTargetV1 | null;
  target_slug: string;
  retention_max_entries: number;
  total_entries: number;
  entries: ProjectStatusHistoryEntryV1[];
}

export interface RemoteTargetConfigV1 {
  target_id?: string;
  connection_mode?: "ssh";
  host: string;
  user: string;
  port?: number;
  allowlisted_root: string;
  profile_label?: string;
  auth_method?: "ssh_agent" | "pem_path";
  pem_path?: string;
  known_hosts_mode?: "strict" | "accept_new";
}

export interface RemoteTargetV1 extends RemoteTargetConfigV1 {
  target_id: string;
  connection_mode: "ssh";
  port: number;
  profile_label: string;
  auth_method: "ssh_agent" | "pem_path";
  pem_path: string;
  known_hosts_mode: "strict" | "accept_new";
  status: "configured" | "unconfigured" | "disabled";
}

export interface RemoteSshTestResponseV1 {
  version: "RemoteSshTestResponseV1";
  target: RemoteTargetV1;
  status: "pass" | "fail";
  detail: string;
}

export interface RemoteSshExecuteResponseV1 {
  version: "RemoteSshExecuteResponseV1";
  target: RemoteTargetV1;
  status: "pass" | "fail";
  command: string;
  stdout: string;
  stderr: string;
  exit_code: number;
}

export interface DiscoveryIntakeV1 {
  input_mode: "prompt" | "onboarding";
  project_prompt?: string;
  project_goal: string;
  users: string;
  constraints: string;
  timeline: string;
  integrations: string;
  compliance: string;
  deployment_target: string;
  other_context: string;
}

export interface DiscoveryQuestionV1 {
  question_id: string;
  prompt: string;
  rationale: string;
  required: boolean;
}

export interface DiscoverySynthesisV1 {
  summary: string;
  recommended_profile: string;
  must_haves: string[];
  open_questions: string[];
  product_spec: {
    intent: string;
    target_users: string[];
    constraints: string[];
    milestones: string[];
  };
  design: {
    components: string[];
    data_flows: string[];
    risks: string[];
  };
  plan: {
    workstreams: string[];
    initial_backlog: string[];
  };
}

export interface DiscoverySessionV1 {
  version: "DiscoverySessionV1";
  session_id: string;
  status: "intake" | "questions_generated" | "answering" | "synthesized";
  provider?: "none" | "openai" | "codex_cli" | "claude_code";
  model?: string;
  created_at: string;
  updated_at: string;
  intake: DiscoveryIntakeV1;
  questions: DiscoveryQuestionV1[];
  answers: Record<string, string>;
  question_round?: number;
  project_scan_summary?: {
    target_repo?: string;
    scanned_at?: string;
    languages: string[];
    package_managers: string[];
    ci_surfaces: string[];
    deployment_surfaces: string[];
    critical_gaps: string[];
    target_mode?: "local" | "remote_ssh";
    remote_target?: RemoteTargetV1 | null;
    scan_limits_effective?: {
      max_depth: number;
      max_files: number;
    } | null;
    scan_truncated?: boolean;
    scan_truncation_reason?: string;
  } | null;
  project_scan_artifact_paths?: {
    json: string;
    markdown: string;
  } | null;
  synthesis: DiscoverySynthesisV1 | null;
  approval: {
    required: boolean;
    approved: boolean;
    approval_artifact_path: string;
  };
  artifacts: Record<string, string>;
}

export interface DiscoveryPromptBundleV1 {
  version: "DiscoveryPromptBundleV1";
  session_id: string;
  provider: "none" | "openai" | "codex_cli" | "claude_code";
  model: string;
  stage: "questions" | "synthesis";
  selected_profile: string;
  workflow_type?: "new_project" | "existing_project";
  prompt_template_id?: string;
  prompt_inputs: Record<string, unknown>;
  included_context_sections?: string[];
  artifact_references?: string[];
  source_citations?: string[];
  prompt_context_artifact_path?: string;
  context_pack_artifact_path?: string;
  deterministic_system_instructions: string;
  assembled_prompt: string;
  generated_at: string;
  hash: string;
}

export type DiscoveryFollowOnPromptIdV1 =
  | "bootstrap_hydration"
  | "phase_planning"
  | "phase_1_execution"
  | "run_all_phases";

export interface DiscoveryPhasePlanPhaseV1 {
  phase_id: string;
  title: string;
  objective: string;
  deliverables: string[];
  execution_focus: string;
}

export interface DiscoveryFollowOnPromptV1 {
  prompt_id: DiscoveryFollowOnPromptIdV1;
  title: string;
  summary: string;
  prompt: string;
}

export interface DiscoveryFollowOnPlanResponseV1 {
  version: "DiscoveryFollowOnPlanResponseV1";
  session_id: string;
  target_repo: string;
  workflow_type: "new_project" | "existing_project";
  selected_profile: string;
  generated_at: string;
  phase_plan: {
    summary: string;
    phases: DiscoveryPhasePlanPhaseV1[];
    next_recommended_phase_id: string;
  };
  alignment_state: AlignmentStateV1;
  prompts: DiscoveryFollowOnPromptV1[];
  artifact_paths: {
    bootstrap_prompt_markdown: string;
    phase_plan_json: string;
    phase_plan_markdown: string;
    execution_prompts_json: string;
    execution_prompts_markdown: string;
    alignment_state_json: string;
    alignment_state_markdown: string;
  };
}

export interface AssistantRunRequestV1 {
  assistant: "codex_cli" | "claude_code";
  source_mode: "builder" | "review" | "project_status" | "docs";
  prompt: string;
  session_id?: string;
  target_repo?: string;
  execution_scope?: "manager_repo" | "local_repo";
}

export type AssistantRunStatusV1 = "queued" | "running" | "pass" | "fail";

export type AssistantRunStageV1 =
  | "queued"
  | "launching_cli"
  | "running_cli"
  | "writing_artifacts"
  | "completed"
  | "failed";

export interface AssistantRunResponseV1 {
  version: "AssistantRunResponseV1";
  run_id: string;
  assistant: "codex_cli" | "claude_code";
  source_mode: "builder" | "review" | "project_status" | "docs";
  session_id?: string;
  target_repo?: string;
  execution_scope?: "manager_repo" | "local_repo";
  execution_context?: {
    scope: "manager_repo" | "local_repo";
    target_label: string;
    working_directory: string;
  };
  status: AssistantRunStatusV1;
  stage: AssistantRunStageV1;
  prompt: string;
  prompt_preview?: string;
  stdout: string;
  stderr: string;
  stdout_tail?: string;
  stderr_tail?: string;
  started_at: string;
  updated_at: string;
  finished_at?: string;
  detail?: string;
  duration_ms?: number;
  exit_code: number | null;
  terminal_command?: string;
  needs_operator_input?: boolean;
  artifact_paths: {
    json: string;
    markdown: string;
  };
}

export interface AssistantRunSummaryV1 {
  version: "AssistantRunSummaryV1";
  run_id: string;
  assistant: "codex_cli" | "claude_code";
  source_mode: "builder" | "review" | "project_status" | "docs";
  target_repo?: string;
  execution_scope?: "manager_repo" | "local_repo";
  execution_context?: {
    scope: "manager_repo" | "local_repo";
    target_label: string;
    working_directory: string;
  };
  status: AssistantRunStatusV1;
  stage: AssistantRunStageV1;
  started_at: string;
  updated_at: string;
  finished_at?: string;
  detail?: string;
  duration_ms?: number;
  exit_code: number | null;
  needs_operator_input?: boolean;
  artifact_paths: {
    json: string;
    markdown: string;
  };
}

export interface AssistantRunListResponseV1 {
  version: "AssistantRunListResponseV1";
  generated_at: string;
  active_run_id: string;
  runs: AssistantRunSummaryV1[];
}

export interface TrackerSnapshotV4 {
  version: "TrackerSnapshotV4";
  generated_at: string;
  repo_root: string;
  summary: TrackerSummaryV1;
  phases: PhaseBoardV1;
  loop_state: LoopStateV1;
  capability_gaps: CapabilityGapV1;
  changelog: ChangelogV1;
  current_features: CurrentFeaturesV1;
  current_guidance: CurrentGuidanceV1;
  loop_processes: LoopProcessesV1;
  human_gate_stats: HumanGateStatsV1;
  archive_register: ArchiveRegisterV1;
  policies: PolicyDomainSummaryV1;
  topology: TopologySnapshotV1;
  project_overview: ProjectOverviewV1;
  service_inventory: ServiceInventoryV1;
  harness_help: HarnessHelpV1;
  qa_signals?: QaSignalsV1;
  git: GitStateV1;
  docs: DocRecordV1[];
}

export interface TrackerSnapshotV5 extends Omit<TrackerSnapshotV4, "version"> {
  version: "TrackerSnapshotV5";
  review_queue: ReviewQueueV1;
  route_context_coverage: RouteContextCoverageV1;
  human_review_summary: HumanReviewSummaryV1;
}

export interface TrackerSnapshotV6 extends Omit<TrackerSnapshotV5, "version" | "summary"> {
  version: "TrackerSnapshotV6";
  summary: TrackerSummaryV2;
}

export type TrackerSnapshotV4OrV5 = TrackerSnapshotV4 | TrackerSnapshotV5;
export type TrackerSnapshotVLegacy = TrackerSnapshotV4 | TrackerSnapshotV5;
export type TrackerSnapshotVLatest = TrackerSnapshotV6;

export interface ControlRuntimeStateV1 {
  last_sync_at: string;
  last_sync_result: "never" | "success" | "failed";
  last_sync_duration_ms: number;
  sync_count: number;
  syncing: boolean;
  last_error: string;
}

export interface UiAccessStatusV1 {
  runtime_mode: "wsl" | "linux" | "other";
  bind_host: string;
  ui_port: number;
  preferred_urls: string[];
  browser_access_summary: string;
  remote_ssh_tunnel_example: string;
  execution_host_summary: string;
  public_bind_supported: boolean;
}

export interface AssistantRuntimeStatusV1 {
  assistant: "codex_cli" | "claude_code";
  label: string;
  command: string;
  args: string[];
  terminal_command_template: string;
  availability_status: "available" | "unavailable";
  detail: string;
}

export interface ControlStatusV1 {
  api: "TrackerControlStatusV1";
  runtime_state: ControlRuntimeStateV1;
  runtime_snapshot: {
    generated_at?: string;
    docs_indexed?: number;
    markdown_changed_count?: number;
    branch?: string;
  };
  tracker_snapshot: {
    version: string;
    generated_at: string;
    summary: Partial<TrackerSummaryV1 | TrackerSummaryV2>;
  };
  ui_access?: UiAccessStatusV1;
  assistant_runtimes?: {
    codex_cli: AssistantRuntimeStatusV1;
    claude_code: AssistantRuntimeStatusV1;
  };
  remote_ssh?: {
    feature_flag_enabled: boolean;
    ssh_binary_available: boolean;
    allowed_command_prefixes: string[];
    mode: "disabled" | "guarded";
  };
  builder_feature_flags?: {
    managed_by: "environment";
    existing_project_mode_enabled: boolean;
    allowlisted_root: string;
    path_disclosure_mode: "masked" | "full";
    scan_limits_defaults: {
      max_depth: number;
      max_files: number;
    };
    project_status_history_retention: number;
  };
}
