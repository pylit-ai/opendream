import { createResource, createSignal, Show, type JSX } from 'solid-js';
import { Dialog } from '@kobalte/core/dialog';
import { Download, Package } from 'lucide-solid';
import { createExport, getExports } from '~/api/client';
import { invalidate } from '~/lib/cache';
import type { ExportItem, ExportsResponse } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { Chip } from '~/components/Chip';
import { SlideOver } from '~/components/SlideOver';
import { EmptyState } from '~/components/EmptyState';
import { LoadingPage } from '~/components/Loading';
import { ErrorState } from '~/components/ErrorState';
import { formatDate } from '~/lib/format';

const FORMAT_OPTIONS = ['json', 'csv'] as const;
type ExportFormat = (typeof FORMAT_OPTIONS)[number];

function formatVariant(f: string | undefined) {
  if (f === 'json') return 'ok' as const;
  if (f === 'csv') return 'neutral' as const;
  return 'neutral' as const;
}

function statusVariant(s: string | undefined) {
  const v = (s ?? '').toLowerCase();
  if (v.includes('done') || v.includes('complete') || v.includes('ok')) return 'ok' as const;
  if (v.includes('pending') || v.includes('process')) return 'warn' as const;
  if (v.includes('fail') || v.includes('error')) return 'danger' as const;
  return 'neutral' as const;
}

function formatSize(bytes: number | undefined): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const COLS: TableColumn<ExportItem>[] = [
  {
    key: 'created',
    header: 'Created',
    render: (item) => (
      <span class="text-xs text-text-muted">{item.created_at ? formatDate(item.created_at) : '—'}</span>
    ),
    width: '120px',
  },
  {
    key: 'format',
    header: 'Format',
    render: (item) => {
      const f = String(item.format ?? '');
      return <Chip variant={formatVariant(f)}>{f || '—'}</Chip>;
    },
    width: '80px',
  },
  {
    key: 'scope',
    header: 'Scope',
    render: (item) => (
      <span class="text-xs">{String(item.scope ?? item.entity_scope ?? item.filter ?? '—')}</span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (item) => {
      const s = String(item.status ?? '');
      return <Chip variant={statusVariant(s)}>{s || '—'}</Chip>;
    },
    width: '100px',
  },
  {
    key: 'size',
    header: 'Size',
    align: 'right',
    render: (item) => (
      <span class="font-mono text-xs text-text-muted">
        {formatSize(item.size as number | undefined)}
      </span>
    ),
    width: '80px',
  },
];

export default function ExportsRoute(): JSX.Element {
  const [selected, setSelected] = createSignal<ExportItem | null>(null);
  const [createOpen, setCreateOpen] = createSignal(false);
  const [format, setFormat] = createSignal<ExportFormat>('json');
  const [scope, setScope] = createSignal('');
  const [creating, setCreating] = createSignal(false);
  const [createError, setCreateError] = createSignal('');

  const [data, { refetch }] = createResource<ExportsResponse>(getExports);

  const items = (): ExportItem[] => data()?.items ?? [];

  async function handleCreate() {
    setCreating(true);
    setCreateError('');
    try {
      await createExport({ format: format(), scope: scope() || undefined });
      setCreateOpen(false);
      setScope('');
      invalidate('exports');
      refetch();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <Page
      title="Exports"
      actions={
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          <Download size={12} />
          New export
        </button>
      }
    >
      <Show when={data.loading}>
        <LoadingPage />
      </Show>
      <Show when={data.error}>
        <ErrorState
          message={data.error instanceof Error ? data.error.message : String(data.error)}
          onRetry={refetch}
        />
      </Show>
      <Show when={!data.loading && !data.error}>
        <Table
          items={items()}
          columns={COLS}
          rowKey={(item, i) => String(item.id ?? i)}
          onRowClick={setSelected}
          empty={
            <EmptyState
              icon={Package}
              title="No exports yet"
              description="Create one to download memory data as JSON or CSV."
              action={
                <button
                  type="button"
                  onClick={() => setCreateOpen(true)}
                  class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
                >
                  Create your first export
                </button>
              }
            />
          }
        />
      </Show>

      {/* Detail slide-over */}
      <SlideOver
        open={selected() !== null}
        onOpenChange={(o) => { if (!o) setSelected(null); }}
        title="Export details"
      >
        <Show when={selected()}>
          {(item) => (
            <div class="flex flex-col gap-4 p-4">
              <div class="flex flex-col gap-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-text-muted">Created</span>
                  <span>{item().created_at ? formatDate(item().created_at!) : '—'}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-muted">Format</span>
                  <Chip variant={formatVariant(String(item().format ?? ''))}>{String(item().format ?? '—')}</Chip>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-muted">Status</span>
                  <Chip variant={statusVariant(String(item().status ?? ''))}>{String(item().status ?? '—')}</Chip>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-muted">Size</span>
                  <span class="font-mono text-xs">{formatSize(item().size as number | undefined)}</span>
                </div>
              </div>
              {(() => {
                const dlUrl = String(item().download_url ?? item().url ?? '');
                return dlUrl ? (
                  <a
                    href={dlUrl}
                    download=""
                    class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
                  >
                    <Download size={12} />
                    Download
                  </a>
                ) : null;
              })()}
            </div>
          )}
        </Show>
      </SlideOver>

      {/* Create dialog */}
      <Dialog open={createOpen()} onOpenChange={setCreateOpen} modal>
        <Dialog.Portal>
          <Dialog.Overlay class="overlay-fade fixed inset-0 z-40 bg-black/40 backdrop-blur-[3px]" />
          <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
            <Dialog.Content class="palette-enter w-full max-w-md rounded-xl bg-surface p-6 hairline shadow-[var(--shadow-elevated)]">
              <Dialog.Title class="mb-4 text-sm font-semibold text-text">New export</Dialog.Title>

              <div class="flex flex-col gap-3">
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-text-muted">Format</label>
                  <div class="flex gap-1">
                    {FORMAT_OPTIONS.map((f) => (
                      <button
                        type="button"
                        onClick={() => setFormat(f)}
                        class={`flex-1 rounded-md px-2 py-1.5 text-xs transition-colors duration-150 ${
                          format() === f
                            ? 'bg-surface-elevated text-text hairline'
                            : 'text-text-muted hover:text-text'
                        }`}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-text-muted">Scope (optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. agent_id or memory_type…"
                    value={scope()}
                    onInput={(e) => setScope(e.currentTarget.value)}
                    class="w-full rounded border border-border bg-surface px-2 py-1.5 text-xs text-text placeholder-text-subtle focus:border-accent focus:outline-none"
                  />
                </div>
                <Show when={createError()}>
                  <p class="text-xs text-danger">{createError()}</p>
                </Show>
              </div>

              <div class="mt-4 flex justify-end gap-2">
                <Dialog.CloseButton class="rounded px-3 py-1.5 text-xs text-text-muted hover:text-text">
                  Cancel
                </Dialog.CloseButton>
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={creating()}
                  class="rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                >
                  {creating() ? 'Creating…' : 'Create'}
                </button>
              </div>
            </Dialog.Content>
          </div>
        </Dialog.Portal>
      </Dialog>
    </Page>
  );
}
