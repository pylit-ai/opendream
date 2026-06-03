import { createResource, createSignal, For, Show, type JSX } from 'solid-js';
import { Layers } from 'lucide-solid';
import { getWorkspaces, inspectWorkspace } from '~/api/client';
import type { WorkspaceDashboard, WorkspaceEntry, WorkspaceInspectResponse } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { Chip } from '~/components/Chip';
import { EmptyState } from '~/components/EmptyState';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { SlideOver } from '~/components/SlideOver';
import { CopyButton } from '~/components/CopyButton';
import { StatStrip, type Stat } from '~/components/StatStrip';
import { formatDate, formatDateLong, formatNumber, truncateMiddle } from '~/lib/format';
import { cachedFetch } from '~/lib/cache';

function statusVariant(active: boolean | undefined) {
  return active ? ('ok' as const) : ('neutral' as const);
}

function workspacePath(item: WorkspaceEntry): string {
  return String(
    item.path ??
      (item as { workspace_path?: string }).workspace_path ??
      (item as { workspace?: string }).workspace ??
      (item as { id?: string }).id ??
      '—',
  );
}

export default function WorkspacesRoute(): JSX.Element {
  const [data, { refetch }] = createResource<WorkspaceDashboard>(() =>
    cachedFetch('workspaces', getWorkspaces, 30_000),
  );
  const [selected, setSelected] = createSignal<WorkspaceEntry | null>(null);

  const summaryStats = (): Stat[] => {
    const v = data() as
      | (WorkspaceDashboard & {
          summary?: { total?: number; ok?: number; with_service?: number; stale?: number; missing?: number; broken?: number };
        })
      | undefined;
    const list = items();
    const s = v?.summary;
    const count = (kind: string) =>
      list.filter((e) => (e as { status_kind?: string }).status_kind === kind).length;
    const total = s?.total ?? list.length;
    const ok = s?.ok ?? count('ok');
    const withService = s?.with_service ??
      list.filter((e) => Boolean((e as { service_state_summary?: string }).service_state_summary)).length;
    const degraded =
      (s?.stale ?? count('stale')) + (s?.missing ?? count('missing')) + (s?.broken ?? count('broken'));
    return [
      { label: 'Total', value: total },
      { label: 'Healthy', value: ok, tone: ok > 0 ? 'ok' : 'default' },
      { label: 'With service', value: withService },
      { label: 'Degraded', value: degraded, tone: degraded > 0 ? 'warn' : 'default' },
    ];
  };

  const [showTemp, setShowTemp] = createSignal(false);

  const isTempPath = (p: string): boolean =>
    p.startsWith('/private/var/folders/') ||
    p.startsWith('/private/tmp/') ||
    p.startsWith('/tmp/') ||
    p.startsWith('/var/folders/') ||
    /\/tmp[a-z0-9_]+\/workspace$/i.test(p);

  const allItems = (): WorkspaceEntry[] => {
    const v = data();
    return (
      ((v as { items?: WorkspaceEntry[] } | undefined)?.items as WorkspaceEntry[] | undefined) ??
      ((v as { entries?: WorkspaceEntry[] } | undefined)?.entries as WorkspaceEntry[] | undefined) ??
      []
    );
  };

  const items = (): WorkspaceEntry[] => {
    if (showTemp()) return allItems();
    return allItems().filter((e) => !isTempPath(workspacePath(e)));
  };

  const hiddenCount = (): number => allItems().length - items().length;

  const cols: TableColumn<WorkspaceEntry>[] = [
    {
      key: 'name',
      header: 'Name',
      width: '180px',
      render: (item) => (
        <span class="font-mono text-[12.5px] text-text">
          {(item as { workspace_name?: string }).workspace_name ?? '—'}
        </span>
      ),
    },
    {
      key: 'path',
      header: 'Path',
      render: (item) => {
        const p = workspacePath(item);
        return (
          <span title={p} class="font-mono text-xs tracking-[-0.01em] text-text-muted">
            {truncateMiddle(p, 64)}
          </span>
        );
      },
    },
    {
      key: 'last_activity',
      header: 'Last seen',
      render: (item) => {
        const ts =
          item.last_activity ??
          (item as { last_seen_at?: string }).last_seen_at ??
          item.last_seen ??
          item.updated_at;
        return (
          <span class="text-xs text-text-muted">
            {ts ? formatDate(ts as string) : '—'}
          </span>
        );
      },
      width: '130px',
    },
    {
      key: 'runs',
      header: 'Runs',
      align: 'right',
      numeric: true,
      render: (item) => (
        <span class="font-mono text-xs text-text-muted">
          {typeof item['run_count'] === 'number'
            ? formatNumber(item['run_count'] as number)
            : '—'}
        </span>
      ),
      width: '90px',
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => {
        const active = Boolean(item['active']);
        const kind = (item as { status_kind?: string }).status_kind;
        return (
          <Chip variant={statusVariant(active)}>
            {active ? 'active' : kind ?? String(item['status'] ?? 'inactive')}
          </Chip>
        );
      },
      width: '110px',
    },
  ];

  return (
    <Page title="Workspaces" subtitle="Switch active observability scope">
      <Show when={data.loading}>
        <SkeletonRows rows={4} />
      </Show>
      <Show when={data.error}>
        <ErrorState
          message={data.error instanceof Error ? data.error.message : String(data.error)}
          onRetry={refetch}
        />
      </Show>
      <Show when={!data.loading && !data.error}>
        <StatStrip stats={summaryStats()} />
        <Show when={hiddenCount() > 0 || showTemp()}>
          <div class="flex items-center justify-between gap-2 px-1 text-[11px] text-text-muted">
            <span>
              <Show when={hiddenCount() > 0 && !showTemp()}>
                {hiddenCount()} tempdir workspace
                {hiddenCount() === 1 ? '' : 's'} hidden (test fixtures, /tmp/* and /private/var/folders)
              </Show>
              <Show when={showTemp()}>Showing all workspaces including tempdirs</Show>
            </span>
            <button
              type="button"
              onClick={() => setShowTemp(!showTemp())}
              class="rounded-md hairline px-2 py-1 hover:bg-surface-elevated"
            >
              {showTemp() ? 'Hide tempdir' : 'Show tempdir'}
            </button>
          </div>
        </Show>
        <Table
          items={items()}
          columns={cols}
          rowKey={(item, i) => String(item.path ?? item.id ?? i)}
          onRowClick={(w) => setSelected(w)}
          empty={
            <EmptyState
              icon={Layers}
              title="No workspaces"
              description="Workspaces appear here when an observability scope is active."
            />
          }
        />
      </Show>

      <SlideOver
        open={selected() !== null}
        onOpenChange={(o) => !o && setSelected(null)}
        title="Workspace detail"
        description={
          selected()
            ? (selected() as { workspace_name?: string }).workspace_name ?? workspacePath(selected()!)
            : undefined
        }
      >
        <Show when={selected()}>
          {(w) => <WorkspaceDetail entry={w()} />}
        </Show>
      </SlideOver>
    </Page>
  );
}

function WorkspaceDetail(props: { entry: WorkspaceEntry }): JSX.Element {
  const path = workspacePath(props.entry);
  const [inspect] = createResource<WorkspaceInspectResponse | null>(async () => {
    return (await cachedFetch(
      `workspace:${path}`,
      () => inspectWorkspace(path),
      60_000,
    ).catch(() => null)) as WorkspaceInspectResponse | null;
  });

  const detail = (): WorkspaceEntry => {
    const v = inspect();
    if (v && (v as { status?: string }).status === 'ok' && 'entry' in (v as object)) {
      return (v as { entry: WorkspaceEntry }).entry;
    }
    return props.entry;
  };

  return (
    <div class="flex flex-col gap-5 p-5">
      <header class="flex items-start gap-2">
        <span
          class="flex-1 break-all font-mono text-[12.5px] text-text"
          title={path}
        >
          {path}
        </span>
        <CopyButton value={path} label="Copy path" />
      </header>

      <Show when={!inspect.loading} fallback={<SkeletonRows rows={3} />}>
        <section class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
          <dt class="text-text-subtle">Name</dt>
          <dd class="font-mono text-[11.5px] text-text">
            {(detail() as { workspace_name?: string }).workspace_name ?? '—'}
          </dd>
          <dt class="text-text-subtle">Status</dt>
          <dd class="text-text">
            {(detail() as { status_kind?: string }).status_kind ?? '—'}
          </dd>
          <dt class="text-text-subtle">First seen</dt>
          <dd class="text-[11.5px] text-text">
            <Show
              when={(detail() as { first_seen_at?: string }).first_seen_at}
              fallback="—"
            >
              {formatDateLong((detail() as { first_seen_at: string }).first_seen_at)}
            </Show>
          </dd>
          <dt class="text-text-subtle">Last seen</dt>
          <dd class="text-[11.5px] text-text">
            <Show
              when={(detail() as { last_seen_at?: string }).last_seen_at}
              fallback="—"
            >
              {formatDateLong((detail() as { last_seen_at: string }).last_seen_at)}
            </Show>
          </dd>
          <dt class="text-text-subtle">Activation</dt>
          <dd class="text-[11.5px] text-text">
            {(detail() as { activation_state_summary?: string }).activation_state_summary ?? '—'}
          </dd>
          <dt class="text-text-subtle">Service</dt>
          <dd class="text-[11.5px] text-text">
            {(detail() as { service_state_summary?: string }).service_state_summary ?? '—'}
          </dd>
          <dt class="text-text-subtle">Semantic</dt>
          <dd class="text-[11.5px] text-text">
            {(detail() as { semantic_state_summary?: string }).semantic_state_summary ?? '—'}
          </dd>
          <Show
            when={Array.isArray((detail() as { notes?: string[] }).notes) &&
              ((detail() as { notes?: string[] }).notes ?? []).length > 0}
          >
            <dt class="text-text-subtle">Notes</dt>
            <dd class="flex flex-col gap-1 text-[11.5px] text-text">
              <For each={((detail() as { notes?: string[] }).notes ?? [])}>
                {(n) => <span>{n}</span>}
              </For>
            </dd>
          </Show>
        </section>
      </Show>
    </div>
  );
}
