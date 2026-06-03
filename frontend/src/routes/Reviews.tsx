import { createEffect, createMemo, createResource, createSignal, For, onCleanup, onMount, on, Show, type JSX } from 'solid-js';
import { useNavigate, useSearchParams } from '@solidjs/router';
import { CheckCircle } from 'lucide-solid';
import {
  applyReviewRecommendations,
  getAutoReviewerStats,
  getMemory,
  getReviewRecommendations,
  getReviews,
  getRun,
  getRunDiff,
  submitReviewDecision,
  type ReviewRecommendation,
  type ReviewRecommendationsResponse,
} from '~/api/client';
import type { AutoReviewerStats } from '~/api/types';
import type { MemoryRecord, ReviewsResponse, RunDiff, RunRecord } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { FilterBar, type ActiveFilter } from '~/components/FilterBar';
import { Chip, type ChipVariant } from '~/components/Chip';
import { EmptyState } from '~/components/EmptyState';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { SlideOver } from '~/components/SlideOver';
import { MemoryInspector } from '~/components/MemoryInspector';
import { DiffView } from '~/components/DiffView';
import { IdLink } from '~/components/IdLink';
import { RawFormattedView } from '~/components/RawFormattedView';
import { cachedFetch, invalidate, peek } from '~/lib/cache';
import {
  REVIEW_QUEUE_GLOSSARY,
  helpForReviewQueueType,
  labelForReviewQueueType,
} from '~/lib/observeGlossary';

type ReviewAction = 'approve' | 'suppress' | 'merge' | 'split' | 'mark_stale' | 'attach_note' | 'escalate';

interface RichReviewItem {
  id: string;
  queue_item_id: string;
  queue_item_type: string;
  object_id: string;
  object_type: string;
  reason: string;
  actions: ReviewAction[];
  created_at?: string;
  [k: string]: unknown;
}

function asPreview(v: unknown): string | undefined {
  if (v == null) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try { return JSON.stringify(v).slice(0, 240); } catch { return undefined; }
}

function queueTypeVariant(t: string): ChipVariant {
  if (t.includes('contested')) return 'warn';
  if (t.includes('failed')) return 'danger';
  if (t.includes('large_diff')) return 'warn';
  if (t.includes('suspicious')) return 'danger';
  return 'neutral';
}

function queueTypeLabel(t: string): string {
  return labelForReviewQueueType(t);
}

const ALL_TYPES = [
  'contested_memory',
  'low_confidence_memory',
  'large_diff',
  'failed_run',
  'suspicious_retrieval',
];

const SORT_OPTIONS = [
  { value: 'default', label: 'Default order' },
  { value: 'type:asc', label: 'Type A→Z' },
];

