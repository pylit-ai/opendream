import { For, Show, createResource, createSignal, type JSX } from 'solid-js';
import { createAnnotation, getMemory, getMemoryLineage } from '~/api/client';
import type { MemoryLineage, MemoryRecord } from '~/api/types';
import { cachedFetch, invalidate } from '~/lib/cache';
import { Chip, type ChipVariant } from './Chip';
import { CopyButton } from './CopyButton';
import { LoadingPage } from './Loading';
import { formatDateLong } from '~/lib/format';
import { RawFormattedView } from './RawFormattedView';
import { MemoryTypeChip } from './MemoryTypeChip';
import { helpForMemoryStatus } from '~/lib/observeGlossary';
import { stripMemoryPrefix } from '~/lib/memoryPresentation';

export interface MemoryInspectorProps {
  memoryId: string;
  onNavigate?: (newId: string) => void;
  /** Header action area (e.g. Approve / Suppress buttons in Reviews). */
  headerActions?: JSX.Element;
}

function asText(v: unknown): string | undefined {
  if (v == null) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return undefined;
  }
}

function statusVariant(s: string | undefined): ChipVariant {
  const v = (s ?? '').toLowerCase();
  if (v.includes('durable') || v.includes('active')) return 'ok';
  if (v.includes('contested') || v.includes('learned')) return 'warn';
  if (v.includes('pruned') || v.includes('rejected') || v.includes('suppress')) return 'danger';
  return 'neutral';
}

interface LineageEntry {
  id: string;
  preview?: string;
}

function asLineageList(value: unknown): LineageEntry[] {
  if (!Array.isArray(value)) return [];
  const out: LineageEntry[] = [];
  for (const raw of value) {
    if (typeof raw === 'string') {
      out.push({ id: raw });
    } else if (raw && typeof raw === 'object') {
      const r = raw as { memory_id?: string; id?: string; summary?: string; title?: string };
      const id = r.memory_id ?? r.id;
      if (id) out.push({ id, preview: asText(r.summary) ?? asText(r.title) });
    }
  }
  return out;
}

/**
 * Full-fidelity memory inspector for the SlideOver / Reviews / Memories surfaces.
 * Resolves the memory record first, then lets slower lineage data fill in
 * progressively so a heavy graph query does not hide the core memory.
 */
