import type {
  AnnotationCreateRequest,
  AutoReviewerConfigUpdate,
  AutoReviewerDryRun,
  AutoReviewerStats,
  ContextRecord,
  DreamCoverageResponse,
  DreamCycle,
  DreamCycleListResponse,
  DreamFunnelResponse,
  EvalsResponse,
  ExportCreateRequest,
  ExportsResponse,
  GraphParams,
  GraphPayload,
  HealthPayload,
  LearnedContextRestoreRequest,
  MemoryLineage,
  MemoryListParams,
  MemoryListResponse,
  MemoryRecord,
  OverviewPayload,
  ReviewDecisionRequest,
  ReviewsResponse,
  RetrievalListParams,
  RetrievalListResponse,
  RetrievalRecord,
  RunDiff,
  RunListParams,
  RunListResponse,
  RunRecord,
  SemanticChangeReview,
  SemanticDreamModeRequest,
  ServiceControlRequest,
  ShowcaseResponse,
  SessionDiagnostics,
  SessionRecord,
  SessionTimeline,
  SessionsResponse,
  UiContext,
  UiMeta,
  WorkspaceDashboard,
  WorkspaceInspectResponse,
} from './types';

const BASE_URL = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return '';
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch (err) {
    throw new ApiError(0, null, `Network error: ${(err as Error).message}`);
  }

  const contentType = response.headers.get('content-type') ?? '';
  let body: unknown = null;
  if (contentType.includes('application/json')) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  } else {
    try {
      body = await response.text();
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, body, `${response.status} ${response.statusText} for ${path}`);
  }

  return body as T;
}

// ----- GET endpoints -----

export const getUiMeta = () => api<UiMeta>('/api/ui-meta');
export const getUiContext = () => api<UiContext>('/api/ui-context');
export const getHealth = () => api<HealthPayload>('/api/health');
export const getOverview = () => api<OverviewPayload>('/api/overview');

export const getLatestSemanticChange = () =>
  api<SemanticChangeReview>('/api/semantic-changes/latest');
export const getSemanticChange = (sourceId: string) =>
  api<SemanticChangeReview>(`/api/semantic-changes/${encodeURIComponent(sourceId)}`);

export const getWorkspaces = () => api<WorkspaceDashboard>('/api/workspaces');
export const inspectWorkspace = (workspaceArg: string) =>
  api<WorkspaceInspectResponse>(`/api/workspaces/${encodeURIComponent(workspaceArg)}`);

export const getMemories = (params?: MemoryListParams) =>
  api<MemoryListResponse>(`/api/memories${buildQuery(params as Record<string, unknown>)}`);
export const getMemory = (id: string) =>
  api<MemoryRecord>(`/api/memories/${encodeURIComponent(id)}`);
export const getMemoryLineage = (id: string) =>
  api<MemoryLineage>(`/api/memories/${encodeURIComponent(id)}/lineage`);

export const getSessions = () => api<SessionsResponse>('/api/sessions');
export const getSessionTimeline = (id: string) =>
  api<SessionTimeline>(`/api/sessions/${encodeURIComponent(id)}/timeline`);