export default function ReviewsRoute(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [typeFilter, setTypeFilter] = createSignal((searchParams.type as string) ?? '');
  const [sort, setSort] = createSignal('default');
  const [pendingActions, setPendingActions] = createSignal<Set<string>>(new Set());
  const [selected, setSelected] = createSignal<RichReviewItem | null>(null);
  const [previewMap, setPreviewMap] = createSignal<Record<string, string>>({});
  const [checked, setChecked] = createSignal<Set<string>>(new Set());
  const [groupBy, setGroupBy] = createSignal<'none' | 'type'>('none');
  const [bulkPending, setBulkPending] = createSignal(false);
  const [bulkProgress, setBulkProgress] = createSignal({ done: 0, total: 0 });
  const [helpOpen, setHelpOpen] = createSignal(false);
  const [focusedIndex, setFocusedIndex] = createSignal(0);

  const [reviews, { refetch }] = createResource<ReviewsResponse>(() =>
    cachedFetch('reviews', getReviews, 15_000),
  );

  const [autoStats] = createResource<AutoReviewerStats | null>(getAutoReviewerStats);
  const autoAppliedCount = (): number => autoStats()?.last_run?.applied_count ?? 0;

  // Recommendations: deterministic per-rule suggestions for every queue item.
  const [recsResp, { refetch: refetchRecs }] = createResource<ReviewRecommendationsResponse | null>(
    getReviewRecommendations,
  );
  const recMap = createMemo<Map<string, ReviewRecommendation>>(() => {
    const m = new Map<string, ReviewRecommendation>();
    for (const r of recsResp()?.items ?? []) m.set(r.queue_item_id, r);
    return m;
  });
  const [showOnlyRecs, setShowOnlyRecs] = createSignal(false);
  const [applyAllPending, setApplyAllPending] = createSignal(false);
  const [applyAllResult, setApplyAllResult] = createSignal<string | null>(null);

  const applyAllRecommendations = async (): Promise<void> => {
    const total = recsResp()?.total_recommended ?? 0;
    if (total === 0) return;
    if (
      !window.confirm(
        `Apply ${total} recommended action${total === 1 ? '' : 's'}? Each becomes a ReviewDecision with actor=auto-reviewer:<rule>. Reversible per item.`,
      )
    )
      return;
    setApplyAllPending(true);
    setApplyAllResult(null);
    try {
      const res = await applyReviewRecommendations();
      setApplyAllResult(`Applied ${res.applied_count} of ${res.proposed_count}.`);
    } catch (e) {
      setApplyAllResult(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      invalidate('reviews');
      await Promise.allSettled([refetch(), refetchRecs()]);
      setApplyAllPending(false);
      // Auto-clear the "Applied N of M" text when the queue is now empty
      if ((reviews()?.items?.length ?? 0) === 0) {
        setApplyAllResult(null);
      }
    }
  };

  // URL ↔ state for ?id= and ?type=
  createEffect(
    on(typeFilter, (v) => {
      const cur = (searchParams.type as string) ?? '';
      if (v !== cur) setSearchParams({ type: v || undefined }, { replace: true });
    }),
  );
  createEffect(
    on(
      () => searchParams.type,
      (v) => {
        const x = typeof v === 'string' ? v : '';
        if (x !== typeFilter()) setTypeFilter(x);
      },
    ),
  );
  createEffect(
    on(
      () => [reviews(), searchParams.id] as const,
      ([data, id]) => {
        const wanted = typeof id === 'string' ? id : null;
        if (!wanted) {
          if (selected() !== null) setSelected(null);
          return;
        }
        const items = (data?.items ?? []) as RichReviewItem[];
        const found = items.find(
          (r) => r.id === wanted || r.queue_item_id === wanted || r.object_id === wanted,
        );
        if (found && selected()?.id !== found.id) setSelected(found);
      },
    ),
  );

  const openItem = (item: RichReviewItem | null): void => {
    setSelected(item);
    setSearchParams(
      { id: item ? item.id ?? item.queue_item_id ?? item.object_id : undefined },
      { replace: false },
    );
  };

  const activeFilters = (): ActiveFilter[] => {
    const out: ActiveFilter[] = [];
    if (typeFilter()) {
      const t = typeFilter();
      out.push({ key: 'type', label: `type: ${queueTypeLabel(t)}`, onRemove: () => setTypeFilter('') });
    }
    return out;
  };

  const filteredItems = (): RichReviewItem[] => {
    let list = (reviews()?.items ?? []) as RichReviewItem[];
    if (typeFilter()) list = list.filter((r) => r.queue_item_type === typeFilter());
    if (showOnlyRecs()) list = list.filter((r) => recMap().has(r.queue_item_id ?? r.id));
    if (sort() === 'type:asc') {
      list = [...list].sort((a, b) => (a.queue_item_type ?? '').localeCompare(b.queue_item_type ?? ''));
    }
    return list;
  };

  // Background prefetch + preview population for memory-typed items.
  createEffect(() => {
    const list = (reviews()?.items ?? []) as RichReviewItem[];
    const memIds = list
      .filter((r) => r.object_type === 'memory' && r.object_id)
      .map((r) => r.object_id)
      .slice(0, 24);
    if (memIds.length === 0) return;
    void Promise.allSettled(
      memIds.map(async (id) => {
        const m = (await cachedFetch(`memory:${id}`, () => getMemory(id), 60_000).catch(
          () => null,
        )) as MemoryRecord | null;
        if (!m) return;
        const body = (m.summary as string | undefined) ?? (m.body as string | undefined);
        if (body) {
          setPreviewMap((prev) => ({ ...prev, [id]: body.replace(/\s+/g, ' ').slice(0, 120) }));
        }
      }),
    );
  });

  const submitAction = async (item: RichReviewItem, action: ReviewAction): Promise<void> => {
    const key = `${item.id}:${action}`;
    setPendingActions((prev) => new Set([...prev, key]));
    try {
      await submitReviewDecision(`${item.queue_item_id}/${action}`, {
        queue_item_type: item.queue_item_type,
        rationale: '',
        actor: 'operator',
      });
    } catch {
      // refetch anyway
    } finally {
      invalidate('reviews');
      await refetch();
      setPendingActions((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      openItem(null);
    }
  };

  const isPending = (item: RichReviewItem, action: ReviewAction): boolean =>
    pendingActions().has(`${item.id}:${action}`);

  const toggleChecked = (id: string): void => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const checkedItems = createMemo<RichReviewItem[]>(() => {
    const set = checked();
    return filteredItems().filter((r) => set.has(r.id));
  });

  const allFilteredChecked = (): boolean => {
    const f = filteredItems();
    if (f.length === 0) return false;
    const set = checked();
    return f.every((r) => set.has(r.id));
  };

  const toggleAllFiltered = (): void => {
    const f = filteredItems();
    setChecked((prev) => {
      const next = new Set(prev);
      const all = f.every((r) => next.has(r.id));
      if (all) f.forEach((r) => next.delete(r.id));
      else f.forEach((r) => next.add(r.id));
      return next;
    });
  };

  const bulkSubmit = async (action: ReviewAction): Promise<void> => {
    const items = checkedItems().filter((r) => r.actions?.includes(action));
    if (items.length === 0) return;
    setBulkPending(true);
    setBulkProgress({ done: 0, total: items.length });
    let done = 0;
    for (const item of items) {
      try {
        await submitReviewDecision(`${item.queue_item_id}/${action}`, {
          queue_item_type: item.queue_item_type,
          rationale: '',
          actor: 'operator',
        });
      } catch {
        // continue
      } finally {
        done += 1;
        setBulkProgress({ done, total: items.length });
      }
    }
    invalidate('reviews');
    await refetch();
    setChecked(new Set<string>());
    setBulkPending(false);
    setBulkProgress({ done: 0, total: 0 });
  };

  // Keyboard shortcuts: j/k navigate, x toggle check, a/s/m primary actions, ? help, esc close.
  onMount(() => {
    const onKey = (e: KeyboardEvent) => {
      if (helpOpen() && e.key === 'Escape') {
        setHelpOpen(false);
        e.preventDefault();
        return;
      }
      const tag = (e.target as HTMLElement | null)?.tagName ?? '';
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const list = filteredItems();
      if (list.length === 0) return;
      const idx = Math.min(focusedIndex(), list.length - 1);
      const cur = list[idx];
      switch (e.key) {
        case '?':
          setHelpOpen(true);
          e.preventDefault();
          return;
        case 'j':
          setFocusedIndex(Math.min(idx + 1, list.length - 1));
          e.preventDefault();
          return;
        case 'k':
          setFocusedIndex(Math.max(idx - 1, 0));
          e.preventDefault();
          return;
        case 'x':
          if (cur) toggleChecked(cur.id);
          e.preventDefault();
          return;
        case 'a':
          if (cur && cur.actions?.includes('approve')) void submitAction(cur, 'approve');
          e.preventDefault();
          return;
        case 's':
          if (cur && cur.actions?.includes('suppress')) void submitAction(cur, 'suppress');
          e.preventDefault();
          return;
        case 'm':
          if (cur && cur.actions?.includes('mark_stale')) void submitAction(cur, 'mark_stale');
          e.preventDefault();
          return;
        case 'Enter':
          if (cur) openItem(cur);
          e.preventDefault();
          return;
        case 'Escape':
          if (selected()) openItem(null);
          return;
      }
    };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  const columns: TableColumn<RichReviewItem>[] = [
    {
      key: 'check',
      header: '',
      width: '34px',
      render: (r) => (
        <input
          type="checkbox"
          checked={checked().has(r.id)}
          onClick={(e) => e.stopPropagation()}
          onChange={() => toggleChecked(r.id)}
          class="h-3.5 w-3.5 cursor-pointer accent-accent"
          aria-label={`Select ${r.id}`}
        />
      ),
    },
    {
      key: 'type',
      header: 'Type',
      width: '170px',
      render: (r) => {
        const queueType = r.queue_item_type ?? 'unknown';
        const help = helpForReviewQueueType(queueType);
        return (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setTypeFilter(queueType);
            }}
            class="cursor-pointer rounded transition-opacity hover:opacity-80"
            title={`Filter by type: ${queueTypeLabel(queueType)}. ${help}`}
          >
            <Chip variant={queueTypeVariant(queueType)} title={help}>
              {queueTypeLabel(queueType)}
            </Chip>
          </button>
        );
      },
    },
    {
      key: 'item_id',
      header: 'Item',
      width: '220px',
      render: (r) => (
        <div class="flex flex-col gap-0.5">
          <IdLink
            id={r.object_id ?? r.queue_item_id}
            preview={previewMap()[r.object_id]}
            onClick={() => openItem(r)}
            onHover={() => {
              if (r.object_type === 'memory' && r.object_id) {
                void cachedFetch(`memory:${r.object_id}`, () => getMemory(r.object_id!), 60_000);
              }
            }}
          />
          <Show when={previewMap()[r.object_id]}>
            <span class="line-clamp-1 text-[11px] text-text-subtle">
              {previewMap()[r.object_id]}
            </span>
          </Show>
        </div>
      ),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (r) => <span class="text-sm text-text">{r.reason ?? '—'}</span>,
    },
    {
      key: 'recommended',
      header: 'Recommended',
      width: '160px',
      render: (r) => {
        const rec = recMap().get(r.queue_item_id ?? r.id);
        if (!rec) return <span class="text-text-subtle">—</span>;
        const tone =
          rec.action === 'approve'
            ? 'ok'
            : rec.action === 'suppress'
              ? 'danger'
              : 'warn';
        return (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              void submitAction(r, rec.action as ReviewAction);
            }}
            disabled={!r.actions?.includes(rec.action as ReviewAction)}
            title={`${rec.rule_id}: ${rec.rationale}\n\nClick to apply just this one.`}
            class="row-hover flex items-center gap-1.5"
          >
            <Chip variant={tone as ChipVariant}>{rec.action.replace(/_/g, ' ')}</Chip>
            <span class="font-mono text-[10px] text-text-subtle">{rec.rule_id}</span>
          </button>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      width: '210px',
      align: 'right',
      render: (r) => {
        const primary: ReviewAction[] = (['approve', 'suppress', 'mark_stale'] as ReviewAction[]).filter(
          (a) => r.actions?.includes(a),
        );
        return (
          <div class="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            {primary.map((action) => (
              <button
                type="button"
                disabled={isPending(r, action)}
                onClick={() => submitAction(r, action)}
                class={
                  action === 'approve'
                    ? 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium bg-[color-mix(in_oklab,rgb(var(--c-success))_14%,transparent)] text-success hover:bg-[color-mix(in_oklab,rgb(var(--c-success))_22%,transparent)] disabled:opacity-50 transition-colors'
                    : action === 'suppress'
                    ? 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium bg-[color-mix(in_oklab,rgb(var(--c-danger))_14%,transparent)] text-danger hover:bg-[color-mix(in_oklab,rgb(var(--c-danger))_22%,transparent)] disabled:opacity-50 transition-colors'
                    : 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium hairline text-text-muted hover:bg-surface-elevated hover:text-text disabled:opacity-50 transition-colors'
                }
              >
                {isPending(r, action) ? '…' : action.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        );
      },
    },
  ];

  return (
    <Page
      title="Review queue"
      subtitle="Optional review backlog for uncertain memories, inspectable run diffs, and retrievals that need a spot check"
    >
      <section class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text-muted">
        <p>
          <span class="font-medium text-text">Review queue items are prompts for judgment, not automatic failures.</span>{' '}
          Approve, suppress, mark stale, or attach notes when the evidence explains what should happen.
        </p>
        <details class="mt-2">
          <summary class="cursor-pointer font-medium text-text">Review type glossary</summary>
          <div class="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <For each={REVIEW_QUEUE_GLOSSARY}>
              {(entry) => (
                <div class="rounded bg-surface-elevated/60 px-2 py-1.5">
                  <div class="font-mono text-[10.5px] text-text" title={entry.help}>{entry.key}</div>
                  <div>{entry.help}</div>
                </div>
              )}
            </For>
          </div>
        </details>
      </section>

      <Show when={!autoStats.loading && autoStats() !== null && autoAppliedCount() > 0}>
        <button
          type="button"
          onClick={() => navigate('/settings?tab=automation')}
          class="flex w-full items-center gap-2 rounded-md bg-surface-elevated px-3 py-2 hairline text-left text-[12px] text-text hover:bg-surface-elevated/80 transition-colors"
        >
          <span class="font-medium">{autoAppliedCount()} item{autoAppliedCount() === 1 ? '' : 's'} auto-resolved this session</span>
          <span class="text-text-muted">· View automation settings →</span>
        </button>
      </Show>

      <Show when={(recsResp()?.total_recommended ?? 0) > 0}>
        <div class="flex flex-wrap items-center gap-2 rounded-md hairline bg-surface px-3 py-2 text-[12px]">
          <span class="font-medium text-text">
            {recsResp()!.total_recommended} of {recsResp()!.total_items} have a recommended action
          </span>
          <Show when={Object.keys(recsResp()!.by_action).length > 0}>
            <span class="text-text-subtle">·</span>
            <span class="font-mono text-[10.5px] text-text-muted">
              {Object.entries(recsResp()!.by_action)
                .map(([k, v]) => `${k}:${v}`)
                .join(' / ')}
            </span>
          </Show>
          <span class="flex-1" />
          <label class="flex items-center gap-1.5 text-text-muted">
            <input
              type="checkbox"
              checked={showOnlyRecs()}
              onChange={(e) => setShowOnlyRecs(e.currentTarget.checked)}
              class="h-3.5 w-3.5 accent-accent"
            />
            Only show recommended
          </label>
          <button
            type="button"
            disabled={applyAllPending()}
            onClick={() => void applyAllRecommendations()}
            class="rounded-md bg-accent px-3 py-1 text-[11.5px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
            title="Apply every recommended action across all rules. Each becomes a reversible ReviewDecision."
          >
            {applyAllPending()
              ? 'Applying…'
              : `Apply all ${recsResp()!.total_recommended} recommendations`}
          </button>
        </div>
        <Show when={applyAllResult()}>
          <p class="text-[11px] text-text-muted">
            {applyAllResult()}{' '}
            <Show when={applyAllResult()?.startsWith('Applied')}>
              <span>Queue will refresh — configure rules in{' '}
                <button
                  type="button"
                  onClick={() => navigate('/settings?tab=automation')}
                  class="text-accent underline"
                >
                  Automation settings
                </button>{' '}
                to reduce future manual work.
              </span>
            </Show>
          </p>
        </Show>
      </Show>

      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 text-[11px] text-text-muted">
          <button
            type="button"
            onClick={toggleAllFiltered}
            class="rounded-md hairline px-2 py-1 hover:bg-surface-elevated"
          >
            {allFilteredChecked() ? 'Clear all' : 'Select all'}
          </button>
          <span>·</span>
          <span>Group by</span>
          <button
            type="button"
            onClick={() => setGroupBy('none')}
            class={`rounded px-2 py-0.5 ${groupBy() === 'none' ? 'bg-surface-elevated text-text' : 'text-text-muted hover:text-text'}`}
          >
            none
          </button>
          <button
            type="button"
            onClick={() => setGroupBy('type')}
            class={`rounded px-2 py-0.5 ${groupBy() === 'type' ? 'bg-surface-elevated text-text' : 'text-text-muted hover:text-text'}`}
          >
            type
          </button>
        </div>
        <button
          type="button"
          onClick={() => setHelpOpen(true)}
          class="rounded-md hairline px-2 py-1 text-[11px] text-text-muted hover:bg-surface-elevated"
          title="Keyboard shortcuts"
        >
          ? shortcuts
        </button>
      </div>

      <FilterBar
        sort={sort()}
        onSortChange={setSort}
        sortOptions={SORT_OPTIONS}
        activeFilters={activeFilters()}
        filterForm={
          <div class="flex flex-col gap-3">
            <label class="flex flex-col gap-1 text-xs text-text-muted">
              Type
              <select
                value={typeFilter()}
                onChange={(e) => setTypeFilter(e.currentTarget.value)}
                class="h-8 rounded-md border border-border bg-surface px-2 text-sm text-text focus:border-accent focus:outline-none"
              >
                <option value="">All types</option>
                {ALL_TYPES.map((t) => (
                  <option value={t}>{queueTypeLabel(t)}</option>
                ))}
              </select>
            </label>
          </div>
        }
      />

      <Show when={!reviews.loading} fallback={<SkeletonRows rows={6} />}>
        <Show
          when={!reviews.error}
          fallback={
            <ErrorState
              message={
                reviews.error instanceof Error ? reviews.error.message : String(reviews.error)
              }
              onRetry={refetch}
            />
          }
        >
          <Show
            when={groupBy() === 'type'}
            fallback={
              <Table
                items={filteredItems()}
                columns={columns}
                rowKey={(r) => r.id ?? r.queue_item_id}
                onRowClick={(r) => openItem(r)}
                empty={
                  <EmptyState
                    icon={CheckCircle}
                    title="Inbox zero"
                    description="Nothing needs your attention. Take a breath."
                  />
                }
              />
            }
          >
            <Show
              when={filteredItems().length > 0}
              fallback={
                <EmptyState
                  icon={CheckCircle}
                  title="Inbox zero"
                  description="Nothing needs your attention. Take a breath."
                />
              }
            >
              <div class="flex flex-col gap-4">
                <For
                  each={Array.from(
                    filteredItems().reduce<Map<string, RichReviewItem[]>>((acc, r) => {
                      const k = r.queue_item_type ?? 'unknown';
                      const arr = acc.get(k) ?? [];
                      arr.push(r);
                      acc.set(k, arr);
                      return acc;
                    }, new Map()).entries(),
                  )}
                >
                  {([typeKey, items]) => (
                    <section class="flex flex-col gap-2">
                      <header class="flex items-center justify-between gap-2 px-1">
                        <div class="flex items-center gap-2">
                          <Chip variant={queueTypeVariant(typeKey)}>{queueTypeLabel(typeKey)}</Chip>
                          <span class="text-[11px] text-text-subtle">{items.length}</span>
                        </div>
                        <div class="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setChecked((prev) => {
                                const next = new Set(prev);
                                items.forEach((r) => next.add(r.id));
                                return next;
                              });
                            }}
                            class="rounded-md hairline px-2 py-0.5 text-[11px] text-text-muted hover:bg-surface-elevated"
                          >
                            Select group
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              setChecked((prev) => {
                                const next = new Set(prev);
                                items.forEach((r) => {
                                  if (r.actions?.includes('approve')) next.add(r.id);
                                });
                                return next;
                              });
                              await bulkSubmit('approve');
                            }}
                            class="rounded-full bg-[color-mix(in_oklab,rgb(var(--c-success))_14%,transparent)] px-2.5 py-0.5 text-[11px] font-medium text-success hover:bg-[color-mix(in_oklab,rgb(var(--c-success))_22%,transparent)]"
                          >
                            Approve all
                          </button>
                        </div>
                      </header>
                      <Table
                        items={items}
                        columns={columns}
                        rowKey={(r) => r.id ?? r.queue_item_id}
                        onRowClick={(r) => openItem(r)}
                      />
                    </section>
                  )}
                </For>
              </div>
            </Show>
          </Show>
        </Show>
      </Show>

      <SlideOver
        open={selected() !== null}
        onOpenChange={(o) => !o && openItem(null)}
        title="Review item"
        description={selected()?.id}
      >
        <Show when={selected()}>
          {(item) => <ReviewDetail item={item()} onAction={submitAction} pending={pendingActions()} />}
        </Show>
      </SlideOver>

      <Show when={checked().size > 0}>
        <div class="fixed inset-x-0 bottom-4 z-30 flex justify-center pointer-events-none">
          <div class="pointer-events-auto flex items-center gap-2 rounded-full bg-surface-elevated px-4 py-2 hairline shadow-lg">
            <span class="text-[12px] text-text">
              {checked().size} selected
              <Show when={bulkPending()}>
                <span class="ml-2 text-text-muted">
                  · {bulkProgress().done}/{bulkProgress().total}
                </span>
              </Show>
            </span>
            <span class="text-text-subtle">·</span>
            <button
              type="button"
              disabled={bulkPending()}
              onClick={() => void bulkSubmit('approve')}
              class="rounded-full bg-[color-mix(in_oklab,rgb(var(--c-success))_14%,transparent)] px-3 py-1 text-[11px] font-medium text-success hover:bg-[color-mix(in_oklab,rgb(var(--c-success))_22%,transparent)] disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={bulkPending()}
              onClick={() => void bulkSubmit('suppress')}
              class="rounded-full bg-[color-mix(in_oklab,rgb(var(--c-danger))_14%,transparent)] px-3 py-1 text-[11px] font-medium text-danger hover:bg-[color-mix(in_oklab,rgb(var(--c-danger))_22%,transparent)] disabled:opacity-50"
            >
              Suppress
            </button>
            <button
              type="button"
              disabled={bulkPending()}
              onClick={() => void bulkSubmit('mark_stale')}
              class="rounded-full hairline px-3 py-1 text-[11px] font-medium text-text-muted hover:bg-surface disabled:opacity-50"
            >
              Mark stale
            </button>
            <button
              type="button"
              disabled={bulkPending()}
              onClick={() => setChecked(new Set<string>())}
              class="rounded-full px-3 py-1 text-[11px] text-text-subtle hover:text-text disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>
      </Show>

      <Show when={helpOpen()}>
        <div
          class="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
          onClick={() => setHelpOpen(false)}
        >
          <div
            class="flex w-[320px] flex-col gap-2 rounded-lg bg-surface-elevated p-5 hairline shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 class="text-sm font-medium text-text">Keyboard shortcuts</h3>
            <dl class="grid grid-cols-[60px_1fr] gap-x-3 gap-y-1.5 text-[12px]">
              <dt class="font-mono text-text-muted">j / k</dt>
              <dd class="text-text">next / prev item</dd>
              <dt class="font-mono text-text-muted">x</dt>
              <dd class="text-text">toggle selection</dd>
              <dt class="font-mono text-text-muted">a</dt>
              <dd class="text-text">approve focused</dd>
              <dt class="font-mono text-text-muted">s</dt>
              <dd class="text-text">suppress focused</dd>
              <dt class="font-mono text-text-muted">m</dt>
              <dd class="text-text">mark stale focused</dd>
              <dt class="font-mono text-text-muted">enter</dt>
              <dd class="text-text">open inspector</dd>
              <dt class="font-mono text-text-muted">esc</dt>
              <dd class="text-text">close panel</dd>
              <dt class="font-mono text-text-muted">?</dt>
              <dd class="text-text">this help</dd>
            </dl>
            <button
              type="button"
              onClick={() => setHelpOpen(false)}
              class="self-end rounded-md hairline px-3 py-1 text-[11px] text-text-muted hover:bg-surface"
            >
              Close
            </button>
          </div>
        </div>
      </Show>
    </Page>
  );
}

