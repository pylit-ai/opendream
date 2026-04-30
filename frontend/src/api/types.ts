// API response types for the OpenDream Observe backend.
// Shapes are derived from opendream/webapp.py + observability.py.
// Many handlers return `unknown` deep payloads (raw store records) — those
// are typed loosely with TODO markers; refine when the surface needs them.

export interface UiMeta {
  // TODO: shape returned by _ui_meta_payload (webapp.py); contains UI version + capabilities.
  [key: string]: unknown;
}

export interface UiContext {
  // TODO: shape returned by _ui_context_payload (webapp.py).
  [key: string]: unknown;
}

export interface HealthPayload {
  // TODO: shape from _health_payload(store).
  status?: string;
  [key: string]: unknown;
}

export interface OverviewPayload {
  // TODO: shape from index["overview"] in observability.index_observability().
  generated_at?: string;
  counts?: Record<string, number>;
  readiness?: unknown;
  recent?: unknown[];
  [key: string]: unknown;
}

export interface SemanticChangeReview {
  // TODO: build_semantic_change_review() return shape.
  source_id?: string;
  generated_at?: string;
  status?: string;
  changes?: unknown[];
  [key: string]: unknown;
}

export interface WorkspaceEntry {
  // TODO: workspace_catalog.inspect_entry() return shape.
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
  // TODO: query_memories shape includes facets/aggregates; refine.
  [key: string]: unknown;
}

export interface MemoryLineage {
  // TODO: lineage shape from observability.
  ancestors?: unknown[];
  descendants?: unknown[];
  [key: string]: unknown;
}

export interface SessionRecord {
  session_id: string;
  agent_id?: string;
  started_at?: string;
  ended_at?: string;
  [key: string]: unknown;
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
  // TODO: timeline-specific fields (events, segments).
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
  signal_row_count?: number;
  funnel: DreamFunnelCounts;
  phase_durations: Record<string, number>;
  phase_traces?: DreamPhaseTrace[];
  phases?: string[];
  narrative: string;
  reporting_agent_label?: string;
  warnings?: string[];
  summary?: Record<string, unknown>;
  learned_context_created?: number;
  learned_context_superseded?: number;
  proposals_generated?: number;
  proposals_approved?: number;
  proposals_rejected?: number;
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
  // TODO: context payload shape.
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
  // TODO: review queue item shape.
  id?: string;
  [key: string]: unknown;
}

export interface ReviewDecision {
  // TODO: store.load_review_decisions item shape.
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
  // TODO: export item shape.
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
  // TODO: shape consumed by create_export().
  [key: string]: unknown;
}

export interface ReviewDecisionRequest {
  // TODO: shape consumed by create_review_decision().
  [key: string]: unknown;
}

export interface SemanticDreamModeRequest {
  mode?: string;
  enabled?: boolean;
  [key: string]: unknown;
}

export interface LearnedContextRestoreRequest {
  // TODO
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
