import { createMemo, createResource, For, Show, type JSX } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { Activity } from 'lucide-solid';
import { getOverview, getRetrievals, getRuns } from '~/api/client';
import type {
  OverviewPayload,
  RetrievalListResponse,
  RunListResponse,
  RunRecord,
} from '~/api/types';
import { Page } from '~/components/Page';
import { StatStrip, type Stat } from '~/components/StatStrip';
import { Chip } from '~/components/Chip';
import { SkeletonRows, SkeletonStats } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { EmptyState } from '~/components/EmptyState';
import { formatDate, formatDateLong, formatDuration } from '~/lib/format';
import { cachedFetch } from '~/lib/cache';

interface MemorySurface {
  durable_active_total?: number;
  durable_contested_total?: number;
  learned_context_active_total?: number;
  learned_context_recently_pruned_total?: number;
  recent_highlights?: Array<{
    memory_id?: string;
    title?: string;
    summary?: string;
    type?: string;
    status?: string;
    updated_at?: string;
  }>;
}

interface RecentRunItem {
  run_id?: string;
  id?: string;
  type?: string;
  status?: string;
  summary?: string;
  started_at?: string;
  ended_at?: string;
  reporting_agent_label?: string;
  source_reporting_agents?: Array<{ agent_label?: string; agent_id?: string }>;
}

interface RecentSession {
  session_id?: string;
  started_at?: string;
  ended_at?: string;
  event_count?: number;
}

interface UnifiedRecent {
  kind: string;
  id: string;
  summary?: string;
  agent?: string;
  status?: string;
  duration?: string;
  ts?: string;
}

function asPreview(v: unknown): string | undefined {
  if (v == null) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v).slice(0, 240);
  } catch {
    return undefined;
  }
}

function durationOf(start?: string, end?: string): string | undefined {
  if (!start || !end) return undefined;
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (Number.isNaN(a) || Number.isNaN(b)) return undefined;
  return formatDuration(Math.max(0, b - a));
}

function extractAgent(r: RecentRunItem): string | undefined {
  if (r.reporting_agent_label) return r.reporting_agent_label;
  const list = r.source_reporting_agents;
  if (Array.isArray(list) && list.length > 0) {
    return list.map((a) => a.agent_label ?? a.agent_id ?? '?').join(', ');
  }
  return undefined;
}