function ReviewDetail(props: {
  item: RichReviewItem;
  onAction: (item: RichReviewItem, a: ReviewAction) => Promise<void>;
  pending: Set<string>;
}): JSX.Element {
  const isPending = (a: ReviewAction): boolean =>
    props.pending.has(`${props.item.id}:${a}`);

  const actions = (): ReviewAction[] => {
    const all: ReviewAction[] = ['approve', 'suppress', 'mark_stale'];
    return all.filter((a) => props.item.actions?.includes(a));
  };

  const headerActions = (
    <div class="flex flex-wrap items-center gap-1.5">
      <For each={actions()}>
        {(action) => (
          <button
            type="button"
            disabled={isPending(action)}
            onClick={() => props.onAction(props.item, action)}
            class={
              action === 'approve'
                ? 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium bg-[color-mix(in_oklab,rgb(var(--c-success))_14%,transparent)] text-success hover:bg-[color-mix(in_oklab,rgb(var(--c-success))_22%,transparent)] disabled:opacity-50 transition-colors'
                : action === 'suppress'
                ? 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium bg-[color-mix(in_oklab,rgb(var(--c-danger))_14%,transparent)] text-danger hover:bg-[color-mix(in_oklab,rgb(var(--c-danger))_22%,transparent)] disabled:opacity-50 transition-colors'
                : 'inline-flex h-6 items-center rounded-full px-2.5 text-[11px] font-medium hairline text-text-muted hover:bg-surface-elevated hover:text-text disabled:opacity-50 transition-colors'
            }
          >
            {isPending(action) ? '…' : action.replace(/_/g, ' ')}
          </button>
        )}
      </For>
    </div>
  );

  if (props.item.object_type === 'memory' && props.item.object_id) {
    const [navId, setNavId] = createSignal(props.item.object_id);
    return (
      <MemoryInspector
        memoryId={navId()}
        onNavigate={setNavId}
        headerActions={headerActions}
      />
    );
  }

  if (props.item.queue_item_type === 'large_diff' || props.item.object_type === 'run') {
    const runId = props.item.object_id;
    const [data] = createResource<{ run: RunRecord; diff: RunDiff | null }>(async () => {
      const [run, diff] = await Promise.all([
        cachedFetch(`run:${runId}`, () => getRun(runId), 60_000),
        cachedFetch(`run-diff:${runId}`, () => getRunDiff(runId), 60_000).catch(() => null),
      ]);
      return { run: run as RunRecord, diff: diff as RunDiff | null };
    });
    return (
      <div class="flex flex-col gap-4 p-5">
        <header class="flex flex-col gap-2">
          <span class="font-mono text-[12.5px] text-text">{runId}</span>
          {headerActions}
          <p class="text-[12.5px] text-text-muted">{props.item.reason}</p>
        </header>
        <Show when={data()}>
          {(d) => (
            <>
              <Show when={asPreview(d().run.summary)}>
                <p class="text-[13px] text-text">{asPreview(d().run.summary)}</p>
              </Show>
              <Show when={d().diff?.diff_text}>
                <DiffView patch={d().diff!.diff_text} language="text" />
              </Show>
            </>
          )}
        </Show>
      </div>
    );
  }

  // Generic fallback inspector
  return (
    <div class="flex flex-col gap-4 p-5">
      <header class="flex flex-col gap-2">
        <span class="font-mono text-[12.5px] text-text">{props.item.object_id}</span>
        {headerActions}
      </header>
      <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
        <dt class="text-text-subtle">Type</dt>
        <dd class="text-text">{queueTypeLabel(props.item.queue_item_type)}</dd>
        <dt class="text-text-subtle">Object</dt>
        <dd class="font-mono text-[11.5px] text-text">{props.item.object_type}</dd>
        <dt class="text-text-subtle">Reason</dt>
        <dd class="text-text">{props.item.reason}</dd>
      </dl>
      <RawFormattedView
        content={JSON.stringify(props.item, null, 2)}
        language="json"
        storageKey="review-raw"
      />
    </div>
  );
}

// Suppress unused-import warning when peek isn't referenced in this file.
void peek;
