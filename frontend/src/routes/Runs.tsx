import { createEffect, createResource, createSignal, For, on, Show, type JSX } from 'solid-js';
import { useNavigate, useSearchParams } from '@solidjs/router';
import { PlayCircle } from 'lucide-solid';
import { getMemory, getRun, getRunDiff, getRuns } from '~/api/client';
import type { RunDiff, RunListParams, RunListResponse, RunRecord } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { FilterBar, type ActiveFilter } from '~/components/FilterBar';
import { Chip, type ChipVariant } from '~/components/Chip';
import { SlideOver } from '~/components/SlideOver';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { EmptyState } from '~/components/EmptyState';
import { formatDate, formatDateLong, formatDuration } from '~/lib/format';
import { DiffView } from '~/components/DiffView';
import { IdLink } from '~/components/IdLink';
import { MemoryInspector } from '~/components/MemoryInspector';
import { RawFormattedView } from '~/components/RawFormattedView';
import { cachedFetch, peek } from '~/lib/cache';
import { RUN_KIND_GLOSSARY, helpForRunKind } from '~/lib/observeGlossary';

function asPreview(v: unknown): string | undefined {
  if (v == null) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try { return JSON.stringify(v).slice(0, 240); } catch { return undefined; }
}

function statusVariant(s: string | undefined): ChipVariant {
  const v = (s ?? '').toLowerCase();
  if (v.includes('ok') || v.includes('success') || v.includes('complete')) return 'ok';
  if (v.includes('warn') || v.includes('partial')) return 'warn';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

function durationOf(r: RunRecord): string {
  if (!r.started_at || !r.ended_at) return '—';
  const a = Date.parse(r.started_at);
  const b = Date.parse(r.ended_at);
  if (Number.isNaN(a) || Number.isNaN(b)) return '—';
  return formatDuration(Math.max(0, b - a));
}

interface RunOperation {
  kind?: string;
  type?: string;
  memory_id?: string;
  object_id?: string;
  summary?: string;
  [k: string]: unknown;
}

const SORT_OPTIONS = [
  { value: 'started_at:desc', label: 'Newest first' },
  { value: 'started_at:asc', label: 'Oldest first' },
  { value: 'agent_id:asc', label: 'Agent A→Z' },
];

export default function RunsRoute(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [search, setSearch] = createSignal((searchParams.search as string) ?? '');
  const [agent, setAgent] = createSignal((searchParams.agent as string) ?? '');
  const [statusFilter, setStatusFilter] = createSignal((searchParams.status as string) ?? '');
  const [kindFilter, setKindFilter] = createSignal((searchParams.kind as string) ?? '');
  const [sort, setSort] = createSignal('started_at:desc');
  const [selectedRunId, setSelectedRunId] = createSignal<string | null>(
    (searchParams.id as string) ?? null,
  );
  const [memoryFocus, setMemoryFocus] = createSignal<string | null>(null);

  // URL → state for ?id=, ?agent=, ?status=, ?kind=, ?search=
  createEffect(
    on(
      () => searchParams.id,
      (v) => {
        const id = typeof v === 'string' ? v : null;
        if (id !== selectedRunId()) setSelectedRunId(id);
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
    on(
      () => searchParams.status,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== statusFilter()) setStatusFilter(x);
      },
    ),
  );
  createEffect(
    on(
      () => searchParams.kind,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== kindFilter()) setKindFilter(x);
      },
    ),
  );
  // state → URL: only sync agent / status / kind / search; id is set via row clicks.
  createEffect(
    on(agent, (v) => {
      const cur = (searchParams.agent as string) ?? '';
      if (v !== cur) setSearchParams({ agent: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(statusFilter, (v) => {
      const cur = (searchParams.status as string) ?? '';
      if (v !== cur) setSearchParams({ status: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(kindFilter, (v) => {
      const cur = (searchParams.kind as string) ?? '';
      if (v !== cur) setSearchParams({ kind: v || undefined }, { replace: true });
    }),
  );

  const openRun = (id: string | null): void => {
    setSelectedRunId(id);
    setSearchParams({ id: id ?? undefined }, { replace: false });
  };
  void navigate;

  const params = (): RunListParams => {
    const [field, dir] = sort().split(':');
    const out: RunListParams = { limit: 50 };
    if (search()) out.search = search();
    if (field) out.sort = field;
    if (dir === 'asc' || dir === 'desc') out.sort_dir = dir;
    return out;
  };

  const [runs, { refetch }] = createResource<RunListResponse, RunListParams>(
    params,
    (p) => cachedFetch(`runs:${JSON.stringify(p)}`, () => getRuns(p), 15_000),
  );

  const [detail] = createResource<
    { run: RunRecord; diff: RunDiff | null } | null,
    string | null
  >(selectedRunId, async (id) => {
    if (!id) return null;
    const [run, diff] = await Promise.all([
      cachedFetch(`run:${id}`, () => getRun(id), 60_000),
      cachedFetch(`run-diff:${id}`, () => getRunDiff(id), 60_000).catch(() => null),
    ]);
    return { run: run as RunRecord, diff: diff as RunDiff | null };
  });

  const activeFilters = (): ActiveFilter[] => {
    const out: ActiveFilter[] = [];
    if (agent()) {
      const a = agent();
      out.push({ key: 'agent', label: `agent: ${a}`, onRemove: () => setAgent('') });
    }
    if (statusFilter()) {
      const s = statusFilter();
      out.push({ key: 'status', label: `status: ${s}`, onRemove: () => setStatusFilter('') });
    }
    if (kindFilter()) {
      const k = kindFilter();
      out.push({ key: 'kind', label: `kind: ${k}`, onRemove: () => setKindFilter('') });
    }
    return out;
  };

  const filteredItems = (): RunRecord[] => {
    let list = runs()?.items ?? [];
    if (agent()) list = list.filter((r) => r.agent_id === agent());
    if (statusFilter()) {
      const s = statusFilter().toLowerCase();
      list = list.filter((r) => (r.status ?? '').toLowerCase() === s);
    }
    if (kindFilter()) {
      const k = kindFilter().toLowerCase();
      list = list.filter((r) => {
        const rk = ((r as { kind?: string }).kind ?? (r as { type?: string }).type ?? '').toLowerCase();
        return rk === k;
      });
    }
    return list;
  };

  const columns: TableColumn<RunRecord>[] = [
    {
      key: 'started',
      header: 'Started',
      width: '150px',
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
      header: 'Run',
      width: '170px',
      render: (r) => (
        <IdLink
          id={r.run_id}
          preview={asPreview(r.summary)}
          onClick={() => openRun(r.run_id)}
          onHover={() => {
            void cachedFetch(`run:${r.run_id}`, () => getRun(r.run_id), 60_000);
            void cachedFetch(`run-diff:${r.run_id}`, () => getRunDiff(r.run_id), 60_000).catch(
              () => null,
            );
          }}
        />
      ),
    },
    {
      key: 'kind',
      header: 'Kind',
      width: '120px',
      render: (r) => {
        const k = (r as { kind?: string; type?: string }).kind ??
          (r as { type?: string }).type ??
          'run';
        const help = helpForRunKind(k);
        return (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setKindFilter(k);
            }}
            class="cursor-pointer rounded px-1 -mx-1 font-mono text-xs text-text-muted transition-colors hover:bg-[color-mix(in_oklab,rgb(var(--c-accent))_8%,transparent)] hover:text-accent"
            title={`Filter by kind: ${k}. ${help}`}
          >
            {k}
          </button>
        );
      },
    },
    {
      key: 'agent',
      header: 'Agent',
      width: '140px',
      render: (r) => (
        <Show
          when={r.agent_id}
          fallback={<span class="font-mono text-xs text-text-muted">—</span>}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setAgent(r.agent_id!);
            }}
            class="cursor-pointer rounded px-1 -mx-1 font-mono text-xs text-text-muted transition-colors hover:bg-[color-mix(in_oklab,rgb(var(--c-accent))_8%,transparent)] hover:text-accent"
            title={`Filter by agent: ${r.agent_id}`}
          >
            {r.agent_id}
          </button>
        </Show>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '100px',
      render: (r) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (r.status) setStatusFilter(r.status);
          }}
          class="cursor-pointer rounded transition-opacity hover:opacity-80"
          title={`Filter by status: ${r.status ?? 'unknown'}`}
        >
          <Chip variant={statusVariant(r.status)}>{r.status ?? 'unknown'}</Chip>
        </button>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      width: '100px',
      align: 'right',
      numeric: true,
      render: (r) => <span class="font-mono text-xs text-text-muted">{durationOf(r)}</span>,
    },
  ];

  return (
    <Page title="Runs" subtitle="Runtime activity log: consolidation jobs, dream cycles, and automation projections">
      <FilterBar
        search={search()}
        onSearchChange={setSearch}
        searchPlaceholder="Search runs"
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
          </div>
        }
      />

      <section class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text-muted">
        <div class="flex flex-col gap-2">
          <p>
            <span class="font-medium text-text">Runs are the audit log.</span>{' '}
            A consolidation row means OpenDream processed memory inputs. Dream cycles are a smaller subset; use the Dreams page when you only want dream outcomes.
          </p>
          <details>
            <summary class="cursor-pointer font-medium text-text">Run kind glossary</summary>
            <div class="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <For each={RUN_KIND_GLOSSARY}>
                {(entry) => (
                  <div class="rounded bg-surface-elevated/60 px-2 py-1.5">
                    <div class="font-mono text-[10.5px] text-text" title={entry.help}>{entry.key}</div>
                    <div>{entry.help}</div>
                  </div>
                )}
              </For>
            </div>
          </details>
        </div>
      </section>

      <Show when={!runs.loading} fallback={<SkeletonRows rows={8} />}>
        <Show
          when={!runs.error}
          fallback={
            <ErrorState
              message={runs.error instanceof Error ? runs.error.message : String(runs.error)}
              onRetry={refetch}
            />
          }
        >
          <Table
            items={filteredItems()}
            columns={columns}
            rowKey={(r) => r.run_id}
            onRowClick={(r) => openRun(r.run_id)}
            empty={
              <EmptyState
                icon={PlayCircle}
                title="No runs yet"
                description="They'll appear here as your agents work."
              />
            }
          />
        </Show>
      </Show>

      <SlideOver
        open={selectedRunId() !== null}
        onOpenChange={(o) => !o && openRun(null)}
        title="Run inspector"
        description={selectedRunId() ?? undefined}
      >
        <div class="flex flex-col gap-4 p-5">
          <Show when={detail.loading}>
            <SkeletonRows rows={4} />
          </Show>
          <Show when={detail()}>
            {(d) => {
              const run = d().run;
              const ops = ((run as { operations?: RunOperation[] }).operations ?? []) as RunOperation[];
              const memOps = ops.filter((op) => op.memory_id ?? op.object_id);
              const phaseTraces = ((run as { phase_traces?: unknown[] }).phase_traces ?? []) as unknown[];
              return (
                <>
                  <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                    <dt class="text-text-subtle">Status</dt>
                    <dd>
                      <Chip variant={statusVariant(run.status)}>{run.status ?? 'unknown'}</Chip>
                    </dd>
                    <dt class="text-text-subtle">Kind</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {(run as { kind?: string; type?: string }).kind ??
                        (run as { type?: string }).type ??
                        '—'}
                    </dd>
                    <dt class="text-text-subtle">Agent</dt>
                    <dd class="font-mono text-[11.5px] text-text">{run.agent_id ?? '—'}</dd>
                    <dt class="text-text-subtle">Started</dt>
                    <dd class="text-[11.5px] text-text">
                      {run.started_at ? formatDateLong(run.started_at) : '—'}
                    </dd>
                    <dt class="text-text-subtle">Ended</dt>
                    <dd class="text-[11.5px] text-text">
                      {run.ended_at ? formatDateLong(run.ended_at) : '—'}
                    </dd>
                    <dt class="text-text-subtle">Duration</dt>
                    <dd class="font-mono text-[11.5px] text-text">{durationOf(run)}</dd>
                  </dl>

                  <Show when={asPreview(run.summary)}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Summary
                      </h4>
                      <RawFormattedView
                        content={asPreview(run.summary) ?? ''}
                        language="auto"
                        storageKey="run-summary"
                      />
                    </section>
                  </Show>

                  <Show when={(run as { error?: string }).error}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Error
                      </h4>
                      <RawFormattedView
                        content={(run as { error?: string }).error ?? ''}
                        language="text"
                        storageKey="run-error"
                      />
                    </section>
                  </Show>

                  <Show when={phaseTraces.length > 0}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Phase timeline · {phaseTraces.length}
                      </h4>
                      <ol class="flex flex-col">
                        <For each={phaseTraces}>
                          {(p, i) => {
                            const ph = p as {
                              phase?: string;
                              name?: string;
                              status?: string;
                              started_at?: string;
                              ended_at?: string;
                              duration_ms?: number;
                              summary?: string;
                            };
                            const label = ph.phase ?? ph.name ?? `phase ${i() + 1}`;
                            const dur =
                              typeof ph.duration_ms === 'number'
                                ? formatDuration(ph.duration_ms)
                                : durationOf({ started_at: ph.started_at, ended_at: ph.ended_at } as RunRecord);
                            return (
                              <li class="hairline-b flex items-start gap-3 py-2">
                                <div class="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-accent" />
                                <div class="flex flex-1 flex-col gap-0.5 min-w-0">
                                  <div class="flex items-center gap-2">
                                    <span class="text-[12.5px] font-medium text-text">{label}</span>
                                    <Show when={ph.status}>
                                      <Chip variant={statusVariant(ph.status)}>{ph.status}</Chip>
                                    </Show>
                                  </div>
                                  <Show when={ph.started_at}>
                                    <span class="font-mono text-[11px] text-text-subtle">
                                      {formatDateLong(ph.started_at!)}
                                    </span>
                                  </Show>
                                  <Show when={asPreview(ph.summary)}>
                                    <span class="text-[11.5px] text-text-muted">{asPreview(ph.summary)}</span>
                                  </Show>
                                </div>
                                <span class="font-mono text-[11px] tabular-nums text-text-muted">
                                  {dur ?? '—'}
                                </span>
                              </li>
                            );
                          }}
                        </For>
                      </ol>
                    </section>
                  </Show>

                  <Show when={memOps.length > 0}>
                    <section class="flex flex-col gap-1.5">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Memory operations · {memOps.length}
                      </h4>
                      <div class="flex flex-col gap-1">
                        <For each={memOps.slice(0, 30)}>
                          {(op) => {
                            const memId = (op.memory_id ?? op.object_id) as string | undefined;
                            const cached = memId
                              ? (peek(`memory:${memId}`) as
                                  | { title?: string; summary?: string }
                                  | undefined)
                              : undefined;
                            const [hydrated] = createResource<
                              { title?: string; summary?: string } | null
                            >(async () => {
                              if (!memId || cached) return null;
                              return (await cachedFetch(
                                `memory:${memId}`,
                                () => getMemory(memId),
                                60_000,
                              ).catch(() => null)) as
                                | { title?: string; summary?: string }
                                | null;
                            });
                            const meta = (): { title?: string; summary?: string } =>
                              cached ?? hydrated() ?? {};
                            const fallbackText = (): string =>
                              op.summary ?? meta().title ?? meta().summary ?? '';
                            return (
                              <div class="flex items-center gap-2 rounded-md hairline px-2.5 py-1.5">
                                <span class="text-[10px] uppercase tracking-[0.06em] text-text-subtle min-w-[60px]">
                                  {op.kind ?? op.type ?? 'op'}
                                </span>
                                <Show when={memId}>
                                  <IdLink
                                    id={memId!}
                                    onClick={() => setMemoryFocus(memId!)}
                                    onHover={() => {
                                      void cachedFetch(
                                        `memory:${memId}`,
                                        () => getMemory(memId!),
                                        60_000,
                                      );
                                    }}
                                  />
                                </Show>
                                <Show when={fallbackText()}>
                                  <span class="line-clamp-1 flex-1 text-[12px] text-text-muted">
                                    {fallbackText()}
                                  </span>
                                </Show>
                              </div>
                            );
                          }}
                        </For>
                      </div>
                    </section>
                  </Show>

                  <Show when={d().diff?.diff_text}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Diff
                      </h4>
                      <DiffView patch={d().diff!.diff_text} language="text" />
                    </section>
                  </Show>

                  <section class="flex flex-col gap-1">
                    <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                      Raw run
                    </h4>
                    <RawFormattedView
                      content={JSON.stringify(run, null, 2)}
                      language="json"
                      storageKey="run-raw"
                      defaultMode="raw"
                    />
                  </section>
                </>
              );
            }}
          </Show>
        </div>
      </SlideOver>

      <SlideOver
        open={memoryFocus() !== null}
        onOpenChange={(o) => !o && setMemoryFocus(null)}
        title="Memory inspector"
        description={memoryFocus() ?? undefined}
      >
        <Show when={memoryFocus()}>
          {(id) => <MemoryInspector memoryId={id()} onNavigate={(next) => setMemoryFocus(next)} />}
        </Show>
      </SlideOver>
    </Page>
  );
}
