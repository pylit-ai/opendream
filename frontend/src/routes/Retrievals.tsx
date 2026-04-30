import { createEffect, createResource, createSignal, For, on, Show, type JSX } from 'solid-js';
import { useSearchParams } from '@solidjs/router';
import { SearchCode } from 'lucide-solid';
import { getMemory, getRetrieval, getRetrievals } from '~/api/client';
import type { RetrievalListParams, RetrievalListResponse, RetrievalRecord } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { FilterBar, type ActiveFilter } from '~/components/FilterBar';
import { SlideOver } from '~/components/SlideOver';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { EmptyState } from '~/components/EmptyState';
import { formatDate, formatDateLong, formatNumber } from '~/lib/format';
import { IdLink } from '~/components/IdLink';
import { MemoryInspector } from '~/components/MemoryInspector';
import { RawFormattedView } from '~/components/RawFormattedView';
import { cachedFetch, peek } from '~/lib/cache';

function asPreview(v: unknown): string | undefined {
  if (v == null) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try { return JSON.stringify(v).slice(0, 240); } catch { return undefined; }
}

const SORT_OPTIONS = [
  { value: 'timestamp:desc', label: 'Newest first' },
  { value: 'timestamp:asc', label: 'Oldest first' },
  { value: 'agent_id:asc', label: 'Agent A→Z' },
];