export function MemoryInspector(props: MemoryInspectorProps): JSX.Element {
  const [memory, { refetch: refetchMemory }] = createResource<MemoryRecord | null, string>(
    () => props.memoryId,
    async (id) => {
      if (!id) return null;
      return cachedFetch(`memory:${id}`, () => getMemory(id), 60_000);
    },
  );
  const [lineage, { refetch: refetchLineage }] = createResource<MemoryLineage | null, string>(
    () => props.memoryId,
    async (id) => {
      if (!id) return null;
      return cachedFetch(`memory-lineage:${id}`, () => getMemoryLineage(id), 60_000).catch(
        () => null,
      );
    },
  );
  const refetchAll = (): void => {
    void refetchMemory();
    void refetchLineage();
  };

  return (
    <div class="flex flex-col gap-5 p-5">
      <header class="flex flex-col gap-2">
        <div class="flex items-start gap-2">
          <span
            class="flex-1 break-all font-mono text-[12.5px] text-text"
            title={props.memoryId}
          >
            {props.memoryId}
          </span>
          <CopyButton value={props.memoryId} label="Copy memory ID" />
        </div>
        <Show when={props.headerActions}>{props.headerActions}</Show>
      </header>

      <Show
        when={!memory.loading || memory()}
        fallback={
          <LoadingPage
            compact
            label="Loading memory"
            detail={props.memoryId}
          />
        }
      >
        <Show when={memory.error}>
          <p class="text-[12.5px] text-danger">
            {memory.error instanceof Error ? memory.error.message : 'Failed to load memory.'}
          </p>
        </Show>
        <Show when={memory()}>
          {(d) => {
            const m = d();
            const lin = lineage();
            const supersedes = asLineageList(
              (m as { supersedes?: unknown }).supersedes ?? lin?.supersedes,
            );
            const conflictsWith = asLineageList(
              (m as { conflicts_with?: unknown }).conflicts_with ?? lin?.conflicts_with,
            );
            const supersededBy = asLineageList(
              (m as { superseded_by?: unknown }).superseded_by,
            );
            const ancestors = asLineageList(lin?.ancestors);
            const descendants = asLineageList(lin?.descendants);
            const sourcePaths = (m as { source_paths?: string[] }).source_paths ?? [];
            const reportingAgents =
              (m as { reporting_agents?: Array<{ agent_label?: string; agent_id?: string }> })
                .reporting_agents ?? [];

            return (
              <>
                <div class="flex flex-wrap items-center gap-1.5">
                  <Chip variant={statusVariant(m.status)} title={helpForMemoryStatus(m.status)}>
                    {m.status ?? 'unknown'}
                  </Chip>
                  <Show when={m.type}>
                    <MemoryTypeChip type={m.type} />
                  </Show>
                  <Show when={typeof m.confidence === 'number'}>
                    <Chip
                      variant="accent"
                      title="Confidence is OpenDream's estimate that this memory is correct and still useful."
                    >
                      conf {(m.confidence ?? 0).toFixed(2)}
                    </Chip>
                  </Show>
                  <Show when={typeof m.salience === 'number'}>
                    <Chip
                      variant="neutral"
                      title="Salience is the retrieval priority signal: higher values make a memory more likely to be surfaced."
                    >
                      sal {(m.salience ?? 0).toFixed(2)}
                    </Chip>
                  </Show>
                </div>

                <Show when={asText(m.title)}>
                  <h3 class="text-[15px] font-medium tracking-tight text-text">
                    {stripMemoryPrefix(asText(m.title), m.type)}
                  </h3>
                </Show>

                <Show when={asText(m.summary)}>
                  <p class="text-[13px] leading-relaxed text-text">
                    {stripMemoryPrefix(asText(m.summary), m.type)}
                  </p>
                </Show>

                <Show when={asText(m.body)}>
                  <section class="flex flex-col gap-1">
                    <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                      Body
                    </h4>
                    <RawFormattedView
                      content={asText(m.body) ?? ''}
                      language="auto"
                      storageKey="memory-body"
                    />
                  </section>
                </Show>

                <section class="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                  <dt class="text-text-subtle">Scope</dt>
                  <dd class="font-mono text-[11.5px] text-text">{m.scope ?? '—'}</dd>
                  <dt class="text-text-subtle">Agent</dt>
                  <dd class="font-mono text-[11.5px] text-text">
                    <Show
                      when={reportingAgents.length > 0}
                      fallback={<>{m.agent_id ?? '—'}</>}
                    >
                      {reportingAgents
                        .map((a) => a.agent_label ?? a.agent_id ?? '?')
                        .join(', ')}
                    </Show>
                  </dd>
                  <Show when={(m as { reporting_agent_label?: string }).reporting_agent_label}>
                    <dt class="text-text-subtle">Adapter</dt>
                    <dd class="font-mono text-[11.5px] text-text-muted">
                      {(m as { reporting_agent_label?: string }).reporting_agent_label}
                    </dd>
                  </Show>
                  <dt class="text-text-subtle">Created</dt>
                  <dd class="text-[11.5px] text-text">
                    {m.created_at ? formatDateLong(m.created_at) : '—'}
                  </dd>
                  <dt class="text-text-subtle">Updated</dt>
                  <dd class="text-[11.5px] text-text">
                    {m.updated_at ? formatDateLong(m.updated_at) : '—'}
                  </dd>
                  <Show
                    when={(m as unknown as { last_accessed_at?: string }).last_accessed_at}
                  >
                    <dt class="text-text-subtle">Last accessed</dt>
                    <dd class="text-[11.5px] text-text">
                      {formatDateLong(
                        (m as unknown as { last_accessed_at: string }).last_accessed_at,
                      )}
                    </dd>
                  </Show>
                  <Show when={(m as unknown as { valid_from?: string }).valid_from}>
                    <dt class="text-text-subtle">Valid from</dt>
                    <dd class="text-[11.5px] text-text">
                      {formatDateLong((m as unknown as { valid_from: string }).valid_from)}
                    </dd>
                  </Show>
                  <Show when={(m as unknown as { valid_to?: string | null }).valid_to}>
                    <dt class="text-text-subtle">Valid to</dt>
                    <dd class="text-[11.5px] text-text">
                      {formatDateLong((m as unknown as { valid_to: string }).valid_to)}
                    </dd>
                  </Show>
                  <Show when={typeof (m as { access_count?: number }).access_count === 'number'}>
                    <dt class="text-text-subtle">Accesses</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {(m as { access_count?: number }).access_count}
                    </dd>
                  </Show>
                  <Show
                    when={typeof (m as { retrieval_frequency?: number }).retrieval_frequency === 'number'}
                  >
                    <dt class="text-text-subtle">Retrievals</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {(m as { retrieval_frequency?: number }).retrieval_frequency}
                    </dd>
                  </Show>
                  <Show
                    when={typeof (m as { source_count?: number }).source_count === 'number'}
                  >
                    <dt class="text-text-subtle">Sources</dt>
                    <dd class="font-mono text-[11.5px] text-text">
                      {(m as { source_count?: number }).source_count}
                    </dd>
                  </Show>
                  <Show when={sourcePaths.length > 0}>
                    <dt class="text-text-subtle">Source paths</dt>
                    <dd class="flex flex-col gap-0.5 font-mono text-[11px] text-text-muted">
                      <For each={sourcePaths.slice(0, 5)}>
                        {(p) => <span class="truncate" title={p}>{p}</span>}
                      </For>
                    </dd>
                  </Show>
                  <Show
                    when={
                      Array.isArray((m as { source_event_ids?: string[] }).source_event_ids) &&
                      ((m as { source_event_ids?: string[] }).source_event_ids ?? []).length > 0
                    }
                  >
                    <dt class="text-text-subtle">Source events</dt>
                    <dd class="flex flex-col gap-0.5 font-mono text-[11px] text-text-muted">
                      <For
                        each={(m as { source_event_ids?: string[] }).source_event_ids ?? []}
                      >
                        {(eid) => <span class="truncate">{eid}</span>}
                      </For>
                    </dd>
                  </Show>
                </section>

                <section class="flex flex-col gap-2">
                  <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                    Annotations ·{' '}
                    {((m as { annotations?: unknown[] }).annotations ?? []).length}
                  </h4>
                  <Show
                    when={
                      Array.isArray((m as { annotations?: unknown[] }).annotations) &&
                      ((m as { annotations?: unknown[] }).annotations ?? []).length > 0
                    }
                  >
                    <RawFormattedView
                      content={JSON.stringify(
                        (m as { annotations?: unknown[] }).annotations ?? [],
                        null,
                        2,
                      )}
                      language="json"
                      storageKey="memory-annotations"
                    />
                  </Show>
                  <AnnotationComposer
                    memoryId={props.memoryId}
                    onCreated={() => {
                      invalidate(`memory:${props.memoryId}`);
                      invalidate(`memory-lineage:${props.memoryId}`);
                      refetchAll();
                    }}
                  />
                </section>

                <Show
                  when={
                    Array.isArray(
                      (m as { manual_reviews?: unknown[] }).manual_reviews,
                    ) &&
                    ((m as { manual_reviews?: unknown[] }).manual_reviews ?? []).length > 0
                  }
                >
                  <section class="flex flex-col gap-1">
                    <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                      Manual reviews
                    </h4>
                    <RawFormattedView
                      content={JSON.stringify(
                        (m as { manual_reviews?: unknown[] }).manual_reviews ?? [],
                        null,
                        2,
                      )}
                      language="json"
                      storageKey="memory-reviews"
                    />
                  </section>
                </Show>

                <Show when={lineage.loading}>
                  <section class="flex flex-col gap-2">
                    <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                      Lineage
                    </h4>
                    <LoadingPage
                      compact
                      label={
                        supersedes.length +
                          conflictsWith.length +
                          supersededBy.length +
                          ancestors.length +
                          descendants.length >
                        0
                          ? 'Refreshing lineage'
                          : 'Loading lineage'
                      }
                      detail="Checking ancestor, descendant, and conflict links."
                    />
                  </section>
                </Show>

                <Show when={lineage.error}>
                  <p class="text-[12.5px] text-text-muted">
                    Lineage unavailable:{' '}
                    {lineage.error instanceof Error ? lineage.error.message : 'request failed'}
                  </p>
                </Show>

                <Show
                  when={
                    supersedes.length +
                      conflictsWith.length +
                      supersededBy.length +
                      ancestors.length +
                      descendants.length >
                    0
                  }
                >
                  <section class="flex flex-col gap-3">
                    <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                      Lineage
                    </h4>
                    <LineageBlock
                      label="Supersedes"
                      entries={supersedes}
                      onNav={props.onNavigate}
                    />
                    <LineageBlock
                      label="Superseded by"
                      entries={supersededBy}
                      onNav={props.onNavigate}
                    />
                    <LineageBlock
                      label="Conflicts with"
                      entries={conflictsWith}
                      onNav={props.onNavigate}
                    />
                    <LineageBlock
                      label="Ancestors"
                      entries={ancestors}
                      onNav={props.onNavigate}
                    />
                    <LineageBlock
                      label="Descendants"
                      entries={descendants}
                      onNav={props.onNavigate}
                    />
                  </section>
                </Show>

                <section class="flex flex-col gap-1">
                  <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                    Raw record
                  </h4>
                  <RawFormattedView
                    content={JSON.stringify(m, null, 2)}
                    language="json"
                    storageKey="memory-raw"
                    defaultMode="raw"
                  />
                </section>
              </>
            );
          }}
        </Show>
        <Show when={!memory() && !memory.loading && !memory.error}>
          <p class="text-[12.5px] text-text-muted">Memory not found.</p>
        </Show>
      </Show>
    </div>
  );
}

