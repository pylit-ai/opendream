import { createResource, Show, type JSX } from 'solid-js';
import { CheckCircle } from 'lucide-solid';
import { getEvals } from '~/api/client';
import type { EvalsResponse } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { Chip, type ChipVariant } from '~/components/Chip';
import { EmptyState } from '~/components/EmptyState';
import { SkeletonRows } from '~/components/Skeleton';
import { ErrorState } from '~/components/ErrorState';
import { formatDate } from '~/lib/format';

interface EvalItem {
  name?: string;
  status?: string;
  score?: number | null;
  last_run?: string;
  ran_at?: string;
  timestamp?: string;
  message?: string;
  detail?: string;
  [k: string]: unknown;
}

function statusVariant(s: string | undefined): ChipVariant {
  const v = (s ?? '').toLowerCase();
  if (v.includes('ok') || v.includes('pass') || v.includes('success')) return 'ok';
  if (v.includes('warn') || v.includes('partial')) return 'warn';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

function extractItems(data: EvalsResponse | undefined): EvalItem[] {
  if (!data) return [];
  // Try common shapes: { evals: [...] }, { items: [...] }, array
  const evals = data.evals;
  if (Array.isArray(evals)) return evals as EvalItem[];
  if (Array.isArray(data)) return data as EvalItem[];
  const health = data.health;
  if (health && typeof health === 'object') {
    // flatten health object into rows
    return Object.entries(health as Record<string, unknown>).map(([name, val]) => {
      if (val && typeof val === 'object') return { name, ...(val as object) };
      return { name, status: String(val) };
    });
  }
  return [];
}

const COLS: TableColumn<EvalItem>[] = [
  {
    key: 'name',
    header: 'Name',
    render: (item) => <span class="font-mono text-xs">{item.name ?? '—'}</span>,
  },
  {
    key: 'status',
    header: 'Status',
    render: (item) => (
      <Chip variant={statusVariant(item.status)}>{item.status ?? '—'}</Chip>
    ),
    width: '100px',
  },
  {
    key: 'score',
    header: 'Score',
    align: 'right',
    render: (item) => (
      <span class="font-mono text-xs">
        {item.score !== null && item.score !== undefined ? String(item.score) : '—'}
      </span>
    ),
    width: '80px',
  },
  {
    key: 'last_run',
    header: 'Last run',
    render: (item) => {
      const ts = item.last_run ?? item.ran_at ?? item.timestamp;
      return <span class="text-xs text-text-muted">{ts ? formatDate(ts) : '—'}</span>;
    },
    width: '120px',
  },
  {
    key: 'message',
    header: 'Message',
    render: (item) => (
      <span class="truncate text-xs text-text-muted">{item.message ?? item.detail ?? '—'}</span>
    ),
  },
];

export default function EvalsRoute(): JSX.Element {
  const [data, { refetch }] = createResource<EvalsResponse>(getEvals);

  return (
    <Page title="Evals" subtitle="Quality + health checks">
      <Show when={!data.loading} fallback={<SkeletonRows rows={4} />}>
        <Show
          when={!data.error}
          fallback={
            <ErrorState
              message={data.error instanceof Error ? data.error.message : String(data.error)}
              onRetry={refetch}
            />
          }
        >
          <Table
            items={extractItems(data())}
            columns={COLS}
            rowKey={(item, i) => String(item.name ?? i)}
            empty={
              <EmptyState
                icon={CheckCircle}
                title="No eval results"
                description="Run evals to see quality and health checks."
              />
            }
          />
        </Show>
      </Show>
    </Page>
  );
}
