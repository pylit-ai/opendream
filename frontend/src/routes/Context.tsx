import { createEffect, createResource, createSignal, For, Show, type JSX } from 'solid-js';
import { useNavigate, useSearchParams } from '@solidjs/router';
import { FileText } from 'lucide-solid';
import { getContext, getContexts, getContextUseRecords } from '~/api/client';
import { cachedFetch } from '~/lib/cache';
import type {
  ContextListResponse,
  ContextRecord,
  ContextUseListResponse,
  ContextUseRecord,
} from '~/api/types';
import { Page } from '~/components/Page';
import { EmptyState } from '~/components/EmptyState';
import { LoadingPage } from '~/components/Loading';
import { ErrorState } from '~/components/ErrorState';
import { RawFormattedView } from '~/components/RawFormattedView';
import { formatDate, formatDateLong, formatNumber } from '~/lib/format';
import { cn } from '~/lib/cn';

interface ContextEntry {
  context_id: string;
  session_id?: string;
  created_at?: string;
  character_count?: number;
  selected_memory_ids_count?: number;
  context_use_count?: number;
  latest_memory_use_state?: string;
  latest_context_use_id?: string;
  query?: string;
  display_name?: string;
}

function MemoryUseStateChip(props: { state?: string; hasRecord?: boolean }): JSX.Element {
  const state = () => (props.hasRecord === false ? 'not-recorded' : (props.state || 'unknown')).toLowerCase();
  const label = () => {
    switch (state()) {
      case 'not-recorded':
        return 'No use record';
      case 'unknown':
        return 'Unknown use';
      case 'checked-none':
        return 'Checked none';
      case 'used':
        return 'Used';
      case 'ignored':
        return 'Ignored';
      case 'conflicted':
        return 'Conflicted';
      case 'stale':
        return 'Stale';
      default:
        return state();
    }
  };
  const title = () => {
    switch (state()) {
      case 'not-recorded':
        return 'No context-use audit record exists for this prepared context. It may predate this instrumentation, or the agent did not record usage. This does not prove the memory was unused.';
      case 'unknown':
        return 'A context-use audit record exists, but the agent or wrapper did not say whether the selected memories were used, ignored, stale, or conflicted.';
      case 'used':
        return 'The agent explicitly recorded at least one selected memory as used for this context.';
      case 'checked-none':
        return 'The agent recorded that it checked the prepared context and no selected memory applied.';
      case 'ignored':
        return 'The agent recorded that it ignored the prepared context.';
      case 'conflicted':
        return 'The agent recorded that selected memory conflicted with the task or other evidence.';
      case 'stale':
        return 'The agent recorded that selected memory was stale for the task.';
      default:
        return `Memory-use state: ${state()}`;
    }
  };
  const tone = () => {
    switch (state()) {
      case 'used':
        return 'border-emerald-500/40 bg-emerald-500/12 text-emerald-300';
      case 'checked-none':
        return 'border-sky-500/40 bg-sky-500/12 text-sky-300';
      case 'ignored':
      case 'unknown':
        return 'border-amber-500/40 bg-amber-500/12 text-amber-300';
      case 'conflicted':
      case 'stale':
        return 'border-rose-500/40 bg-rose-500/12 text-rose-300';
      case 'not-recorded':
        return 'border-border bg-surface-elevated text-text-muted';
      default:
        return 'border-border bg-surface-elevated text-text-muted';
    }
  };
  return (
    <span
      class={cn('rounded-full border px-2 py-0.5 text-[10.5px] font-medium', tone())}
      title={title()}
      aria-label={title()}
    >
      {label()}
    </span>
  );
}

function SelectionMetric(props: {
  label: string;
  candidateCount?: number;
  selectedCount?: number;
  emptyHint?: string;
}): JSX.Element {
  const candidates = () => props.candidateCount ?? 0;
  const selected = () => props.selectedCount ?? 0;
  const empty = () => candidates() === 0 || selected() === 0;
  return (
    <div class="rounded-md border border-border bg-surface-elevated px-3 py-2">
      <div class="flex items-center justify-between gap-3">
        <span class="text-[11px] font-medium text-text">{props.label}</span>
        <span class={cn('font-mono text-[11px]', empty() ? 'text-warn' : 'text-success')}>
          {formatNumber(selected())}/{formatNumber(candidates())}
        </span>
      </div>
      <Show when={empty() && props.emptyHint}>
        <p class="mt-1 text-[10.5px] leading-4 text-text-muted">{props.emptyHint}</p>
      </Show>
    </div>
  );
}