function statusTone(s: string | undefined): 'ok' | 'warn' | 'danger' | 'neutral' {
  const v = (s ?? '').toLowerCase();
  if (!v) return 'neutral';
  if (v.includes('ok') || v.includes('success') || v.includes('complete')) return 'ok';
  if (v.includes('warn') || v.includes('partial')) return 'warn';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

function routeForKind(kind: string, id: string): string {
  const k = kind.toLowerCase();
  if (k.includes('retrieval')) return `/retrievals?id=${encodeURIComponent(id)}`;
  if (k.includes('session')) return `/sessions?id=${encodeURIComponent(id)}`;
  if (k.includes('memory')) return `/memories?id=${encodeURIComponent(id)}`;
  return `/runs?id=${encodeURIComponent(id)}`;
}

export default function OverviewRoute(): JSX.Element {
  const navigate = useNavigate();

  const [overview, { refetch }] = createResource<OverviewPayload>(() =>
    cachedFetch('overview', getOverview, 15_000),
  );

  const [fallbackRuns] = createResource<RunRecord[]>(async () => {
    const ov = (await cachedFetch('overview', getOverview, 15_000).catch(() => null)) as
      | (OverviewPayload & { recent_runs?: RecentRunItem[] })
      | null;
    if (Array.isArray(ov?.recent_runs) && ov!.recent_runs!.length > 0) return [];
    const r = (await cachedFetch(
      'runs:overview-recent',
      () => getRuns({ limit: 8 } as never),
      15_000,
    ).catch(() => ({ items: [] }))) as RunListResponse;
    return r.items ?? [];
  });

  const [fallbackRetrievals] = createResource<RetrievalListResponse | null>(async () => {
    const ov = (await cachedFetch('overview', getOverview, 15_000).catch(() => null)) as
      | (OverviewPayload & { recent_runs?: RecentRunItem[] })
      | null;
    if (Array.isArray(ov?.recent_runs) && ov!.recent_runs!.length > 0) return null;
    return (await cachedFetch(
      'retrievals:overview-recent',
      () => getRetrievals({ limit: 4 } as never),
      15_000,
    ).catch(() => null)) as RetrievalListResponse | null;
  });

  const recent = createMemo<UnifiedRecent[]>(() => {
    const ov = overview() as
      | (OverviewPayload & {
          recent_runs?: RecentRunItem[];
          recent_sessions?: RecentSession[];
        })
      | undefined;
    const items: UnifiedRecent[] = [];

    const runs = ov?.recent_runs ?? [];
    for (const r of runs) {
      items.push({
        kind: r.type ?? 'run',
        id: r.run_id ?? r.id ?? 'run',
        summary: r.summary,
        agent: extractAgent(r),
        status: r.status,
        duration: durationOf(r.started_at, r.ended_at),
        ts: r.ended_at ?? r.started_at,
      });
    }
    const sessions = ov?.recent_sessions ?? [];
    for (const s of sessions) {
      items.push({
        kind: 'session',
        id: s.session_id ?? 'session',
        summary:
          typeof s.event_count === 'number'
            ? `${s.event_count} event${s.event_count === 1 ? '' : 's'}`
            : undefined,
        duration: durationOf(s.started_at, s.ended_at),
        ts: s.ended_at ?? s.started_at,
      });
    }

    if (items.length === 0) {
      const fr = fallbackRuns() ?? [];
      for (const r of fr) {
        items.push({
          kind: 'run',
          id: r.run_id,
          summary: r.summary,
          agent: r.agent_id,
          status: r.status,
          duration: durationOf(r.started_at, r.ended_at),
          ts: r.ended_at ?? r.started_at,
        });
      }
      const retr = fallbackRetrievals();
      const retrItems = retr?.items ?? [];
      for (const r of retrItems) {
        items.push({
          kind: 'retrieval',
          id: r.id,
          summary: r.query,
          agent: r.agent_id,
          ts: r.timestamp,
        });
      }
    }

    return items
      .filter((x) => x.id)
      .sort((a, b) => (b.ts ?? '').localeCompare(a.ts ?? ''))
      .slice(0, 12);
  });

  const next = (): { posture?: string; nextAction?: string } => {
    const ov = overview() as
      | (OverviewPayload & { product_posture?: string; next_action?: string })
      | undefined;
    return { posture: ov?.product_posture, nextAction: ov?.next_action };
  };

  const highlights = (): MemorySurface['recent_highlights'] => {
    const ov = overview() as (OverviewPayload & { memory_surface?: MemorySurface }) | undefined;
    return ov?.memory_surface?.recent_highlights ?? [];
  };

  const buildClickableStats = (p: OverviewPayload | undefined): Stat[] => {
    const surface = ((p as { memory_surface?: MemorySurface } | undefined)?.memory_surface ??
      {}) as MemorySurface;
    const counts = ((p as { memory_counts?: { total?: number; by_status?: Record<string, number> } } | undefined)
      ?.memory_counts ?? {}) as { total?: number; by_status?: Record<string, number> };
    const retr = ((p as { retrievals?: { total?: number } } | undefined)?.retrievals ?? {}) as {
      total?: number;
    };

    const durable = surface.durable_active_total ?? counts.by_status?.active ?? counts.total ?? 0;
    const contested = surface.durable_contested_total ?? counts.by_status?.contested ?? 0;
    const learned = surface.learned_context_active_total ?? 0;
    const pruned = surface.learned_context_recently_pruned_total ?? 0;
    const retrievalTotal = retr.total ?? 0;

    return [
      {
        label: 'Durable',
        value: durable,
        onClick: () => navigate('/memories?status=active'),
      },
      {
        label: 'Contested',
        value: contested,
        tone: contested > 0 ? 'warn' : 'default',
        onClick: () => navigate('/memories?status=contested'),
      },
      {
        label: 'Learned active',
        value: learned,
        onClick: () => navigate('/memories?status=learned'),
      },
      {
        label: 'Recently pruned',
        value: pruned,
        onClick: () => navigate('/memories?status=pruned'),
      },
      {
        label: 'Retrievals',
        value: retrievalTotal,
        onClick: () => navigate('/retrievals'),
      },
    ];
  };

  return (
    <Page title="Overview" subtitle="Memory subsystem snapshot">
      <Show when={!overview.loading} fallback={<><SkeletonStats /><SkeletonRows rows={5} /></>}>
        <Show
          when={!overview.error}
          fallback={
            <ErrorState
              message={overview.error instanceof Error ? overview.error.message : String(overview.error)}
              onRetry={refetch}
            />
          }
        >
          <StatStrip stats={buildClickableStats(overview())} />

          <Show when={next().posture || next().nextAction}>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-muted">
              <Show when={next().posture}>
                <span class="text-text">Posture</span>
                <button
                  type="button"
                  onClick={() => navigate('/settings')}
                  class="cursor-pointer rounded transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                  title="Open settings"
                >
                  <Chip variant="neutral">{next().posture}</Chip>
                </button>
              </Show>
              <Show when={next().nextAction}>
                <span class="text-text-subtle">·</span>
                <span class="text-text">Next</span>
                <span class="text-xs">{next().nextAction}</span>
              </Show>
            </div>
          </Show>

          <section class="flex flex-col gap-3">
            <div class="text-[10px] uppercase tracking-[0.1em] text-text-subtle">
              Recent activity
            </div>
            <Show
              when={recent().length > 0}
              fallback={
                <EmptyState
                  icon={Activity}
                  title="No activity yet"
                  description="Runs, sessions, and retrievals appear here as agents work in this workspace."
                />
              }
            >
              <ul class="flex flex-col">
                <For each={recent()}>
                  {(item) => (
                    <li class="hairline-b">
                      <button
                        type="button"
                        onClick={() => navigate(routeForKind(item.kind, item.id))}
                        class="row-hover flex h-11 w-full items-center gap-3 px-1 text-left text-sm transition-colors hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/60"
                        title={`Open ${item.kind} ${item.id}`}
                      >
                        <span class="w-20 shrink-0 truncate text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                          {item.kind}
                        </span>
                        <span class="flex-1 truncate text-text" title={asPreview(item.summary) ?? item.id}>
                          {asPreview(item.summary) ?? <span class="text-text-subtle">—</span>}
                        </span>
                        <Show when={item.agent}>
                          <span
                            role="button"
                            tabindex={0}
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/runs?agent=${encodeURIComponent(item.agent!)}`);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.stopPropagation();
                                navigate(`/runs?agent=${encodeURIComponent(item.agent!)}`);
                              }
                            }}
                            class="hidden cursor-pointer rounded px-1 font-mono text-[11px] text-text-muted transition-colors hover:bg-[color-mix(in_oklab,rgb(var(--c-accent))_8%,transparent)] hover:text-accent sm:inline"
                            title={`Filter runs by ${item.agent}`}
                          >
                            {item.agent}
                          </span>
                        </Show>
                        <Show when={item.status}>
                          <span
                            role="button"
                            tabindex={0}
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/runs?status=${encodeURIComponent(item.status!)}`);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.stopPropagation();
                                navigate(`/runs?status=${encodeURIComponent(item.status!)}`);
                              }
                            }}
                            class="cursor-pointer rounded transition-opacity hover:opacity-80"
                            title={`Filter runs by status ${item.status}`}
                          >
                            <Chip variant={statusTone(item.status)}>{item.status}</Chip>
                          </span>
                        </Show>
                        <span class="font-mono text-[11px] tabular-nums text-text-muted">
                          {item.duration ?? '—'}
                        </span>
                        <span
                          title={item.ts ? formatDateLong(item.ts) : undefined}
                          class="w-16 text-right font-mono text-[11px] tabular-nums text-text-muted"
                        >
                          {item.ts ? formatDate(item.ts) : '—'}
                        </span>
                      </button>
                    </li>
                  )}
                </For>
              </ul>
            </Show>
          </section>

          <Show when={(highlights() ?? []).length > 0}>
            <section class="flex flex-col gap-3">
              <div class="text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                Memory highlights
              </div>
              <ul class="flex flex-col gap-1">
                <For each={highlights()}>
                  {(h) => (
                    <li>
                      <button
                        type="button"
                        onClick={() =>
                          h.memory_id &&
                          navigate(`/memories?id=${encodeURIComponent(h.memory_id)}`)
                        }
                        class="row-hover flex w-full items-center gap-3 rounded-md hairline px-2.5 py-1.5 text-left transition-colors hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                        title={`Open memory ${h.memory_id ?? ''}`}
                      >
                        <span class="font-mono text-[11px] text-text-muted">{h.memory_id}</span>
                        <Show when={h.type}>
                          <span
                            role="button"
                            tabindex={0}
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/memories?type=${encodeURIComponent(h.type!)}`);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.stopPropagation();
                                navigate(`/memories?type=${encodeURIComponent(h.type!)}`);
                              }
                            }}
                            class="cursor-pointer rounded transition-opacity hover:opacity-80"
                          >
                            <Chip variant="neutral">{h.type}</Chip>
                          </span>
                        </Show>
                        <span class="line-clamp-1 flex-1 text-[12.5px] text-text">
                          {asPreview(h.summary) ?? asPreview(h.title) ?? '—'}
                        </span>
                        <Show when={h.updated_at}>
                          <span class="font-mono text-[11px] text-text-subtle">
                            {formatDate(h.updated_at!)}
                          </span>
                        </Show>
                      </button>
                    </li>
                  )}
                </For>
              </ul>
            </section>
          </Show>
        </Show>
      </Show>
    </Page>
  );
}