function AnnotationComposer(props: {
  memoryId: string;
  onCreated: () => void;
}): JSX.Element {
  const [open, setOpen] = createSignal(false);
  const [actor, setActor] = createSignal('operator');
  const [label, setLabel] = createSignal('note');
  const [note, setNote] = createSignal('');
  const [submitting, setSubmitting] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  const submit = async (): Promise<void> => {
    if (!note().trim()) {
      setError('Note required');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createAnnotation({
        object_type: 'memory',
        object_id: props.memoryId,
        actor: actor().trim() || 'operator',
        label: label().trim() || 'note',
        note: note().trim(),
      });
      setNote('');
      setOpen(false);
      props.onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div class="flex flex-col gap-2">
      <Show
        when={open()}
        fallback={
          <button
            type="button"
            onClick={() => setOpen(true)}
            class="row-hover self-start rounded-md hairline px-3 py-1.5 text-[12px] text-text hover:border-accent/40 hover:bg-surface-elevated"
          >
            + Add annotation
          </button>
        }
      >
        <form
          class="flex flex-col gap-2 rounded-md hairline bg-surface-elevated p-3"
          onSubmit={(e) => { e.preventDefault(); void submit(); }}
        >
          <div class="grid grid-cols-2 gap-2">
            <label class="flex flex-col gap-1 text-[10px] uppercase tracking-[0.06em] text-text-subtle">
              Actor
              <input
                type="text"
                value={actor()}
                onInput={(e) => setActor(e.currentTarget.value)}
                disabled={submitting()}
                class="h-7 rounded-md border border-border bg-surface px-2 text-[12px] text-text focus:border-accent focus:outline-none"
              />
            </label>
            <label class="flex flex-col gap-1 text-[10px] uppercase tracking-[0.06em] text-text-subtle">
              Label
              <input
                type="text"
                value={label()}
                onInput={(e) => setLabel(e.currentTarget.value)}
                disabled={submitting()}
                placeholder="e.g. note, flag, audit"
                class="h-7 rounded-md border border-border bg-surface px-2 text-[12px] text-text focus:border-accent focus:outline-none"
              />
            </label>
          </div>
          <label class="flex flex-col gap-1 text-[10px] uppercase tracking-[0.06em] text-text-subtle">
            Note
            <textarea
              value={note()}
              onInput={(e) => setNote(e.currentTarget.value)}
              disabled={submitting()}
              rows={3}
              placeholder="Why is this memory worth annotating?"
              class="resize-y rounded-md border border-border bg-surface px-2 py-1.5 text-[12.5px] text-text focus:border-accent focus:outline-none"
            />
          </label>
          <Show when={error()}>
            <p class="text-[11.5px] text-danger">{error()}</p>
          </Show>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setError(null);
              }}
              disabled={submitting()}
              class="rounded-md hairline px-3 py-1 text-[12px] text-text-muted hover:bg-surface"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting() || !note().trim()}
              class="rounded-md bg-accent px-3 py-1 text-[12px] font-medium text-accent-fg disabled:opacity-50"
            >
              {submitting() ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </Show>
    </div>
  );
}

function LineageBlock(props: {
  label: string;
  entries: LineageEntry[];
  onNav?: (id: string) => void;
}): JSX.Element {
  return (
    <Show when={props.entries.length > 0}>
      <div class="flex flex-col gap-1">
        <span class="text-[10px] uppercase tracking-[0.06em] text-text-subtle">
          {props.label} · {props.entries.length}
        </span>
        <div class="flex flex-col gap-1">
          <For each={props.entries.slice(0, 12)}>
            {(entry) => (
              <button
                type="button"
                aria-label={`Navigate to ${entry.id}${entry.preview ? `: ${entry.preview}` : ''}`}
                onClick={() => props.onNav?.(entry.id)}
                class="row-hover flex flex-col items-start gap-0.5 rounded-md hairline bg-surface px-2.5 py-1.5 text-left transition-colors hover:border-accent/40 hover:bg-surface-elevated"
              >
                <span class="font-mono text-[11.5px] text-text-muted">{entry.id}</span>
                <Show when={entry.preview}>
                  <span class="line-clamp-1 text-[11.5px] text-text-muted">
                    {entry.preview}
                  </span>
                </Show>
              </button>
            )}
          </For>
        </div>
      </div>
    </Show>
  );
}