export default function ContextRoute(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialId = typeof searchParams.id === 'string' ? searchParams.id : null;
  const [selectedId, setSelectedId] = createSignal<string | null>(initialId);

  const [contextsData, { refetch: refetchContexts }] = createResource<ContextListResponse>(() =>
    cachedFetch('contexts:200', () => getContexts({ limit: 200 }), 15_000),
  );
  const [contextUseData] = createResource<ContextUseListResponse>(() =>
    cachedFetch('context-use:200', () => getContextUseRecords({ limit: 200 }), 15_000),
  );

  const contextEntries = (): ContextEntry[] => {
    return (contextsData()?.items ?? []) as ContextEntry[];
  };
  const contextUseEntries = (): ContextUseRecord[] => contextUseData()?.items ?? [];
  const useRecordsForContext = (contextId?: string | null): ContextUseRecord[] => {
    if (!contextId) return [];
    return contextUseEntries().filter((row) => row.context_id === contextId);
  };
  const latestUseForContext = (contextId?: string | null): ContextUseRecord | undefined =>
    useRecordsForContext(contextId)[0];

  createEffect(() => {
    const id = typeof searchParams.id === 'string' ? searchParams.id : null;
    if (id && id !== selectedId()) setSelectedId(id);
  });

  createEffect(() => {
    if (selectedId()) return;
    const first = contextEntries()[0];
    if (first) setSelectedId(first.context_id);
  });

  const selectContext = (id: string): void => {
    setSelectedId(id);
    setSearchParams({ id }, { replace: false });
  };

  const openMemory = (id: string): void => {
    if (!id || id === '?') return;
    navigate(`/memories/explorer?id=${encodeURIComponent(id)}`);
  };

  const [contextDetail] = createResource<ContextRecord | null, string | null>(
    selectedId,
    async (id) => {
      if (!id) return null;
      return cachedFetch(`context:${id}`, () => getContext(id), 60_000).catch(() => null);
    },
  );
  const selectedUseRecords = (): ContextUseRecord[] => {
    const detailRecords = contextDetail()?.context_use_records ?? [];
    return detailRecords.length > 0 ? detailRecords : useRecordsForContext(selectedId());
  };

  const assembledText = (): string => {
    const d = contextDetail();
    if (!d) return '';
    // try assembled_text in detail or nested payload
    const direct = (d as { assembled_text?: string }).assembled_text;
    if (direct) return direct;
    // might be nested
    const payload = (d as { payload?: { assembled_text?: string } }).payload;
    return payload?.assembled_text ?? JSON.stringify(d, null, 2);
  };

  return (
    <Page title="Context" subtitle="Assembled memory context records">
      <Show
        when={!contextsData.loading}
        fallback={
          <LoadingPage
            label="Loading contexts"
            detail="Reading persisted context assemblies from the workspace."
          />
        }
      >
        <Show
          when={!contextsData.error}
          fallback={
            <ErrorState
              message={
                contextsData.error instanceof Error
                  ? contextsData.error.message
                  : String(contextsData.error)
              }
              onRetry={refetchContexts}
            />
          }
        >
          <Show
            when={contextEntries().length > 0}
            fallback={
              <EmptyState
                icon={FileText}
                title="No context records found"
                description="Context is assembled on-demand during dream cycles. Use ⌘K to open a specific context by ID."
              />
            }
          >
            <div class="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-lg hairline">
              {/* Left list */}
              <nav class="hairline-r flex w-72 flex-shrink-0 flex-col overflow-y-auto bg-surface scrollbar-thin">
                <For each={contextEntries()}>
                  {(entry) => (
                    <button
                      type="button"
                      onClick={() => selectContext(entry.context_id)}
                      class={cn(
                        'hairline-b row-hover flex flex-col gap-0.5 px-4 py-3 text-left text-xs',
                        selectedId() === entry.context_id
                          ? 'bg-[color-mix(in_oklab,rgb(var(--c-accent))_10%,transparent)] text-text'
                          : 'hover:bg-surface-elevated',
                      )}
                    >
                      <span class="truncate font-medium text-text">
                        {entry.display_name ?? entry.query ?? entry.context_id}
                      </span>
                      <div class="flex items-center justify-between gap-2">
                        <span class="truncate font-mono text-[10.5px] text-text-muted">
                          {entry.context_id}
                        </span>
                        <MemoryUseStateChip
                          state={entry.latest_memory_use_state ?? latestUseForContext(entry.context_id)?.memory_use_state}
                          hasRecord={(entry.context_use_count ?? 0) > 0 || latestUseForContext(entry.context_id) !== undefined}
                        />
                      </div>
                      <div class="flex items-center gap-2 text-text-subtle">
                        <Show when={entry.created_at}>
                          <span>{formatDate(entry.created_at!)}</span>
                        </Show>
                      <Show when={entry.character_count}>
                        <span class="tabular-nums">{formatNumber(entry.character_count!)} chars</span>
                      </Show>
                      <Show when={entry.selected_memory_ids_count !== undefined}>
                        <span class="tabular-nums">
                          {formatNumber(entry.selected_memory_ids_count!)} selected
                        </span>
                      </Show>
                    </div>
                  </button>
                  )}
                </For>
              </nav>

              {/* Right detail */}
              <div class="flex min-w-0 flex-1 flex-col overflow-y-auto bg-surface p-4">
                <Show
                  when={selectedId()}
                  fallback={
                    <div class="flex h-full items-center justify-center">
                      <p class="text-sm text-text-muted">Select a context record to view</p>
                    </div>
                  }
                >
                  <Show when={contextDetail.loading}>
                    <LoadingPage
                      label="Loading context detail"
                      detail={selectedId() ?? 'Fetching assembled prompt context.'}
                    />
                  </Show>
                  <Show when={!contextDetail.loading && contextDetail()}>
                    {(d) => (
                      <div class="flex flex-col gap-3">
                        <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-sm">
                          <Show when={(d() as { display_name?: string }).display_name}>
                            <dt class="text-text-muted">Name</dt>
                            <dd class="text-text">{(d() as { display_name?: string }).display_name}</dd>
                          </Show>
                          <dt class="text-text-muted">Context ID</dt>
                          <dd class="font-mono text-xs text-text">{d().context_id}</dd>
                          <Show when={(d() as { created_at?: string }).created_at}>
                            <dt class="text-text-muted">Created</dt>
                            <dd class="text-xs">
                              {formatDateLong((d() as unknown as { created_at: string }).created_at)}
                            </dd>
                          </Show>
                        </dl>
                        {(() => {
                          const selection = d().selection ?? {};
                          const durable = selection.durable_memory ?? {};
                          const learned = selection.learned_context ?? {};
                          const automation = selection.automation ?? {};
                          const pruning = d().context_pruning ?? {};
                          return (
                            <section class="flex flex-col gap-2">
                              <div class="flex items-center justify-between gap-3">
                                <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                  Selection diagnostics
                                </h4>
                                <span class="text-[10.5px] text-text-muted">
                                  {formatNumber(pruning.suppressed_count ?? 0)} suppressed
                                </span>
                              </div>
                              <div class="grid gap-2 md:grid-cols-3">
                                <SelectionMetric
                                  label="Durable memory"
                                  candidateCount={durable.candidate_count}
                                  selectedCount={durable.selected}
                                  emptyHint="No durable memories matched this query."
                                />
                                <SelectionMetric
                                  label="Learned context"
                                  candidateCount={learned.candidate_count}
                                  selectedCount={learned.selected}
                                  emptyHint="No active prompt-eligible learned-context records matched."
                                />
                                <SelectionMetric
                                  label="Automation"
                                  candidateCount={automation.candidate_count}
                                  selectedCount={automation.selected}
                                  emptyHint="No active automation projections are available."
                                />
                              </div>
                            </section>
                          );
                        })()}
                        <section class="flex flex-col gap-1">
                          <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                            Assembled text
                          </h4>
                          <RawFormattedView
                            content={assembledText()}
                            language="auto"
                            storageKey="context-assembled"
                          />
                        </section>
                        {(() => {
                          const dx = d() as {
                            selected_memory_ids?: string[];
                            omission_reasons?: Record<string, string> | Array<{ memory_id?: string; reason?: string }>;
                            startup_index_snapshot?: unknown;
                          };
                          const selected = dx.selected_memory_ids ?? [];
                          const useRecords = selectedUseRecords();
                          const latestUse = useRecords[0];
                          const usedMemoryIds = new Set(
                            useRecords.flatMap((record) => record.used_memory_ids ?? []),
                          );
                          const omissions = dx.omission_reasons;
                          const omissionEntries: Array<{ id: string; reason: string }> = Array.isArray(
                            omissions,
                          )
                            ? omissions.map((o) => ({ id: o.memory_id ?? '?', reason: o.reason ?? '' }))
                            : omissions && typeof omissions === 'object'
                              ? Object.entries(omissions).map(([id, reason]) => ({ id, reason: String(reason) }))
                              : [];
                          const startup = dx.startup_index_snapshot;
                          return (
                            <>
                              <section class="flex flex-col gap-2">
                                <div class="flex items-center justify-between gap-3">
                                  <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                    Context use audit
                                  </h4>
                                  <MemoryUseStateChip
                                    state={latestUse?.memory_use_state}
                                    hasRecord={latestUse !== undefined}
                                  />
                                </div>
                                <Show
                                  when={useRecords.length > 0}
                                  fallback={
                                    <div class="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-200">
                                      No context-use audit record exists for this prepared context. This often means the context predates the audit feature, or the agent did not record usage. It does not prove the selected memories were unused.
                                    </div>
                                  }
                                >
                                  <div class="flex flex-col gap-2">
                                    <For each={useRecords.slice(0, 5)}>
                                      {(record) => (
                                        <div class="rounded-md hairline bg-surface-elevated px-3 py-2 text-[12px]">
                                          <div class="flex flex-wrap items-center justify-between gap-2">
                                            <div class="flex items-center gap-2">
                                              <span class="font-mono text-accent">{record.usage_id}</span>
                                              <MemoryUseStateChip state={record.memory_use_state} />
                                            </div>
                                            <Show when={record.timestamp}>
                                              <span class="text-text-subtle">{formatDate(record.timestamp!)}</span>
                                            </Show>
                                          </div>
                                          <div class="mt-1 grid gap-1 text-text-muted md:grid-cols-[96px_1fr]">
                                            <Show when={record.reporting_agent_label}>
                                              <span>Agent</span>
                                              <span class="text-text">{record.reporting_agent_label}</span>
                                            </Show>
                                            <span>Used IDs</span>
                                            <span class="font-mono text-text">
                                              {(record.used_memory_ids ?? []).length > 0
                                                ? record.used_memory_ids!.join(', ')
                                                : 'none recorded'}
                                            </span>
                                            <Show when={record.usage_note}>
                                              <span>Note</span>
                                              <span class="text-text">{record.usage_note}</span>
                                            </Show>
                                            <Show when={record.visible_attestation}>
                                              <span>Attestation</span>
                                              <span class="text-text">{record.visible_attestation}</span>
                                            </Show>
                                          </div>
                                        </div>
                                      )}
                                    </For>
                                  </div>
                                </Show>
                              </section>
                              <Show when={selected.length > 0}>
                                <section class="flex flex-col gap-1">
                                  <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                    Selected memories · {selected.length}
                                  </h4>
                                  <div class="flex flex-col gap-1">
                                    <For each={selected}>
                                      {(id) => (
                                        <button
                                          type="button"
                                          onClick={() => openMemory(id)}
                                          class="rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px] text-left w-full hover:bg-surface transition-colors"
                                          title={`Open memory ${id} in Explorer`}
                                        >
                                          <span class="font-mono text-accent hover:underline">{id}</span>
                                          <span class="ml-2 rounded-full border border-border px-1.5 py-0.5 text-[10px] text-text-subtle">
                                            {usedMemoryIds.has(id)
                                              ? 'used'
                                              : latestUse
                                                ? 'selected only'
                                                : 'not recorded'}
                                          </span>
                                        </button>
                                      )}
                                    </For>
                                  </div>
                                </section>
                              </Show>
                              <Show when={omissionEntries.length > 0}>
                                <section class="flex flex-col gap-1">
                                  <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                    Omitted · {omissionEntries.length}
                                  </h4>
                                  <div class="flex flex-col gap-1">
                                    <For each={omissionEntries}>
                                      {(o) => (
                                        <button
                                          type="button"
                                          onClick={() => openMemory(o.id)}
                                          disabled={!o.id || o.id === '?'}
                                          class="group flex w-full items-center justify-between gap-2 rounded-md hairline bg-surface-elevated px-3 py-1.5 text-left text-[12px] transition-colors enabled:hover:bg-surface disabled:cursor-default"
                                          title={o.id && o.id !== '?' ? `Open memory ${o.id} in Explorer` : undefined}
                                        >
                                          <span class="font-mono text-accent group-hover:underline">{o.id}</span>
                                          <span class="text-text-subtle">{o.reason || '—'}</span>
                                        </button>
                                      )}
                                    </For>
                                  </div>
                                </section>
                              </Show>
                              <Show when={startup !== undefined && startup !== null}>
                                <section class="flex flex-col gap-1">
                                  <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                    Startup index snapshot
                                  </h4>
                                  <RawFormattedView
                                    content={JSON.stringify(startup, null, 2)}
                                    language="json"
                                    storageKey="context-startup-index"
                                    defaultMode="raw"
                                  />
                                </section>
                              </Show>
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </Show>
                  <Show when={!contextDetail.loading && !contextDetail()}>
                    <p class="text-sm text-text-muted">Context record not found.</p>
                  </Show>
                </Show>
              </div>
            </div>
          </Show>
        </Show>
      </Show>
    </Page>
  );
}
