import { createResource, createSignal, For, Show, type JSX } from 'solid-js';
import { FileText } from 'lucide-solid';
import { getContext, getSessions } from '~/api/client';
import { cachedFetch } from '~/lib/cache';
import type { ContextRecord } from '~/api/types';
import { Page } from '~/components/Page';
import { EmptyState } from '~/components/EmptyState';
import { LoadingPage } from '~/components/Loading';
import { ErrorState } from '~/components/ErrorState';
import { RawFormattedView } from '~/components/RawFormattedView';
import { formatDate, formatDateLong, formatNumber } from '~/lib/format';
import { cn } from '~/lib/cn';

interface ContextEntry {
  context_id: string;
  created_at?: string;
  character_count?: number;
  query?: string;
}

/** Derive context IDs from sessions timeline events. */
function extractContextEntries(sessions: { items: unknown[] }): ContextEntry[] {
  const seen = new Set<string>();
  const entries: ContextEntry[] = [];
  for (const session of sessions.items) {
    const timeline = (session as { timeline?: Array<{
      kind?: string;
      object_id?: string;
      label?: string;
      payload?: {
        context_id?: string;
        created_at?: string;
        character_count?: number;
        assembled_text?: string;
      };
    }> }).timeline ?? [];
    for (const ev of timeline) {
      // only pick up actual context assembly events
      if (ev.kind !== 'memory.context.assembled') continue;
      const ctxId = ev.payload?.context_id ?? ev.object_id;
      if (!ctxId || seen.has(ctxId)) continue;
      seen.add(ctxId);
      // extract query from assembled_text first line
      const text = ev.payload?.assembled_text ?? '';
      const queryMatch = text.match(/Query:\s*(.+)/);
      entries.push({
        context_id: ctxId,
        created_at: ev.payload?.created_at,
        character_count: ev.payload?.character_count,
        query: queryMatch?.[1]?.trim(),
      });
    }
  }
  return entries.slice(0, 50);
}

export default function ContextRoute(): JSX.Element {
  const [selectedId, setSelectedId] = createSignal<string | null>(null);

  const [sessionsData, { refetch: refetchSessions }] = createResource(() =>
    cachedFetch('sessions', getSessions, 15_000),
  );

  const contextEntries = (): ContextEntry[] => {
    const s = sessionsData();
    if (!s) return [];
    return extractContextEntries(s as { items: unknown[] });
  };

  const [contextDetail] = createResource<ContextRecord | null, string | null>(
    selectedId,
    async (id) => {
      if (!id) return null;
      return cachedFetch(`context:${id}`, () => getContext(id), 60_000).catch(() => null);
    },
  );

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
      <Show when={!sessionsData.loading} fallback={<LoadingPage />}>
        <Show
          when={!sessionsData.error}
          fallback={
            <ErrorState
              message={
                sessionsData.error instanceof Error
                  ? sessionsData.error.message
                  : String(sessionsData.error)
              }
              onRetry={refetchSessions}
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
                      onClick={() => setSelectedId(entry.context_id)}
                      class={cn(
                        'hairline-b row-hover flex flex-col gap-0.5 px-4 py-3 text-left text-xs',
                        selectedId() === entry.context_id
                          ? 'bg-[color-mix(in_oklab,rgb(var(--c-accent))_10%,transparent)] text-text'
                          : 'hover:bg-surface-elevated',
                      )}
                    >
                      <span class="font-mono text-text-muted truncate">{entry.context_id}</span>
                      <Show when={entry.query}>
                        <span class="truncate text-text-subtle">{entry.query}</span>
                      </Show>
                      <div class="flex items-center gap-2 text-text-subtle">
                        <Show when={entry.created_at}>
                          <span>{formatDate(entry.created_at!)}</span>
                        </Show>
                        <Show when={entry.character_count}>
                          <span class="tabular-nums">{formatNumber(entry.character_count!)} chars</span>
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
                    <LoadingPage />
                  </Show>
                  <Show when={!contextDetail.loading && contextDetail()}>
                    {(d) => (
                      <div class="flex flex-col gap-3">
                        <dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-sm">
                          <dt class="text-text-muted">Context ID</dt>
                          <dd class="font-mono text-xs text-text">{d().context_id}</dd>
                          <Show when={(d() as { created_at?: string }).created_at}>
                            <dt class="text-text-muted">Created</dt>
                            <dd class="text-xs">
                              {formatDateLong((d() as unknown as { created_at: string }).created_at)}
                            </dd>
                          </Show>
                        </dl>
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
                              <Show when={selected.length > 0}>
                                <section class="flex flex-col gap-1">
                                  <h4 class="text-2xs uppercase tracking-wide text-text-subtle">
                                    Selected memories · {selected.length}
                                  </h4>
                                  <div class="flex flex-col gap-1">
                                    <For each={selected}>
                                      {(id) => (
                                        <div class="rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px]">
                                          <span class="font-mono text-text">{id}</span>
                                        </div>
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
                                        <div class="flex items-center justify-between gap-2 rounded-md hairline bg-surface-elevated px-3 py-1.5 text-[12px]">
                                          <span class="font-mono text-text">{o.id}</span>
                                          <span class="text-text-subtle">{o.reason || '—'}</span>
                                        </div>
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
