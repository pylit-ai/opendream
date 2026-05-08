import { createEffect, createResource, createSignal, For, on, Show, type JSX } from 'solid-js';
import { useSearchParams } from '@solidjs/router';
import { Clock } from 'lucide-solid';
import { getSessions, getSessionDiagnostics, getSessionTimeline } from '~/api/client';
import type { SessionDiagnostics, SessionRecord, SessionsResponse } from '~/api/types';
import { Chip } from '~/components/Chip';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { FilterBar, type ActiveFilter } from '~/components/FilterBar';
import { SlideOver } from '~/components/SlideOver';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { EmptyState } from '~/components/EmptyState';
import { Tabs } from '~/components/Tabs';
import { formatDate, formatDateLong, formatDuration, formatNumber } from '~/lib/format';
import { IdLink } from '~/components/IdLink';
import { RawFormattedView } from '~/components/RawFormattedView';
import { cachedFetch } from '~/lib/cache';

interface TimelineEvent {
  kind?: string;
  label?: string;
  object_id?: string;
  payload?: { created_at?: string; assembled_text?: string; [k: string]: unknown };
  [k: string]: unknown;
}

function durationOf(r: SessionRecord): string {
  if (!r.started_at || !r.ended_at) return '—';
  const a = Date.parse(r.started_at);
  const b = Date.parse(r.ended_at);
  if (Number.isNaN(a) || Number.isNaN(b)) return '—';
  return formatDuration(Math.max(0, b - a));
}

const SORT_OPTIONS = [
  { value: 'event_count:desc', label: 'Most events' },
  { value: 'started_at:desc', label: 'Newest first' },
  { value: 'started_at:asc', label: 'Oldest first' },
  { value: 'event_count:asc', label: 'Fewest events' },
];

const ORPHAN_SESSION_RE = /^session_[a-f0-9]+$/i;
function countOf(value: unknown): number {
  return typeof value === 'number' ? value : Number(value ?? 0) || 0;
}

function isLikelyOrphan(r: { session_id: string; event_count?: number; context_count?: number }): boolean {
  const ec = countOf(r.event_count);
  const cc = countOf(r.context_count);
  return ec <= 1 && cc === 0 && ORPHAN_SESSION_RE.test(r.session_id);
}

function sessionLabel(r: SessionRecord): string {
  const label = (r as { display_name?: string }).display_name;
  return label && label !== r.session_id ? label : r.session_id;
}