export default function RetrievalsRoute(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = createSignal((searchParams.search as string) ?? '');
  const [agent, setAgent] = createSignal((searchParams.agent as string) ?? '');
  const [sort, setSort] = createSignal('timestamp:desc');
  const [selectedId, setSelectedId] = createSignal<string | null>(
    (searchParams.id as string) ?? null,
  );
  const [memFocus, setMemFocus] = createSignal<string | null>(null);

  createEffect(
    on(
      () => searchParams.id,
      (v) => {
        const id = typeof v === 'string' ? v : null;
        if (id !== selectedId()) setSelectedId(id);
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

  const openItem = (id: string | null): void => {
    setSelectedId(id);
    setSearchParams({ id: id ?? undefined }, { replace: false });
  };

  const params = (): RetrievalListParams => {
    const [field, dir] = sort().split(':');
    const out: RetrievalListParams = { limit: 50 };
    if (search()) out.search = search();
    if (agent()) out.agent_id = agent();
    if (field) out.sort = field;
    if (dir === 'asc' || dir === 'desc') out.sort_dir = dir;
    return out;
  };

  const [retrievals, { refetch }] = createResource<RetrievalListResponse, RetrievalListParams>(
    params,
    (p) => cachedFetch(`retrievals:${JSON.stringify(p)}`, () => getRetrievals(p), 15_000),
  );

  const [detail] = createResource<RetrievalRecord | null, string | null>(
    selectedId,
    async (id) => {
      if (!id) return null;
      return (await cachedFetch(
        `retrieval:${id}`,
        () => getRetrieval(id),
        60_000,
      ).catch(() => null)) as RetrievalRecord | null;
    },
  );

  const activeFilters = (): ActiveFilter[] => {
    const out: ActiveFilter[] = [];
    if (agent()) {
      const a = agent();
      out.push({ key: 'agent', label: `agent: ${a}`, onRemove: () => setAgent('') });
    }
    return out;
  };

  const columns: TableColumn<RetrievalRecord>[] = [
    {
      key: 'timestamp',
      header: 'Time',
      width: '160px',
      render: (r) =>
        r.timestamp ? (
          <span title={formatDateLong(r.timestamp)} class="text-text">
            {formatDate(r.timestamp)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        ),
    },
    {
      key: 'id',
      header: 'ID',
      width: '160px',
      render: (r) => (
        <IdLink
          id={r.id}
          preview={r.query}
          onClick={() => openItem(r.id)}
          onHover={() => {
            void cachedFetch(`retrieval:${r.id}`, () => getRetrieval(r.id), 60_000);
          }}
        />
      ),
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
      key: 'query',
      header: 'Query',
      render: (r) => (
        <span class="line-clamp-1 text-sm text-text" title={r.query}>
          {r.query ?? '—'}
        </span>
      ),
    },
    {
      key: 'candidates',
      header: 'Candidates',
      width: '110px',
      align: 'right',
      numeric: true,
      render: (r) => {
        const n = Array.isArray(r.candidates)
          ? r.candidates.length
          : (r.candidate_count as number | undefined);
        return (
          <span class="font-mono text-xs text-text-muted">
            {n != null ? formatNumber(n) : '—'}
          </span>
        );
      },
    },
    {
      key: 'selected',
      header: 'Selected',
      width: '90px',
      align: 'right',
      numeric: true,
      render: (r) => (
        <span class="font-mono text-xs text-text-muted">
          {typeof r.selected === 'number' ? formatNumber(r.selected) : r.selected ?? '—'}
        </span>
      ),
    },
  ];

  return (
    <Page title="Retrievals" subtitle="Memory context assembly log">
      <FilterBar
        search={search()}
        onSearchChange={setSearch}
        searchPlaceholder="Search retrievals"
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

      <Show when={!retrievals.loading} fallback={<SkeletonRows rows={6} />}>
        <Show
          when={!retrievals.error}
          fallback={
            <ErrorState
              message={
                retrievals.error instanceof Error
                  ? retrievals.error.message
                  : String(retrievals.error)
              }
              onRetry={refetch}
            />
          }
        >
          <Table
            items={retrievals()?.items ?? []}
            columns={columns}
            rowKey={(r) => r.id}
            onRowClick={(r) => openItem(r.id)}
            empty={
              <EmptyState
                icon={SearchCode}
                title="No retrievals yet"
                description="They'll appear here once an agent queries memory."
              />
            }
          />
        </Show>
      </Show>

      <SlideOver
        open={selectedId() !== null}
        onOpenChange={(o) => !o && openItem(null)}
        title="Retrieval explainability"
        description={selectedId() ?? undefined}
      >
        <div class="flex flex-col gap-4 p-5">
          <Show when={detail.loading}>
            <SkeletonRows rows={4} />
          </Show>
          <Show when={detail()}>
            {(dx) => {
              const item = dx() as RetrievalRecord;
              const explanations =
                ((item as { explanations?: Array<{
                  memory_id?: string;
                  score?: number;
                  matched_evidence?: { lexical_terms?: string[]; semantic_terms?: string[] };
                  why?: string;
                }> }).explanations) ?? [];
              const excluded =
                ((item as { excluded?: Array<{ memory_id?: string; reason?: string }> }).excluded) ??
                [];
              const candidates = ((item as { candidates?: Array<{ memory_id?: string }> }).candidates ??
                []) as Array<{ memory_id?: string }>;
              const assemblyOrder = ((item as {
                final_context_assembly_order?: Array<string | { memory_id?: string }>;
              }).final_context_assembly_order ?? []) as Array<string | { memory_id?: string }>;
              return (
                <>
                  <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                    <dt class="text-text-subtle">Query</dt>
                    <dd class="text-text">{item.query ?? '—'}</dd>
                    <dt class="text-text-subtle">Agent</dt>
                    <dd class="font-mono text-[11.5px] text-text">{item.agent_id ?? '—'}</dd>
                    <dt class="text-text-subtle">Time</dt>
                    <dd class="text-[11.5px] text-text">
                      {item.timestamp ? formatDateLong(item.timestamp as string) : '—'}
                    </dd>
                    <dt class="text-text-subtle">Selected</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {item.selected ?? explanations.length}
                    </dd>
                    <dt class="text-text-subtle">Candidates</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {Array.isArray(item.candidates)
                        ? item.candidates.length
                        : (item.candidate_count as number | undefined) ?? '—'}
                    </dd>
                  </dl>

                  <Show when={explanations.length > 0}>
                    <section class="flex flex-col gap-2">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Scoring breakdown
                      </h4>
                      <div class="flex flex-col gap-1">
                        <For each={explanations}>
                          {(ex) => {
                            const cached = ex.memory_id
                              ? (peek(`memory:${ex.memory_id}`) as
                                  | { title?: string; summary?: string; type?: string }
                                  | undefined)
                              : undefined;
                            const [hydrated] = createResource<
                              { title?: string; summary?: string; type?: string } | null
                            >(async () => {
                              if (!ex.memory_id || cached) return null;
                              return (await cachedFetch(
                                `memory:${ex.memory_id}`,
                                () => getMemory(ex.memory_id!),
                                60_000,
                              ).catch(() => null)) as
                                | { title?: string; summary?: string; type?: string }
                                | null;
                            });
                            const meta = (): { title?: string; summary?: string; type?: string } =>
                              cached ?? hydrated() ?? {};
                            return (
                              <div class="rounded-md hairline bg-surface-elevated px-3 py-2 text-[12px]">
                                <div class="flex items-start justify-between gap-2">
                                  <div class="flex flex-1 flex-col gap-0.5 min-w-0">
                                    <div class="flex items-center gap-2">
                                      <IdLink
                                        id={ex.memory_id ?? null}
                                        onClick={() => ex.memory_id && setMemFocus(ex.memory_id)}
                                      />
                                      <Show when={meta().type}>
                                        <span class="rounded-full bg-surface px-1.5 py-px font-mono text-[10px] text-text-subtle">
                                          {meta().type}
                                        </span>
                                      </Show>
                                    </div>
                                    <Show when={asPreview(meta().title)}>
                                      <span class="line-clamp-1 text-[12px] font-medium text-text">
                                        {asPreview(meta().title)}
                                      </span>
                                    </Show>
                                    <Show
                                      when={
                                        asPreview(meta().summary) &&
                                        asPreview(meta().summary) !== asPreview(meta().title)
                                      }
                                    >
                                      <span class="line-clamp-1 text-[11.5px] text-text-muted">
                                        {asPreview(meta().summary)}
                                      </span>
                                    </Show>
                                  </div>
                                  <Show when={ex.score !== undefined}>
                                    <span class="font-mono text-accent">
                                      {(ex.score ?? 0).toFixed(4)}
                                    </span>
                                  </Show>
                                </div>
                                <Show when={ex.why}>
                                  <p class="mt-1 text-text-muted">{ex.why}</p>
                                </Show>
                              </div>
                            );
                          }}
                        </For>
                      </div>
                    </section>
                  </Show>

                  <Show when={candidates.length > 0 && explanations.length === 0}>
                    <section class="flex flex-col gap-2">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Candidates
                      </h4>
                      <div class="flex flex-col gap-1">
                        <For each={candidates}>
                          {(c) => (
                            <div class="flex items-center gap-2 rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px]">
                              <IdLink
                                id={c.memory_id ?? null}
                                onClick={() => c.memory_id && setMemFocus(c.memory_id)}
                              />
                            </div>
                          )}
                        </For>
                      </div>
                    </section>
                  </Show>

                  <Show when={item.query}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Query
                      </h4>
                      <RawFormattedView
                        content={item.query as string}
                        language="text"
                        storageKey="retrieval-query"
                      />
                    </section>
                  </Show>

                  <Show when={excluded.length > 0 || true}>
                    <section class="flex flex-col gap-1">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Raw retrieval
                      </h4>
                      <RawFormattedView
                        content={JSON.stringify(item, null, 2)}
                        language="json"
                        storageKey="retrieval-raw"
                        defaultMode="raw"
                      />
                    </section>
                  </Show>
                  <Show when={assemblyOrder.length > 0}>
                    <section class="flex flex-col gap-2">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Final assembly order · {assemblyOrder.length}
                      </h4>
                      <ol class="flex flex-col gap-1">
                        <For each={assemblyOrder}>
                          {(entry, i) => {
                            const id = typeof entry === 'string' ? entry : entry.memory_id ?? null;
                            return (
                              <li class="flex items-center gap-2 rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px]">
                                <span class="w-6 font-mono text-[11px] tabular-nums text-text-subtle">
                                  {i() + 1}
                                </span>
                                <IdLink
                                  id={id}
                                  onClick={() => id && setMemFocus(id)}
                                />
                              </li>
                            );
                          }}
                        </For>
                      </ol>
                    </section>
                  </Show>
                  <Show when={excluded.length > 0}>
                    <section class="flex flex-col gap-2">
                      <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                        Excluded · {excluded.length}
                      </h4>
                      <div class="flex flex-col gap-1">
                        <For each={excluded}>
                          {(ex) => (
                            <div class="flex items-center justify-between gap-2 rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px]">
                              <IdLink
                                id={ex.memory_id ?? null}
                                onClick={() => ex.memory_id && setMemFocus(ex.memory_id)}
                              />
                              <span class="text-text-subtle">{ex.reason ?? '—'}</span>
                            </div>
                          )}
                        </For>
                      </div>
                    </section>
                  </Show>
                </>
              );
            }}
          </Show>
        </div>
      </SlideOver>

      <SlideOver
        open={memFocus() !== null}
        onOpenChange={(o) => !o && setMemFocus(null)}
        title="Memory inspector"
        description={memFocus() ?? undefined}
      >
        <Show when={memFocus()}>
          {(id) => <MemoryInspector memoryId={id()} onNavigate={(next) => setMemFocus(next)} />}
        </Show>
      </SlideOver>
    </Page>
  );
}
