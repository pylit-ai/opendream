import { createEffect, createResource, createSignal, For, on, Show, type JSX } from 'solid-js';
import { useLocation, useNavigate, useSearchParams } from '@solidjs/router';
import { Database } from 'lucide-solid';
import {
  getDreamCycles,
  getMemories,
  getMemory,
  getOverview,
} from '~/api/client';
import type {
  DreamCycle,
  MemoryListParams,
  MemoryListResponse,
  MemoryRecord,
  OverviewPayload,
} from '~/api/types';
import { Page } from '~/components/Page';
import { Tabs } from '~/components/Tabs';
import { Table, type TableColumn } from '~/components/Table';
import { FilterBar } from '~/components/FilterBar';
import { Chip, type ChipVariant } from '~/components/Chip';
import { SlideOver } from '~/components/SlideOver';
import { SkeletonRows, SkeletonStats } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { EmptyState } from '~/components/EmptyState';
import { formatDate, formatDateLong } from '~/lib/format';
import { MemoryInspector } from '~/components/MemoryInspector';
import { IdLink } from '~/components/IdLink';
import { cachedFetch } from '~/lib/cache';

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

const TAB_ITEMS = [
  { value: '/memories', label: 'Surface' },
  { value: '/memories/explorer', label: 'Explorer' },
  { value: '/memories/changes', label: 'Changes' },
];

function statusVariant(s: string | undefined): ChipVariant {
  const v = (s ?? '').toLowerCase();
  if (v.includes('durable') || v.includes('active')) return 'ok';
  if (v.includes('contested') || v.includes('learned')) return 'warn';
  if (v.includes('pruned') || v.includes('rejected')) return 'danger';
  return 'neutral';
}

