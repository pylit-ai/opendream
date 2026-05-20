// API response types for the OpenDream Observe backend.
// Shapes are derived from opendream/webapp.py + observability.py.
// Many handlers return `unknown` deep payloads (raw store records). These stay
// loosely typed until a surface needs a stricter contract.

export interface UiMeta {
  // Shape returned by _ui_meta_payload (webapp.py); contains UI version + capabilities.
  [key: string]: unknown;
}

export interface UiContext {
  // Shape returned by _ui_context_payload (webapp.py).
  [key: string]: unknown;
}

export interface HealthPayload {
  // Shape from _health_payload(store).
  status?: string;
  [key: string]: unknown;
}

export interface StatusSnapshot {
  workspace?: string;
  store_id?: string;
  store_kind?: string;
  initialized?: boolean;
  state?: string;
  pending_events?: number;
  pending_candidates?: number;
  next_eligible_reason?: string;
  next_eligible_at?: string | null;
  dream?: {
    state?: string;
    queue_depth?: number;
    worker?: {
      state?: string;
      active_phase?: string;
      processed_jobs?: number;
      [key: string]: unknown;
    };
    worker_health?: {
      health?: string;
      active_phase?: string;
      active_job_id?: string;
      queue_backlog?: number;
      last_success_at?: string;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  automation?: {
    job_count?: number;
    enabled_jobs?: number;
    due_job_ids?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ShowcaseSourceRef {
  memory_id?: string;
  title?: string;
  type?: string;
  summary?: string;
  status?: string;
  source_event_ids?: string[];
  source_events?: Array<Record<string, unknown>>;
}

export interface ShowcasePromptLink {
  memory_id?: string;
  memory_href?: string;
  title?: string;
  summary?: string;
  source_event_ids?: string[];
  source_refs?: Array<Record<string, unknown>>;
  why_included?: string;
  score?: number;
}

export interface ShowcaseRetrievalReason {
  memory_id?: string;
  score?: number;
  why_included?: string;
  why_excluded?: string | null;
  matched_evidence?: Record<string, unknown>;
  score_contributions?: Record<string, unknown>;
  provenance_tier?: string;
  status?: string;
}

export interface ShowcaseReport {
  scenario?: string;
  status?: string;
  generated_at?: string;
  report_path?: string;
  selected_memory_ids?: string[];
  agent_snippet?: string;
  agent_answers?: {
    stateless?: ShowcaseAgentAnswer;
    memory_assisted?: ShowcaseAgentAnswer;
    comparison?: ShowcaseAnswerComparison;
    [key: string]: unknown;
  };
  objective?: {
    title?: string;
    description?: string;
    success_criteria?: string[];
    research_pattern?: string;
  };
  evaluation_case?: {
    user_prompt?: string;
    retrieval_query?: string;
    expected_response?: string;
    why_this_tests_memory?: string;
    failure_without_memory?: string;
  };
  before?: { selected_memory_ids?: string[]; [key: string]: unknown };
  after?: { selected_memory_ids?: string[]; [key: string]: unknown };
  context?: {
    context_id?: string;
    selected_memory_ids?: string[];
    prompt_context?: string;
    visibility?: Record<string, unknown>;
    selection?: Record<string, unknown>;
    context_pruning?: Record<string, unknown>;
    links?: ShowcasePromptLink[];
  };
  proof?: {
    query?: string;
    source_refs?: ShowcaseSourceRef[];
    expected_signals?: string[];
  };
  retrieval_rationale?: ShowcaseRetrievalReason[];
  reproducibility?: Record<string, unknown>;
  copy_actions?: {
    command?: string;
    report_json_url?: string;
    report_path?: string;
    fixture_path?: string;
  };
  stability_check?: {
    passed?: boolean;
    same_selected_memory_ids?: boolean;
    equivalent_titles?: boolean;
    expected_memory_ids?: string[];
    repeated_memory_ids?: string[];
    expected_titles?: string[];
    repeated_titles?: string[];
  };
  scenario_scale?: Record<string, unknown>;
  agent_observability_trace?: {
    schema?: string;
    run_id?: string;
    session_id?: string;
    context_id?: string;
    source_event_ids?: string[];
    selected_memory_ids?: string[];
    spans?: Array<Record<string, unknown>>;
  };
  evidence_drilldown?: {
    selected?: Array<Record<string, unknown>>;
    excluded?: Array<Record<string, unknown>>;
  };
  selected_vs_excluded?: {
    selected_count?: number;
    excluded_count?: number;
    selected_memory_ids?: string[];
    excluded_memory_ids?: string[];
    excluded_reason_counts?: Record<string, number>;
  };
  score_visualization?: {
    bars?: Array<{ key?: string; label?: string; score?: number; passed?: boolean }>;
    answer_score_delta?: number;
    passed_count?: number;
    total_count?: number;
  };
  claim_verification?: {
    passed?: boolean;
    trust_level?: string;
    summary?: string;
    claims?: Array<Record<string, unknown>>;
  };
  memory_safety?: {
    passed?: boolean;
    risk_level?: string;
    risk_categories?: Array<Record<string, unknown>>;
    misevolution_cases?: Array<Record<string, unknown>>;
  };
  glossary?: Record<string, string>;
  dream_effectiveness?: {
    summary?: string;
    pipeline?: Array<Record<string, unknown>>;
    metrics?: Record<string, unknown>;
    why_it_matters?: string[];
    effective?: Record<string, boolean>;
  };
  checks?: Record<string, { passed?: boolean; detail?: string; [key: string]: unknown }>;
  [key: string]: unknown;
}

export interface ShowcaseAnswerSignal {
  key?: string;
  label?: string;
  passed?: boolean;
  required_terms?: string[];
  missing_terms?: string[];
  forbidden_terms?: string[];
  forbidden_matches?: string[];
  requires_source_refs?: boolean;
}

export interface ShowcaseAnswerMeasurement {
  score?: number;
  passed?: boolean;
  passed_count?: number;
  total_count?: number;
  signals?: ShowcaseAnswerSignal[];
  selected_memory_count?: number;
  source_ref_count?: number;
}

export interface ShowcaseAgentAnswer {
  label?: string;
  mode?: string;
  input?: string;
  selected_memory_ids?: string[];
  answer?: string;
  measurement?: ShowcaseAnswerMeasurement;
}

export interface ShowcaseAnswerComparison {
  score_delta?: number;
  stateless_passed?: boolean;
  memory_assisted_passed?: boolean;
  passed?: boolean;
  stateless_missing_or_failed?: string[];
  memory_assisted_passed_signals?: string[];
}

export interface ShowcaseResponse {
  available: boolean;
  report?: ShowcaseReport | null;
  report_path?: string;
  command?: string;
  [key: string]: unknown;
}

export interface OverviewPayload {
  // Shape from index["overview"] in observability.index_observability().
  generated_at?: string;
  counts?: Record<string, number>;
  readiness?: unknown;
  recent?: unknown[];
  [key: string]: unknown;
}

export interface SemanticDreamConfig {
  mode?: 'deterministic' | 'semantic' | 'hybrid' | string;
  retention?: {
    learned_context_archive_grace_days?: number;
    learned_context_archive_grace_contexts?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface SemanticRetentionProjection {
  grace_days: number;
  grace_contexts: number;
  would_archive_now: number;
  held_by_activity: number;
  expired_within_calendar_grace: number;
  active_total: number;
  archived_total: number;
  directly_restorable_total?: number;
  reopenable_archived_total?: number;
  restore_window_expired_total?: number;
  restore_window_missing_total?: number;
  learned_context_total: number;
  context_assembly_total: number;
  latest_context_created_at?: string | null;
  oldest_active_fresh_until?: string | null;
  future_only?: boolean;
  immediate_effect?: 'future_only' | 'would_archive' | 'no_active_change' | string;
  id?: string;
  label?: string;
  [key: string]: unknown;
}

export interface SemanticRetentionPreview {
  generated_at?: string;
  selected?: SemanticRetentionProjection;
  presets?: SemanticRetentionProjection[];
  [key: string]: unknown;
}

export interface SettingsPayload extends OverviewPayload {
  semantic_config?: SemanticDreamConfig;
  retention_preview?: SemanticRetentionPreview;
}

export interface SemanticChangeItem {
  change_id?: string;
  record_id?: string;
  summary?: string;
  change_class?: 'kept' | 'suppressed' | 'deactivated' | 'restored' | string;
  reason_code?: string;
  before_state?: string;
  after_state?: string;
  source_context_id?: string;
  source_run_id?: string;
  changed_at?: string;
  restore_allowed?: boolean;
  restore_href?: string;
  [key: string]: unknown;
}

export interface SemanticChangeReview {
  source_id?: string;
  source_kind?: string;
  source_run_id?: string;
  created_at?: string;
  status?: string;
  summary_counts?: {
    kept_count?: number;
    suppressed_count?: number;
    deactivated_count?: number;
    restorable_count?: number;
    restored_count?: number;
    [key: string]: unknown;
  };
  items?: SemanticChangeItem[];
  [key: string]: unknown;
}

export interface WorkspaceEntry {
  // workspace_catalog.inspect_entry() return shape.
  path?: string;
  label?: string;
  [key: string]: unknown;
}

export interface WorkspaceDashboard {
  // _workspace_dashboard_payload(); usually contains items + active workspace.
  items?: WorkspaceEntry[];
  active?: WorkspaceEntry | null;
  [key: string]: unknown;
}

export type WorkspaceInspectResponse =
  | { status: 'missing'; workspace: string }
  | { status: 'ok'; entry: WorkspaceEntry };

export interface PageMeta {
  total?: number;
  offset?: number;
  limit?: number;
  has_more?: boolean;
  [key: string]: unknown;
}

export interface MemoryRecord {
  memory_id: string;
  type?: string;
  scope?: string;
  status?: string;
  agent_id?: string;
  salience?: number;
  confidence?: number;
  created_at?: string;
  updated_at?: string;
  summary?: string;
  body?: string;
  lineage?: MemoryLineage;
  [key: string]: unknown;
}

export interface MemoryListResponse {
  items: MemoryRecord[];
  total?: number;
  filters?: Record<string, unknown>;
  // query_memories shape includes facets/aggregates; refine when needed.
  [key: string]: unknown;
}

export interface MemoryLineage {
  // Lineage shape from observability.
  ancestors?: unknown[];
  descendants?: unknown[];
  [key: string]: unknown;
}

export interface SessionRecord {
  session_id: string;
  display_name?: string;
  latest_context_id?: string;
  latest_context_query?: string;
  agent_id?: string;
  started_at?: string;
  ended_at?: string;
  event_count?: number;
  context_count?: number;
  [key: string]: unknown;
}

export interface SessionListParams extends PageParams {
  since?: string;
}

export interface SessionsResponse {
  items: SessionRecord[];
}

export interface SessionDiagnostics {
  orphan_events: Array<{ event_id: string; session_id: string }>;
  orphan_events_total: number;
  mismatch_records: Array<{
    session_id: string;
    recorded_event_count: number;
    actual_event_count: number;
  }>;
  mismatch_records_total: number;
  zero_event_sessions: string[];
  zero_event_sessions_total: number;
  total_sessions: number;
  total_events: number;
}

export interface SessionTimeline extends SessionRecord {
  // Timeline-specific fields (events, segments).
  events?: unknown[];
  [key: string]: unknown;
}

export interface RunRecord {
  run_id: string;
  status?: string;
  started_at?: string;
  ended_at?: string;
  agent_id?: string;
  summary?: string;
  diff_text?: string;
  [key: string]: unknown;
}

export interface RunListResponse {
  items: RunRecord[];
  total?: number;
  [key: string]: unknown;
}

export interface RunDiff {
  run_id: string;
  diff_text: string;
}

export interface DreamFunnelCounts {
  considered: number;
  selected: number;
  generated: number;
  approved: number;
  created: number;
}

export interface DreamPhaseTrace {
  phase: string;
  duration_ms?: number;
  started_at?: string;
  ended_at?: string;
  [key: string]: unknown;
}

export interface DreamChangePointContributor {
  key: string;
  value?: string | number | boolean;
  from?: unknown;
  to?: unknown;
  delta?: number;
  phase?: string;
  baseline_ms?: number;
  duration_ms?: number;
  ratio?: number;
  weight?: number;
  [key: string]: unknown;
}

export interface DreamChangePoint {
  score: number;
  severity: 'low' | 'medium' | 'high';
  kind: 'material' | 'failure' | 'drift' | 'duration_anomaly' | 'boundary' | 'cumulative' | 'noop';
  label: string;
  contributors: DreamChangePointContributor[];
  signature: string;
  is_noop: boolean;
}

export interface DreamCycle {
  run_id: string;
  type?: string;
  mode?: string;
  status?: string;
  reason?: string;
  started_at?: string;
  ended_at?: string;
  duration_ms?: number;
  model_id?: string;
  cost_usd?: number;
  tokens_used?: number;
  signal_source?: string;
  latest_signal_timestamp?: string;
  signal_row_count?: number;
  appended_events?: number;
  funnel: DreamFunnelCounts;
  phase_durations: Record<string, number>;
  phase_traces?: DreamPhaseTrace[];
  phases?: string[];
  trace_summary?: DreamTraceSummary;
  narrative: string;
  reporting_agent_label?: string;
  warnings?: string[];
  summary?: Record<string, unknown>;
  learned_context_created?: number;
  learned_context_superseded?: number;
  proposals_generated?: number;
  proposals_approved?: number;
  proposals_rejected?: number;
  change_point?: DreamChangePoint;
  [key: string]: unknown;
}

export interface DreamTraceSummary {
  input_consumed?: boolean;
  signal_source?: string;
  latest_signal_timestamp?: string;
  rows_scanned?: number;
  rows_gathered?: number;
  families_considered?: number;
  families_selected?: number;
  selected_family_ids?: string[];
  family_result_count?: number;
  drop_reasons?: string[];
  fallback_reason?: string;
  proposal_ids?: string[];
  proposals_generated?: number;
  verifier_verdicts?: Record<string, number>;
  learned_context_created?: number;
  promoted_record_ids?: string[];
  retention_status?: string;
  no_materialization_reason?: string;
  [key: string]: unknown;
}

export interface DreamCycleListResponse {
  total: number;
  items: DreamCycle[];
}

export interface DreamCoverageBucket {
  bucket: string;
  total: number;
  explicit_events: number;
  transcript_episodes: number;
  automation: number;
  shares: Record<string, number>;
}

export interface DreamCoverageResponse {
  window: string;
  items: DreamCoverageBucket[];
}

export interface DreamFunnelResponse {
  window: string;
  total_cycles: number;
  funnel: DreamFunnelCounts;
  cycles: Array<{ run_id: string; started_at?: string; ended_at?: string; funnel: DreamFunnelCounts }>;
}

export interface RetrievalRecord {
  id: string;
  agent_id?: string;
  timestamp?: string;
  query?: string;
  selected?: number;
  candidates?: unknown[];
  [key: string]: unknown;
}

export interface RetrievalListResponse {
  items: RetrievalRecord[];
  total?: number;
  [key: string]: unknown;
}

export interface ContextRecord {
  context_id: string;
  display_name?: string;
  session_id?: string;
  created_at?: string;
  character_count?: number;
  selected_memory_ids_count?: number;
  selected_memory_ids?: string[];
  context_use_records?: ContextUseRecord[];
  context_use_count?: number;
  latest_memory_use_state?: string;
  latest_context_use_id?: string;
  query?: string;
  selection?: Record<string, { candidate_count?: number; selected?: number }>;
  context_pruning?: {
    candidate_count?: number;
    injected_count?: number;
    suppressed_count?: number;
    saved_token_estimate?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ContextListParams extends PageParams {
  session_id?: string;
}

export interface ContextListResponse {
  items: ContextRecord[];
  total?: number;
  [key: string]: unknown;
}

export interface ContextUseRecord {
  usage_id: string;
  context_id: string;
  timestamp?: string;
  memory_use_state?: string;
  selected_memory_ids_count?: number;
  used_memory_ids_count?: number;
  used_memory_ids?: string[];
  usage_note?: string;
  visible_attestation?: string;
  reporting_agent?: {
    agent_id?: string;
    agent_label?: string;
    runtime?: string;
    adapter_id?: string;
    [key: string]: unknown;
  };
  reporting_agent_label?: string;
  context_query?: string;
  context_display_name?: string;
  display_name?: string;
  [key: string]: unknown;
}

export interface ContextUseListParams extends PageParams {
  context_id?: string;
  state?: string;
}

export interface ContextUseListResponse {
  items: ContextUseRecord[];
  total?: number;
  [key: string]: unknown;
}

export interface GraphPayload {
  // build_graph(...) — sigma/graphology compatible nodes/edges.
  nodes?: Array<{ id: string; label?: string; x?: number; y?: number; size?: number; color?: string; [k: string]: unknown }>;
  edges?: Array<{ id?: string; source: string; target: string; label?: string; [k: string]: unknown }>;
  focus?: string | null;
  layout?: string;
  [key: string]: unknown;
}

export interface ReviewItem {
  // Review queue item shape.
  id?: string;
  [key: string]: unknown;
}

export interface ReviewDecision {
  // store.load_review_decisions item shape.
  [key: string]: unknown;
}

export interface ReviewsResponse {
  items: ReviewItem[];
  decisions: ReviewDecision[];
}

export interface EvalsResponse {
  health: unknown;
  evals: unknown;
}

export interface ExportItem {
  // Export item shape.
  id?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface ExportsResponse {
  items: ExportItem[];
}

// POST request payloads

export interface AnnotationCreateRequest {
  object_type: string;
  object_id: string;
  actor: string;
  label: string;
  note: string;
  score?: number | null;
}

export interface ExportCreateRequest {
  // Shape consumed by create_export().
  [key: string]: unknown;
}

export interface ReviewDecisionRequest {
  // Shape consumed by create_review_decision().
  [key: string]: unknown;
}

export interface SemanticDreamModeRequest {
  mode?: string;
  enabled?: boolean;
  [key: string]: unknown;
}

export interface LearnedContextRestoreRequest {
  // Empty request body accepted.
  [key: string]: unknown;
}

export interface LearnedContextReopenRequest {
  limit?: number;
  record_ids?: string[];
  [key: string]: unknown;
}

export interface ServiceControlRequest {
  action?: string;
  [key: string]: unknown;
}

// Auto-reviewer types

export interface AutoReviewerRuleStats {
  rule_id: string;
  applied_count?: number;
  [key: string]: unknown;
}

export interface AutoReviewerLastRun {
  applied_count: number;
  by_rule: Record<string, number>;
  started_at?: string;
  finished_at?: string;
}

export interface AutoReviewerRule {
  rule_id: string;
  enabled: boolean;
  threshold_summary: Record<string, unknown>;
}

export interface AutoReviewerStats {
  last_run: AutoReviewerLastRun | null;
  rules: AutoReviewerRule[];
  cooldown_count: number;
}

export interface AutoReviewerDryRun {
  proposed_count: number;
  by_rule: Record<string, number>;
}

export interface AutoReviewerConfigUpdate {
  rule_id: string;
  enabled?: boolean;
  threshold_summary?: Record<string, unknown>;
}

// Query parameter shapes

export interface PageParams {
  search?: string;
  sort?: string;
  sort_dir?: 'asc' | 'desc';
  offset?: number;
  limit?: number;
}

export interface MemoryListParams extends PageParams {
  type?: string;
  scope?: string;
  status?: string;
  agent_id?: string;
  salience_min?: number;
  salience_max?: number;
  confidence_min?: number;
  confidence_max?: number;
  updated_after?: string;
  updated_before?: string;
  created_after?: string;
  created_before?: string;
}

export interface RunListParams extends PageParams {
  ended_after?: string;
  ended_before?: string;
}

export interface RetrievalListParams extends PageParams {
  agent_id?: string;
  timestamp_after?: string;
  timestamp_before?: string;
  min_selected?: number;
  max_selected?: number;
}

export interface GraphParams {
  focus?: string;
  depth?: number;
  layout?: string;
  limit?: number;
}