export default function SessionsRoute(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = createSignal((searchParams.search as string) ?? '');
  const [agent, setAgent] = createSignal((searchParams.agent as string) ?? '');
  const [sort, setSort] = createSignal('event_count:desc');
  const [hideOrphans, setHideOrphans] = createSignal(true);
  const [selected, setSelected] = createSignal<SessionRecord | null>(null);
  const [expandedEvent, setExpandedEvent] = createSignal<number | null>(null);
  const initialView: 'list' | 'timeline' =
    (searchParams.view as string) === 'timeline' ? 'timeline' : 'list';
  const [view, setView] = createSignal<'list' | 'timeline'>(initialView);
  createEffect(
    on(view, (v) => {
      const cur = (searchParams.view as string) ?? 'list';
      if (v !== cur) setSearchParams({ view: v === 'list' ? undefined : v }, { replace: true });
    }),
  );

  const [sessions, { refetch }] = createResource<SessionsResponse>(() =>
    cachedFetch('sessions:500', () => getSessions({ limit: 500 }), 15_000),
  );

  const showDiagnostics = () => (searchParams.diagnostics as string) === '1';
  const [diagnostics] = createResource<SessionDiagnostics | null, boolean>(
    showDiagnostics,
    (show: boolean) => (show ? getSessionDiagnostics() : Promise.resolve(null)),
  );

  // URL ↔ state for ?id= and ?agent=
  createEffect(
    on(
      () => [sessions(), searchParams.id] as const,
      ([data, id]) => {
        const wanted = typeof id === 'string' ? id : null;
        if (!wanted) {
          if (selected() !== null && !data) return;
          if (selected() !== null) setSelected(null);
          return;
        }
        const items = (data?.items ?? []) as SessionRecord[];
        const found = items.find((s) => s.session_id === wanted) ?? null;
        if (found && selected()?.session_id !== found.session_id) {
          setSelected(found);
        }
      },
    ),
  );
  createEffect(
    on(
      () => searchParams.agent,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== agent()) setAgent(x);
      },
    ),
  );
  createEffect(
    on(agent, (v) => {
      const cur = (searchParams.agent as string) ?? '';
      if (v !== cur) setSearchParams({ agent: v || undefined }, { replace: true });
    }),
  );

  const openSession = (s: SessionRecord | null): void => {
    setExpandedEvent(null);
    setSelected(s);
    setSearchParams({ id: s?.session_id ?? undefined }, { replace: false });
  };

  const activeFilters = (): ActiveFilter[] => {
    const out: ActiveFilter[] = [];
    if (agent()) {
      const a = agent();
      out.push({ key: 'agent', label: `agent: ${a}`, onRemove: () => setAgent('') });
    }
    return out;
  };

  const filteredItems = (): SessionRecord[] => {
    let list = sessions()?.items ?? [];
    if (hideOrphans()) {
      list = list.filter(
        (r) =>
          !isLikelyOrphan(
            r as unknown as { session_id: string; event_count?: number; context_count?: number },
          ),
      );
    }
    if (agent()) list = list.filter((r) => r.agent_id === agent());
    if (search()) {
      const q = search().toLowerCase();
      list = list.filter(
        (r) =>
          r.session_id.toLowerCase().includes(q) ||
          (r.agent_id ?? '').toLowerCase().includes(q),
      );
    }
    const [field, dir] = sort().split(':');
    list = [...list].sort((a, b) => {
      const key = field ?? 'started_at';
      const av = (a as Record<string, unknown>)[key];
      const bv = (b as Record<string, unknown>)[key];
      if (typeof av === 'number' && typeof bv === 'number') {
        return dir === 'asc' ? av - bv : bv - av;
      }
      const as = String(av ?? '');
      const bs = String(bv ?? '');
      return dir === 'asc' ? as.localeCompare(bs) : bs.localeCompare(as);
    });
    return list;
  };
  const orphanCount = (): number => {
    const list = sessions()?.items ?? [];
    return list.filter((r) =>
      isLikelyOrphan(
        r as unknown as { session_id: string; event_count?: number; context_count?: number },
      ),
    ).length;
  };

  const [timeline] = createResource<TimelineEvent[] | null, SessionRecord | null>(
    selected,
    async (s) => {
      if (!s) return null;
      const embedded = (s as { timeline?: TimelineEvent[] }).timeline;
      if (Array.isArray(embedded) && embedded.length > 0) return embedded;
      try {
        const tl = await cachedFetch(
          `session-timeline:${s.session_id}`,
          () => getSessionTimeline(s.session_id),
          60_000,
        );
        const events = (tl as { timeline?: TimelineEvent[]; events?: TimelineEvent[] }).timeline
          ?? (tl as { events?: TimelineEvent[] }).events
          ?? [];
        return events;
      } catch {
        return embedded ?? [];
      }
    },
  );

  const reportingAgents = (r: SessionRecord): string => {
    const agents = (r as { reporting_agents?: Array<{ agent_label?: string }> }).reporting_agents;
    if (!Array.isArray(agents) || agents.length === 0) return r.agent_id ?? '—';
    return agents.map((a) => a.agent_label ?? '?').join(', ');
  };

  const runCount = (r: SessionRecord): number => {
    const cnt = (r as { run_count?: number; event_count?: number }).run_count
      ?? (r as { event_count?: number }).event_count
      ?? 0;
    return cnt;
  };
  const contextCount = (r: SessionRecord): number => countOf((r as { context_count?: number }).context_count);

  const columns: TableColumn<SessionRecord>[] = [
    {
      key: 'started',
      header: 'Started',
      width: '160px',
      render: (r) =>
        r.started_at ? (
          <span title={formatDateLong(r.started_at)} class="text-text">
            {formatDate(r.started_at)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        ),
    },
    {
      key: 'id',
      header: 'Session',
      width: '320px',
      render: (r) => (
        <div class="flex min-w-0 flex-col gap-1">
          <button
            type="button"
            onClick={() => openSession(r)}
            class="truncate text-left text-xs font-medium text-text hover:text-accent"
            title={sessionLabel(r)}
          >
            {sessionLabel(r)}
          </button>
          <span class="flex items-center gap-1.5">
            <IdLink id={r.session_id} onClick={() => openSession(r)} />
            <Show
              when={countOf((r as { event_count?: number }).event_count) === 0}
            >
              <Chip
                variant={contextCount(r) > 0 ? 'neutral' : 'warn'}
                aria-label={
                  contextCount(r) > 0
                    ? 'Session has assembled context but no explicit emitted events'
                    : 'Session has 0 events — see diagnostics'
                }
              >
                {contextCount(r) > 0 ? 'context' : 'empty'}
              </Chip>
            </Show>
          </span>
        </div>
      ),
    },
    {
      key: 'agent',
      header: 'Agent',
      width: '180px',
      render: (r) => (
        <span class="font-mono text-xs text-text-muted">{reportingAgents(r)}</span>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      width: '100px',
      render: (r) => (
        <span class="font-mono text-xs text-text-muted">{durationOf(r)}</span>
      ),
    },
    {
      key: 'runs',
      header: 'Events',
      width: '80px',
      align: 'right',
      numeric: true,
      render: (r) => (
        <span class="font-mono text-xs text-text-muted">{formatNumber(runCount(r))}</span>
      ),
    },
    {
      key: 'contexts',
      header: 'Contexts',
      width: '90px',
      align: 'right',
      numeric: true,
      render: (r) => (
        <span class="font-mono text-xs text-text-muted">{formatNumber(contextCount(r))}</span>
      ),
    },
  ];

  const renderTimelineEvents = (events: TimelineEvent[]): JSX.Element => (
    <ol class="flex flex-col">
      <For each={events}>
        {(ev, i) => {
          const ts =
            (ev.payload as { created_at?: string } | undefined)?.created_at ??
            (ev as { timestamp?: string }).timestamp;
          const isExpanded = () => expandedEvent() === i();
          return (
            <li class="hairline-b">
              <button
                type="button"
                onClick={() => setExpandedEvent((cur) => (cur === i() ? null : i()))}
                class="row-hover flex w-full items-start gap-3 py-2.5 text-left"
              >
                <div class="mt-1.5 flex-shrink-0">
                  <div class="h-2 w-2 rounded-full bg-accent" />
                </div>
                <div class="flex flex-1 flex-col gap-0.5 min-w-0">
                  <span class="text-[12.5px] font-medium text-text">
                    {ev.label ?? ev.kind ?? 'event'}
                  </span>
                  <Show when={ts}>
                    <span class="text-[11px] text-text-muted">
                      {formatDateLong(ts as string)}
                    </span>
                  </Show>
                  <Show when={ev.kind && ev.kind !== ev.label}>
                    <span class="font-mono text-[10.5px] text-text-subtle">{ev.kind}</span>
                  </Show>
                  <Show when={ev.object_id}>
                    <IdLink id={ev.object_id ?? null} />
                  </Show>
                </div>
                <span class="self-center text-[11px] text-text-subtle">
                  {isExpanded() ? '−' : '+'}
                </span>
              </button>
              <Show when={isExpanded()}>
                <div class="ml-5 mb-2">
                  <RawFormattedView
                    content={JSON.stringify(ev.payload ?? ev, null, 2)}
                    language="json"
                    storageKey="session-event"
                  />
                </div>
              </Show>
            </li>
          );
        }}
      </For>
    </ol>
  );

  const diagnosticsPanel = (): JSX.Element => {
    const d = diagnostics();
    if (!d) return <p class="text-[12.5px] text-text-muted">Loading diagnostics…</p>;
    return (
      <div class="rounded-md border border-border bg-surface-raised p-4 text-[12.5px] flex flex-col gap-3">
        <div class="flex items-center justify-between">
          <span class="font-medium text-text">Session Diagnostics</span>
          <button
            type="button"
            class="text-xs text-text-muted hover:text-text"
            onClick={() => setSearchParams({ diagnostics: undefined }, { replace: true })}
          >
            ✕ close
          </button>
        </div>
        <dl class="grid grid-cols-[200px_1fr] gap-x-3 gap-y-1">
          <dt class="text-text-subtle">Total sessions</dt>
          <dd class="font-mono text-text">{d.total_sessions}</dd>
          <dt class="text-text-subtle">Total events</dt>
          <dd class="font-mono text-text">{d.total_events}</dd>
          <dt class="text-text-subtle">Orphan events</dt>
          <dd class="font-mono text-text">{d.orphan_events_total}</dd>
          <dt class="text-text-subtle">Mismatch records</dt>
          <dd class="font-mono text-text">{d.mismatch_records_total}</dd>
          <dt class="text-text-subtle">Zero-event sessions</dt>
          <dd class="font-mono text-text">{d.zero_event_sessions_total}</dd>
        </dl>
        <Show when={d.orphan_events.length > 0}>
          <div>
            <p class="text-text-subtle mb-1">Orphan event samples:</p>
            <ul class="font-mono text-[11px] text-text-muted flex flex-col gap-0.5">
              <For each={d.orphan_events}>
                {(item) => (
                  <li>event_id={item.event_id} session_id={item.session_id}</li>
                )}
              </For>
            </ul>
          </div>
        </Show>
        <Show when={d.mismatch_records.length > 0}>
          <div>
            <p class="text-text-subtle mb-1">Mismatch record samples:</p>
            <ul class="font-mono text-[11px] text-text-muted flex flex-col gap-0.5">
              <For each={d.mismatch_records}>
                {(item) => (
                  <li>
                    {item.session_id} recorded={item.recorded_event_count} actual=
                    {item.actual_event_count}
                  </li>
                )}
              </For>
            </ul>
          </div>
        </Show>
      </div>
    );
  };

  return (
    <Page title="Sessions" subtitle="Agent session tracking and context assembly timeline">
      <Show when={showDiagnostics()}>{diagnosticsPanel()}</Show>
      <Tabs
        items={[
          { value: 'list', label: 'List' },
          { value: 'timeline', label: 'Timeline' },
        ]}
        value={view()}
        onChange={(v) => setView(v as 'list' | 'timeline')}
      />
      <Show when={view() === 'timeline'}>
        <div class="flex flex-col gap-4">
          <label class="flex flex-col gap-1 text-xs text-text-muted">
            Session
            <select
              value={selected()?.session_id ?? ''}
              onChange={(e) => {
                const v = e.currentTarget.value;
                const list = sessions()?.items ?? [];
                openSession(list.find((s) => s.session_id === v) ?? null);
              }}
              class="h-9 rounded-md border border-border bg-surface px-2 text-sm text-text focus:border-accent focus:outline-none"
            >
              <option value="">— Select session —</option>
              <For each={filteredItems()}>
                {(s) => (
                  <option value={s.session_id}>
                    {sessionLabel(s)} · {reportingAgents(s)} ·{' '}
                    {s.started_at ? formatDate(s.started_at) : ''}
                  </option>
                )}
              </For>
            </select>
          </label>
          <Show when={selected()}>
            {(s) => (
              <div class="flex flex-col gap-4">
                <dl class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                  <dt class="text-text-subtle">Name</dt>
                  <dd class="text-text">{sessionLabel(s())}</dd>
                  <dt class="text-text-subtle">Session ID</dt>
                  <dd class="font-mono text-xs text-text-muted">{s().session_id}</dd>
                  <dt class="text-text-subtle">Started</dt>
                  <dd class="text-text">
                    {s().started_at ? formatDateLong(s().started_at!) : '—'}
                  </dd>
                  <dt class="text-text-subtle">Ended</dt>
                  <dd class="text-text">
                    {s().ended_at ? formatDateLong(s().ended_at!) : '—'}
                  </dd>
                  <dt class="text-text-subtle">Duration</dt>
                  <dd class="font-mono text-text">{durationOf(s())}</dd>
                  <dt class="text-text-subtle">Agent</dt>
                  <dd class="font-mono text-text">{reportingAgents(s())}</dd>
                </dl>
                <Show when={timeline.loading}>
                  <SkeletonRows rows={6} />
                </Show>
                <Show when={!timeline.loading && timeline()}>
                  {(events) => (
                    <Show
                      when={events().length > 0}
                      fallback={
                        <p class="text-[12.5px] text-text-muted">No timeline events recorded for this session. Events appear when the agent assembles memory context.</p>
                      }
                    >
                      <section class="flex flex-col gap-1">
                        <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                          Events · {events().length}
                        </h4>
                        {renderTimelineEvents(events())}
                      </section>
                    </Show>
                  )}
                </Show>
              </div>
            )}
          </Show>
          <Show when={!selected()}>
            <p class="text-sm text-text-muted">
              Pick a session above to see its full timeline.
            </p>
          </Show>
        </div>
      </Show>
      <Show when={view() === 'list'}>
      <FilterBar
        search={search()}
        onSearchChange={setSearch}
        searchPlaceholder="Search sessions"
        sort={sort()}
        onSortChange={setSort}
        sortOptions={SORT_OPTIONS}
        activeFilters={activeFilters()}
        filterForm={
          <div class="flex flex-col gap-3">
            <label class="flex flex-col gap-1 text-xs text-text-muted">
              Agent
              <input
                type="text"
                value={agent()}
                onInput={(e) => setAgent(e.currentTarget.value)}
                placeholder="agent_id"
                class="h-8 rounded-md border border-border bg-surface px-2 text-sm text-text focus:border-accent focus:outline-none"
              />
            </label>
            <label class="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={hideOrphans()}
                onChange={(e) => setHideOrphans(e.currentTarget.checked)}
                class="h-3.5 w-3.5 accent-accent"
              />
              Hide orphan sessions ({orphanCount()})
              <span class="text-text-subtle">
                — fragmented `session_xxx` ids with ≤ 1 event (legacy minter)
              </span>
            </label>
          </div>
        }
      />

      <div class="text-xs text-text-muted">
        <button
          type="button"
          class="underline hover:text-text"
          onClick={() =>
            setSearchParams({ diagnostics: showDiagnostics() ? undefined : '1' }, { replace: true })
          }
        >
          {showDiagnostics() ? 'Hide session diagnostics' : 'View session diagnostics →'}
        </button>
      </div>

      <Show when={!sessions.loading} fallback={<SkeletonRows rows={6} />}>
        <Show
          when={!sessions.error}
          fallback={
            <ErrorState
              message={
                sessions.error instanceof Error ? sessions.error.message : String(sessions.error)
              }
              onRetry={refetch}
            />
          }
        >
          <Table
            items={filteredItems()}
            columns={columns}
            rowKey={(r) => r.session_id}
            onRowClick={(r) => openSession(r)}
            empty={
              <EmptyState
                icon={Clock}
                title="No sessions yet"
                description="Sessions appear when an agent assembles context."
              />
            }
          />
        </Show>
      </Show>

      </Show>
      <SlideOver
        open={view() === 'list' && selected() !== null}
        onOpenChange={(o) => !o && openSession(null)}
        title="Session timeline"
        description={selected()?.session_id}
      >
        <div class="flex flex-col gap-4 p-5">
          <Show when={timeline.loading}>
            <SkeletonRows rows={4} />
          </Show>
          <Show when={selected()}>
            {(s) => (
              <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                <dt class="text-text-subtle">Started</dt>
                <dd class="text-[11.5px] text-text">
                  {s().started_at ? formatDateLong(s().started_at!) : '—'}
                </dd>
                <dt class="text-text-subtle">Ended</dt>
                <dd class="text-[11.5px] text-text">
                  {s().ended_at ? formatDateLong(s().ended_at!) : '—'}
                </dd>
                <dt class="text-text-subtle">Duration</dt>
                <dd class="font-mono text-[11.5px] text-text">{durationOf(s())}</dd>
              </dl>
            )}
          </Show>

          <Show when={!timeline.loading && timeline()}>
            {(events) => (
              <Show
                when={events().length > 0}
                fallback={
                  <p class="text-[12.5px] text-text-muted">No timeline events recorded.</p>
                }
              >
                <section class="flex flex-col gap-1">
                  <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                    Events · {events().length}
                  </h4>
                  {renderTimelineEvents(events())}
                </section>
              </Show>
            )}
          </Show>
        </div>
      </SlideOver>
    </Page>
  );
}