function memoryColumns(onSelect: (id: string) => void): TableColumn<MemoryRecord>[] {
  return [
    {
      key: 'id',
      header: 'ID',
      width: '170px',
      render: (m) => (
        <IdLink
          id={m.memory_id}
          preview={asPreview(m.summary)}
          onClick={() => onSelect(m.memory_id)}
          onHover={() => {
            void cachedFetch(`memory:${m.memory_id}`, () => getMemory(m.memory_id), 60_000);
          }}
        />
      ),
    },
    {
      key: 'type',
      header: 'Type',
      width: '110px',
      render: (m) => <span class="text-xs text-text">{m.type ?? '—'}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      width: '110px',
      render: (m) => <Chip variant={statusVariant(m.status)}>{m.status ?? 'unknown'}</Chip>,
    },
    {
      key: 'preview',
      header: 'Summary / preview',
      render: (m) => {
        const text = asPreview(m.summary) ?? asPreview(m.body) ?? '—';
        return <span class="line-clamp-1 text-[12.5px] text-text">{text}</span>;
      },
    },
    {
      key: 'agent',
      header: 'Agent',
      width: '120px',
      render: (m) => (
        <span class="font-mono text-2xs text-text-muted">{m.agent_id ?? '—'}</span>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      width: '120px',
      render: (m) =>
        m.updated_at ? (
          <span title={formatDateLong(m.updated_at)} class="text-2xs text-text-muted">
            {formatDate(m.updated_at)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        ),
    },
  ];
}

interface MemorySurfacePayload extends OverviewPayload {
  memory_counts?: {
    total?: number;
    by_status?: Record<string, number>;
    by_type?: Record<string, number>;
    by_scope?: Record<string, number>;
  };
  memory_surface?: {
    durable_active_total?: number;
    durable_contested_total?: number;
    learned_context_active_total?: number;
    learned_context_recently_pruned_total?: number;
    low_signal_share?: number;
    recent_highlights?: Array<{
      memory_id?: string;
      title?: string;
      summary?: string;
      type?: string;
      status?: string;
      updated_at?: string;
    }>;
    type_mix?: Record<string, number>;
  };
}

const STATUS_ORDER = ['active', 'contested', 'learned', 'pruned', 'rejected', 'archived'];

const STATUS_COPY: Record<string, { label: string; tone: ChipVariant; help: string }> = {
  active: { label: 'Active', tone: 'ok', help: 'Durable memories trusted by the runtime.' },
  contested: {
    label: 'Contested',
    tone: 'warn',
    help: 'Memories with conflicting evidence — review or let auto-reviewer decide.',
  },
  learned: { label: 'Learned', tone: 'warn', help: 'Per-context learnings the runtime is still trying out.' },
  pruned: { label: 'Pruned', tone: 'danger', help: 'Removed during a recent prune cycle (reversible).' },
  rejected: { label: 'Rejected', tone: 'danger', help: 'Operator-suppressed; will not surface in retrievals.' },
  archived: { label: 'Archived', tone: 'neutral', help: 'Inactive but retained for forensic review.' },
};

function SurfaceDashboard(): JSX.Element {
  const navigate = useNavigate();
  const [ov] = createResource<MemorySurfacePayload>(() =>
    cachedFetch('overview', getOverview, 15_000),
  );

  const counts = (): NonNullable<MemorySurfacePayload['memory_counts']> =>
    ov()?.memory_counts ?? {};
  const surface = (): NonNullable<MemorySurfacePayload['memory_surface']> =>
    ov()?.memory_surface ?? {};
  const total = (): number => counts().total ?? 0;

  const statusEntries = (): Array<[string, number]> => {
    const m: Record<string, number> = counts().by_status ?? {};
    const seen = new Set<string>();
    const out: Array<[string, number]> = [];
    for (const key of STATUS_ORDER) {
      if (key in m) {
        out.push([key, m[key]!]);
        seen.add(key);
      }
    }
    for (const [k, v] of Object.entries(m)) {
      if (!seen.has(k)) out.push([k, v as number]);
    }
    return out;
  };

  const typeEntries = (): Array<[string, number]> => {
    const tm = surface().type_mix;
    const mix: Record<string, number> =
      tm && Object.keys(tm).length > 0 ? tm : counts().by_type ?? {};
    const list = Object.entries(mix).sort((a, b) => b[1] - a[1]);
    return list as Array<[string, number]>;
  };
  const typeMax = (): number => Math.max(1, ...typeEntries().map(([, v]) => v));

  const lowSignalPct = (): number | null => {
    const v = surface().low_signal_share;
    if (typeof v !== 'number') return null;
    return Math.round((v <= 1 ? v * 100 : v) * 10) / 10;
  };

  type Highlight = NonNullable<
    NonNullable<MemorySurfacePayload['memory_surface']>['recent_highlights']
  >[number];
  const recent = (): Highlight[] => (surface().recent_highlights ?? []) as Highlight[];

  return (
    <Show when={!ov.loading} fallback={<SkeletonStats />}>
      <Show
        when={!ov.error}
        fallback={
          <ErrorState
            message={ov.error instanceof Error ? ov.error.message : String(ov.error)}
          />
        }
      >
        <div class="flex flex-col gap-4">
          {/* Totals strip */}
          <section class="flex flex-wrap items-stretch gap-x-6 gap-y-2 rounded-md hairline bg-surface px-4 py-2.5">
            <CompactStat
              label="Total"
              value={String(total())}
            />
            <CompactStat
              label="Durable active"
              value={String(surface().durable_active_total ?? 0)}
              tone="ok"
            />
            <CompactStat
              label="Contested"
              value={String(surface().durable_contested_total ?? 0)}
              tone={(surface().durable_contested_total ?? 0) > 0 ? 'warn' : 'default'}
            />
            <CompactStat
              label="Learned (live)"
              value={String(surface().learned_context_active_total ?? 0)}
            />
            <CompactStat
              label="Recently pruned"
              value={String(surface().learned_context_recently_pruned_total ?? 0)}
            />
            <Show when={lowSignalPct() !== null}>
              <CompactStat
                label="Low-signal share"
                value={`${lowSignalPct()}%`}
                tone={(lowSignalPct() ?? 0) > 30 ? 'warn' : 'default'}
              />
            </Show>
          </section>

          <section class="grid gap-3 lg:grid-cols-[1fr_1.4fr]">
            {/* Status distribution */}
            <div class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
              <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">By status</div>
              <p class="text-[11px] text-text-muted">
                Click a row to filter the Explorer. Tones map: green = healthy, yellow = needs
                review, red = suppressed.
              </p>
              <div class="flex flex-col gap-1">
                <For each={statusEntries()}>
                  {([k, v]) => {
                    const meta = STATUS_COPY[k] ?? { label: k, tone: 'neutral' as ChipVariant, help: '' };
                    const pct = total() > 0 ? Math.round((v / total()) * 100) : 0;
                    return (
                      <button
                        type="button"
                        onClick={() => navigate(`/memories/explorer?status=${encodeURIComponent(k)}`)}
                        class="row-hover grid grid-cols-[110px_1fr_60px] items-center gap-3 rounded px-1 py-1 text-left"
                        title={meta.help}
                      >
                        <span class="flex items-center gap-2">
                          <Chip variant={meta.tone}>{meta.label}</Chip>
                        </span>
                        <span class="relative h-3 overflow-hidden rounded-sm bg-surface-elevated">
                          <span
                            class="absolute inset-y-0 left-0"
                            style={{
                              width: `${(v / Math.max(total(), 1)) * 100}%`,
                              'background-color':
                                meta.tone === 'ok'
                                  ? 'rgb(var(--c-success))'
                                  : meta.tone === 'warn'
                                    ? 'rgb(var(--c-warn))'
                                    : meta.tone === 'danger'
                                      ? 'rgb(var(--c-danger))'
                                      : 'rgb(var(--c-accent))',
                              opacity: 0.7,
                            }}
                          />
                        </span>
                        <span class="text-right font-mono text-[11px] text-text">
                          {v} <span class="text-text-subtle">· {pct}%</span>
                        </span>
                      </button>
                    );
                  }}
                </For>
              </div>
            </div>

            {/* Type mix */}
            <div class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
              <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                Top types · {typeEntries().length} of {Object.keys(counts().by_type ?? {}).length}
              </div>
              <Show
                when={typeEntries().length > 0}
                fallback={<p class="text-[11px] text-text-muted">No type breakdown available.</p>}
              >
                <div class="flex flex-col gap-1">
                  <For each={typeEntries()}>
                    {([k, v]) => (
                      <button
                        type="button"
                        onClick={() => navigate(`/memories/explorer?type=${encodeURIComponent(k)}`)}
                        class="row-hover grid grid-cols-[180px_1fr_50px] items-center gap-3 rounded px-1 py-1 text-left"
                        title={`Filter Explorer by type=${k}`}
                      >
                        <span class="truncate font-mono text-[11px] text-text">{k}</span>
                        <span class="relative h-3 overflow-hidden rounded-sm bg-surface-elevated">
                          <span
                            class="absolute inset-y-0 left-0 bg-accent"
                            style={{ width: `${(v / typeMax()) * 100}%`, opacity: 0.7 }}
                          />
                        </span>
                        <span class="text-right font-mono text-[11px] text-text">{v}</span>
                      </button>
                    )}
                  </For>
                </div>
              </Show>
            </div>
          </section>

          {/* Recent highlights */}
          <section class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
            <div class="flex items-baseline justify-between">
              <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                Recent highlights · {recent().length}
              </div>
              <button
                type="button"
                onClick={() => navigate('/memories/explorer')}
                class="text-[10px] text-accent hover:underline"
              >
                Open Explorer →
              </button>
            </div>
            <Show
              when={recent().length > 0}
              fallback={<p class="text-[11px] text-text-muted">No recently updated memories.</p>}
            >
              <ul class="flex flex-col">
                <For each={recent().slice(0, 8)}>
                  {(h) => (
                    <li>
                      <button
                        type="button"
                        onClick={() =>
                          h.memory_id &&
                          navigate(`/memories/explorer?id=${encodeURIComponent(h.memory_id)}`)
                        }
                        class="row-hover hairline-b grid w-full grid-cols-[170px_1fr_100px] items-center gap-3 px-1 py-1.5 text-left"
                        title={asPreview(h.summary) ?? asPreview(h.title) ?? h.memory_id}
                      >
                        <span class="font-mono text-[10.5px] text-text-subtle">
                          {h.memory_id ?? '—'}
                        </span>
                        <span class="line-clamp-1 text-[12px] text-text">
                          {h.title ?? h.summary ?? '—'}
                        </span>
                        <span class="text-right">
                          <Show when={h.type}>
                            <Chip variant="neutral">{h.type}</Chip>
                          </Show>
                        </span>
                      </button>
                    </li>
                  )}
                </For>
              </ul>
            </Show>
          </section>
        </div>
      </Show>
    </Show>
  );
}

function CompactStat(props: {
  label: string;
  value: string | number;
  tone?: 'ok' | 'warn' | 'danger' | 'default';
}): JSX.Element {
  const tone =
    props.tone === 'ok'
      ? 'text-success'
      : props.tone === 'warn'
        ? 'text-warn'
        : props.tone === 'danger'
          ? 'text-danger'
          : 'text-text';
  return (
    <div class="flex flex-col leading-tight">
      <span class="text-[9.5px] uppercase tracking-[0.08em] text-text-subtle">{props.label}</span>
      <span class={`font-mono text-[14px] ${tone}`}>{props.value}</span>
    </div>
  );
}

function MemoriesTable(props: {
  search: string;
  onSearchChange: (v: string) => void;
  pageSize: number;
  statusFilter?: string;
  typeFilter?: string;
}): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedId, setSelectedId] = createSignal<string | null>(
    (searchParams.id as string) ?? null,
  );
  createEffect(
    on(
      () => searchParams.id,
      (v) => {
        const id = typeof v === 'string' ? v : null;
        if (id !== selectedId()) setSelectedId(id);
      },
    ),
  );
  const openMemory = (id: string | null): void => {
    setSelectedId(id);
    setSearchParams({ id: id ?? undefined }, { replace: false });
  };
  const params = (): MemoryListParams => {
    const out: MemoryListParams = { limit: props.pageSize };
    if (props.search) out.search = props.search;
    if (props.statusFilter) out.status = props.statusFilter;
    if (props.typeFilter) out.type = props.typeFilter;
    return out;
  };
  const [resp, { refetch }] = createResource<MemoryListResponse, MemoryListParams>(
    params,
    (p) => cachedFetch(`memories:${JSON.stringify(p)}`, () => getMemories(p), 15_000),
  );

  return (
    <>
      <Show when={!resp.loading} fallback={<SkeletonRows rows={6} />}>
        <Show
          when={!resp.error}
          fallback={
            <ErrorState
              message={resp.error instanceof Error ? resp.error.message : String(resp.error)}
              onRetry={refetch}
            />
          }
        >
          <Table
            items={(resp()?.items ?? []).filter((m) => {
              if (props.statusFilter) {
                const s = (m.status ?? '').toLowerCase();
                if (s !== props.statusFilter.toLowerCase()) return false;
              }
              if (props.typeFilter) {
                const t = (m.type ?? '').toLowerCase();
                if (t !== props.typeFilter.toLowerCase()) return false;
              }
              return true;
            })}
            columns={memoryColumns(openMemory)}
            rowKey={(m) => m.memory_id}
            onRowClick={(m) => openMemory(m.memory_id)}
            empty={
              <EmptyState
                icon={Database}
                title="No memories yet"
                description="They'll appear here as captures are processed."
              />
            }
          />
        </Show>
      </Show>

      <SlideOver
        open={selectedId() !== null}
        onOpenChange={(o) => !o && openMemory(null)}
        title="Memory inspector"
        description={selectedId() ?? undefined}
      >
        <Show when={selectedId()}>
          {(id) => (
            <MemoryInspector memoryId={id()} onNavigate={(next) => openMemory(next)} />
          )}
        </Show>
      </SlideOver>
    </>
  );
}