export const getSessionDiagnostics = async (): Promise<SessionDiagnostics | null> => {
  try {
    return await api<SessionDiagnostics>('/api/sessions/diagnostics');
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
};

export const getRuns = (params?: RunListParams) =>
  api<RunListResponse>(`/api/runs${buildQuery(params as Record<string, unknown>)}`);
export const getRun = (id: string) =>
  api<RunRecord>(`/api/runs/${encodeURIComponent(id)}`);
export const getRunDiff = (id: string) =>
  api<RunDiff>(`/api/runs/${encodeURIComponent(id)}/diff`);

export const getDreamCycles = (params?: { limit?: number; since?: string }) =>
  api<DreamCycleListResponse>(`/api/dream/cycles${buildQuery(params)}`);
export const getDreamCycle = (id: string) =>
  api<DreamCycle>(`/api/dream/cycles/${encodeURIComponent(id)}`);
export const getDreamCoverage = (params?: { window?: string }) =>
  api<DreamCoverageResponse>(`/api/dream/coverage${buildQuery(params)}`);
export const getDreamFunnel = (params?: { window?: string }) =>
  api<DreamFunnelResponse>(`/api/dream/funnel${buildQuery(params)}`);

export const getRetrievals = (params?: RetrievalListParams) =>
  api<RetrievalListResponse>(`/api/retrievals${buildQuery(params as Record<string, unknown>)}`);
export const getRetrieval = (id: string) =>
  api<RetrievalRecord>(`/api/retrievals/${encodeURIComponent(id)}`);

export const getContext = (id: string) =>
  api<ContextRecord>(`/api/context/${encodeURIComponent(id)}`);

export const getGraph = (params?: GraphParams) =>
  api<GraphPayload>(`/api/graph${buildQuery(params as Record<string, unknown>)}`);

export const getReviews = () => api<ReviewsResponse>('/api/reviews');
export const getEvals = () => api<EvalsResponse>('/api/evals');
export const getExports = () => api<ExportsResponse>('/api/exports');
export const getShowcase = () => api<ShowcaseResponse>('/api/showcase');

// ----- POST endpoints -----

export const createAnnotation = (payload: AnnotationCreateRequest) =>
  api<unknown>('/api/annotations', { method: 'POST', body: JSON.stringify(payload) });

export const createExport = (payload: ExportCreateRequest) =>
  api<unknown>('/api/exports', { method: 'POST', body: JSON.stringify(payload) });

export const liveCheck = () =>
  api<HealthPayload>('/api/health/live-check', { method: 'POST' });

export const submitReviewDecision = (subpath: string, payload: ReviewDecisionRequest) =>
  api<unknown>(`/api/reviews/${subpath.replace(/^\//, '')}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export interface ReviewRecommendation {
  queue_item_id: string;
  queue_item_type?: string;
  object_type?: string;
  object_id?: string;
  rule_id: string;
  action: string;
  rationale: string;
  snapshot?: Record<string, unknown>;
}

export interface ReviewRecommendationsResponse {
  items: ReviewRecommendation[];
  by_action: Record<string, number>;
  by_rule: Record<string, number>;
  total_items: number;
  total_recommended: number;
}

export const getReviewRecommendations = async (): Promise<ReviewRecommendationsResponse | null> => {
  try {
    return await api<ReviewRecommendationsResponse>('/api/reviews/recommendations');
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
};

export interface ApplyRecommendationsResponse {
  status: string;
  applied_count: number;
  proposed_count: number;
  by_rule: Record<string, number>;
}

export const applyReviewRecommendations = (rule_ids?: string[]) =>
  api<ApplyRecommendationsResponse>('/api/reviews/recommendations/apply', {
    method: 'POST',
    body: JSON.stringify(rule_ids ? { rule_ids } : {}),
  });

export const setSemanticDreamMode = (payload: SemanticDreamModeRequest) =>
  api<unknown>('/api/semantic-dream-mode', { method: 'POST', body: JSON.stringify(payload) });

export const restoreLearnedContext = (payload: LearnedContextRestoreRequest) =>
  api<unknown>('/api/learned-context/restore', { method: 'POST', body: JSON.stringify(payload) });

export const controlService = (payload: ServiceControlRequest) =>
  api<unknown>('/api/service/control', { method: 'POST', body: JSON.stringify(payload) });

export interface DreamRunResult {
  status?: string;
  reason?: string;
  phases?: string[];
  duration_ms?: number;
  appended_events?: number;
  gathered_rows?: number;
  run_id?: string;
  trigger_class?: string;
  mode?: string;
  narrative?: string;
}

export const runDream = (mode?: 'full' | 'semantic' | 'hybrid') =>
  api<DreamRunResult>('/api/dream/run', {
    method: 'POST',
    body: JSON.stringify(mode ? { mode } : {}),
  });

export interface TranscriptsIngestResult {
  status?: string;
  files_seen?: number;
  files_written?: number;
  files_skipped?: number;
  rows_in?: number;
  rows_out?: number;
  source_dir?: string;
  target_dir?: string;
  written_paths_sample?: string[];
}

export const ingestTranscripts = (overwrite = false) =>
  api<TranscriptsIngestResult>('/api/transcripts/ingest', {
    method: 'POST',
    body: JSON.stringify({ overwrite }),
  });

export type SessionRecordExport = SessionRecord;

// ----- Auto-reviewer endpoints (404 = feature not yet deployed) -----

export async function getAutoReviewerStats(): Promise<AutoReviewerStats | null> {
  try {
    return await api<AutoReviewerStats>('/api/auto-reviewer/stats');
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function runAutoReviewerDryRun(): Promise<AutoReviewerDryRun | null> {
  try {
    return await api<AutoReviewerDryRun>('/api/auto-reviewer/run-dry', { method: 'POST' });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function updateAutoReviewerConfig(payload: AutoReviewerConfigUpdate): Promise<boolean> {
  try {
    await api<unknown>('/api/auto-reviewer/config', { method: 'POST', body: JSON.stringify(payload) });
    return true;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return false;
    throw e;
  }
}