export function MemoriesSurface(): JSX.Element {
  return (
    <MemoriesShell>
      <SurfaceDashboard />
    </MemoriesShell>
  );
}

const STATUS_OPTIONS = ['', 'active', 'contested', 'learned', 'pruned', 'rejected'] as const;

export function MemoriesExplorer(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = createSignal((searchParams.search as string) ?? '');
  const [typeInput, setTypeInput] = createSignal((searchParams.type as string) ?? '');
  const [statusInput, setStatusInput] = createSignal((searchParams.status as string) ?? '');
  const statusFilter = (): string => (searchParams.status as string) ?? '';
  const typeFilter = (): string => (searchParams.type as string) ?? '';
  createEffect(
    on(search, (v) => {
      const cur = (searchParams.search as string) ?? '';
      if (v !== cur) setSearchParams({ search: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(typeInput, (v) => {
      const cur = (searchParams.type as string) ?? '';
      if (v !== cur) setSearchParams({ type: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(statusInput, (v) => {
      const cur = (searchParams.status as string) ?? '';
      if (v !== cur) setSearchParams({ status: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(
      () => searchParams.type,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== typeInput()) setTypeInput(x);
      },
    ),
  );
  createEffect(
    on(
      () => searchParams.status,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== statusInput()) setStatusInput(x);
      },
    ),
  );

  const activeFilters = () => {
    const out: Array<{ key: string; label: string; onRemove: () => void }> = [];
    if (typeInput()) out.push({ key: 'type', label: `type: ${typeInput()}`, onRemove: () => setTypeInput('') });
    if (statusInput())
      out.push({ key: 'status', label: `status: ${statusInput()}`, onRemove: () => setStatusInput('') });
    return out;
  };

  return (
    <MemoriesShell>
      <div class="flex flex-col gap-4">
        <FilterBar
          search={search()}
          onSearchChange={setSearch}
          searchPlaceholder="Search memories"
          activeFilters={activeFilters()}
          filterForm={
            <div class="flex flex-col gap-3">
              <label class="flex flex-col gap-1 text-xs text-text-muted">
                Type
                <input
                  type="text"
                  value={typeInput()}
                  onInput={(e) => setTypeInput(e.currentTarget.value)}
                  placeholder="e.g. preference"
                  class="h-8 rounded-md border border-border bg-surface px-2 text-sm text-text focus:border-accent focus:outline-none"
                />
              </label>
              <label class="flex flex-col gap-1 text-xs text-text-muted">
                Status
                <select
                  value={statusInput()}
                  onChange={(e) => setStatusInput(e.currentTarget.value)}
                  class="h-8 rounded-md border border-border bg-surface px-2 text-sm text-text focus:border-accent focus:outline-none"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option value={s}>{s || 'any'}</option>
                  ))}
                </select>
              </label>
            </div>
          }
        />
        <MemoriesTable
          search={search()}
          onSearchChange={setSearch}
          pageSize={100}
          statusFilter={statusFilter()}
          typeFilter={typeFilter()}
        />
      </div>
    </MemoriesShell>
  );
}

export function MemoriesChanges(): JSX.Element {
  // Spec 448: Memory changes are produced by dream cycles. The legacy
  // /api/semantic-changes/latest endpoint only returns one context's review;
  // the actual stream of "what changed in memory" is the dream cycle list,
  // filtered to cycles whose learned-context delta is non-zero. Each row
  // links into the Dreams cycle detail.
  const navigate = useNavigate();
  const [cycles, { refetch }] = createResource(() =>
    cachedFetch('dream-cycles', () => getDreamCycles({ limit: 200 }), 15_000),
  );

  const allCycles = (): DreamCycle[] => cycles()?.items ?? [];
  const changedCycles = (): DreamCycle[] =>
    allCycles().filter((c) => {
      const created = c.learned_context_created ?? 0;
      const superseded = c.learned_context_superseded ?? 0;
      const approved = c.proposals_approved ?? 0;
      return created > 0 || superseded > 0 || approved > 0;
    });
  const noopCycles = (): DreamCycle[] =>
    allCycles().filter((c) => {
      const created = c.learned_context_created ?? 0;
      const superseded = c.learned_context_superseded ?? 0;
      const approved = c.proposals_approved ?? 0;
      return created === 0 && superseded === 0 && approved === 0;
    });

  const cycleColumns: TableColumn<DreamCycle>[] = [
    {
      key: 'when',
      header: 'When',
      width: '140px',
      render: (c) =>
        c.started_at ? (
          <span title={formatDateLong(c.started_at)} class="text-xs text-text">
            {formatDate(c.started_at)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        ),
    },
    {
      key: 'narrative',
      header: 'Narrative',
      render: (c) => (
        <span class="line-clamp-1 text-[12.5px] text-text" title={c.narrative ?? c.run_id}>
          {c.narrative ?? '(no narrative)'}
        </span>
      ),
    },
    {
      key: 'created',
      header: 'Created',
      width: '80px',
      align: 'right',
      numeric: true,
      render: (c) => (
        <span class="font-mono text-[11px] text-success">+{c.learned_context_created ?? 0}</span>
      ),
    },
    {
      key: 'superseded',
      header: 'Superseded',
      width: '90px',
      align: 'right',
      numeric: true,
      render: (c) => (
        <span class="font-mono text-[11px] text-warn">~{c.learned_context_superseded ?? 0}</span>
      ),
    },
    {
      key: 'approved',
      header: 'Approved',
      width: '80px',
      align: 'right',
      numeric: true,
      render: (c) => (
        <span class="font-mono text-[11px] text-text">{c.proposals_approved ?? 0}</span>
      ),
    },
    {
      key: 'mode',
      header: 'Mode',
      width: '100px',
      render: (c) => <Chip variant="neutral">{c.mode ?? c.type ?? 'dream'}</Chip>,
    },
    {
      key: 'run_id',
      header: 'Run',
      width: '180px',
      render: (c) => (
        <button
          type="button"
          onClick={() => navigate(`/dreams?id=${encodeURIComponent(c.run_id)}`)}
          class="font-mono text-[10.5px] text-accent hover:underline"
        >
          {c.run_id}
        </button>
      ),
    },
  ];

  return (
    <MemoriesShell>
      <Show when={!cycles.loading} fallback={<SkeletonRows rows={6} />}>
        <Show
          when={!cycles.error}
          fallback={
            <ErrorState
              message={cycles.error instanceof Error ? cycles.error.message : String(cycles.error)}
              onRetry={refetch}
            />
          }
        >
          <div class="flex flex-col gap-3">
            <section class="flex flex-wrap items-stretch gap-x-6 gap-y-2 rounded-md hairline bg-surface px-4 py-2.5">
              <CompactStat label="Cycles with changes" value={String(changedCycles().length)} />
              <CompactStat label="No-op cycles" value={String(noopCycles().length)} />
              <CompactStat
                label="Total created"
                value={String(
                  allCycles().reduce((s, c) => s + (c.learned_context_created ?? 0), 0),
                )}
                tone="ok"
              />
              <CompactStat
                label="Total superseded"
                value={String(
                  allCycles().reduce((s, c) => s + (c.learned_context_superseded ?? 0), 0),
                )}
                tone="warn"
              />
              <CompactStat
                label="Total approved"
                value={String(
                  allCycles().reduce((s, c) => s + (c.proposals_approved ?? 0), 0),
                )}
              />
            </section>

            <p class="text-[11.5px] text-text-muted">
              Each row is one dream cycle. Click the run id to open the Dreams cycle detail and
              see the full proposal funnel + audit artifacts. No-op cycles are hidden by default
              — they're cycles where no proposals were approved.
            </p>

            <Table
              items={changedCycles()}
              columns={cycleColumns}
              rowKey={(c) => c.run_id}
              onRowClick={(c) => navigate(`/dreams?id=${encodeURIComponent(c.run_id)}`)}
              empty={
                <EmptyState
                  icon={Database}
                  title="No memory changes yet"
                  description="Run a dream cycle to produce memory changes."
                  action={
                    <button
                      type="button"
                      onClick={() => navigate('/dreams')}
                      class="mt-2 rounded-md bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg hover:opacity-90"
                    >
                      Go to Dreams →
                    </button>
                  }
                />
              }
            />
          </div>
        </Show>
      </Show>
    </MemoriesShell>
  );
}

function MemoriesShell(props: { children?: JSX.Element }): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const tabValue = (): string => {
    const p = location.pathname;
    if (p.startsWith('/memories/explorer')) return '/memories/explorer';
    if (p.startsWith('/memories/changes')) return '/memories/changes';
    return '/memories';
  };
  return (
    <Page title="Memories" subtitle="Surface, explore, and review semantic changes">
      <Tabs items={TAB_ITEMS} value={tabValue()} onChange={(v) => navigate(v)} />
      {props.children}
    </Page>
  );
}

export default MemoriesSurface;
