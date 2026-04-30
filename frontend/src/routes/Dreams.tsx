import { createResource, createSignal, For, Show, type JSX } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { Moon } from 'lucide-solid';
import {
  getDreamCoverage,
  getDreamCycles,
  getDreamFunnel,
  ingestTranscripts,
  runDream,
  type DreamRunResult,
  type TranscriptsIngestResult,
} from '~/api/client';
import type { DreamCoverageResponse, DreamCycle, DreamCycleListResponse, DreamFunnelResponse } from '~/api/types';
import { Page } from '~/components/Page';
import { Table, type TableColumn } from '~/components/Table';
import { Chip, type ChipVariant } from '~/components/Chip';
import { EmptyState } from '~/components/EmptyState';
import { ErrorState } from '~/components/ErrorState';
import { SkeletonRows } from '~/components/Skeleton';
import { SlideOver } from '~/components/SlideOver';
import { IdLink } from '~/components/IdLink';
import { CopyButton } from '~/components/CopyButton';
import { CoverageTrend } from '~/components/dreams/CoverageTrend';
import { Funnel } from '~/components/dreams/Funnel';
import { PhaseBar, PhaseLegend } from '~/components/dreams/PhaseBar';
import { formatDate, formatDateLong, formatDuration, formatNumber } from '~/lib/format';
import { cachedFetch, invalidate } from '~/lib/cache';

function statusVariant(s: string | undefined): ChipVariant {
  const v = (s ?? '').toLowerCase();
  if (v.includes('complete') || v.includes('ok')) return 'ok';
  if (v.includes('skip') || v.includes('insufficient') || v.includes('warn')) return 'warn';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

function reasonVariant(r: string | undefined): ChipVariant {
  if (!r) return 'neutral';
  const v = r.toLowerCase();
  if (v === 'no-episodes' || v.includes('insufficient')) return 'warn';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

function durationOf(r: DreamCycle): string {
  const explicit = r.duration_ms;
  if (typeof explicit === 'number') return formatDuration(explicit);
  if (!r.started_at || !r.ended_at) return '—';
  const a = Date.parse(r.started_at);
  const b = Date.parse(r.ended_at);
  if (Number.isNaN(a) || Number.isNaN(b)) return '—';
  return formatDuration(Math.max(0, b - a));
}

export default function DreamsRoute(): JSX.Element {
  const navigate = useNavigate();
  const [cycles, { refetch }] = createResource<DreamCycleListResponse>(() =>
    cachedFetch('dream-cycles', () => getDreamCycles({ limit: 200 }), 15_000),
  );
  const [coverage] = createResource<DreamCoverageResponse>(() =>
    cachedFetch('dream-coverage', () => getDreamCoverage({ window: '7d' }), 15_000),
  );
  const [funnel] = createResource<DreamFunnelResponse>(() =>
    cachedFetch('dream-funnel', () => getDreamFunnel({ window: '7d' }), 15_000),
  );

  const [busy, setBusy] = createSignal<string | null>(null);
  const [lastDream, setLastDream] = createSignal<DreamRunResult | null>(null);
  const [lastIngest, setLastIngest] = createSignal<TranscriptsIngestResult | null>(null);
  const [err, setErr] = createSignal<string | null>(null);
  const [selected, setSelected] = createSignal<DreamCycle | null>(null);
  const [showAllPhases, setShowAllPhases] = createSignal(false);
  const phaseLimit = () => (showAllPhases() ? dreams().length : 5);
  const observedPhases = (): string[] => {
    const set = new Set<string>();
    for (const r of dreams()) {
      const d = r.phase_durations ?? {};
      for (const k of Object.keys(d)) set.add(k);
    }
    return Array.from(set);
  };

  async function trigger(action: 'full' | 'semantic' | 'hybrid' | 'ingest') {
    setBusy(action);
    setErr(null);
    try {
      if (action === 'ingest') {
        setLastIngest(await ingestTranscripts(false));
      } else {
        setLastDream(await runDream(action));
      }
      invalidate('runs');
      invalidate('overview');
      invalidate('dream-cycles');
      invalidate('dream-coverage');
      invalidate('dream-funnel');
      await refetch();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const dreams = (): DreamCycle[] => cycles()?.items ?? [];

  const skipped = (): DreamCycle[] =>
    dreams().filter((r) => (r.status ?? '').toLowerCase() === 'skipped');

  const columns: TableColumn<DreamCycle>[] = [
    {
      key: 'when',
      header: 'When',
      width: '150px',
      render: (r) =>
        r.started_at ? (
          <span title={formatDateLong(r.started_at)} class="text-xs text-text">
            {formatDate(r.started_at)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        ),
    },
    {
      key: 'mode',
      header: 'Mode',
      width: '110px',
      render: (r) => {
        const mode = String(
          r.mode ??
            r.type ??
            'dream',
        );
        return <Chip variant="neutral">{mode}</Chip>;
      },
    },
    {
      key: 'status',
      header: 'Status',
      width: '120px',
      render: (r) => <Chip variant={statusVariant(r.status)}>{r.status ?? '—'}</Chip>,
    },
    {
      key: 'reason',
      header: 'Reason',
      width: '160px',
      render: (r) => {
        const reason = r.reason;
        return reason ? <Chip variant={reasonVariant(reason)}>{reason}</Chip> : <span class="text-text-subtle">—</span>;
      },
    },
    {
      key: 'phases',
      header: 'Phases',
      render: (r) => {
        const phases = r.phases ?? [];
        return (
          <div class="min-w-[160px]">
            <PhaseBar durations={r.phase_durations ?? {}} height={10} />
            <div class="mt-1 truncate font-mono text-[10.5px] text-text-muted">
              {phases.length > 0 ? phases.join(' -> ') : '—'}
            </div>
          </div>
        );
      },
    },
    {
      key: 'duration',
      header: 'Duration',
      width: '90px',
      align: 'right',
      numeric: true,
      render: (r) => <span class="font-mono text-xs text-text-muted">{durationOf(r)}</span>,
    },
    {
      key: 'agent',
      header: 'Agent',
      width: '120px',
      render: (r) => {
        const ag = r.reporting_agent_label
          ?? (r as { agent_id?: string }).agent_id
          ?? '—';
        return <span class="font-mono text-[11px] text-text-muted">{ag}</span>;
      },
    },
    {
      key: 'model',
      header: 'Model',
      width: '120px',
      render: (r) => {
        const mid = r.model_id || '—';
        return <span class="font-mono text-[11px] text-text-muted">{mid}</span>;
      },
    },
    {
      key: 'id',
      header: 'Run',
      width: '170px',
      render: (r) => (
        <div class="flex flex-col gap-0.5">
          <IdLink id={r.run_id} onClick={() => setSelected(r)} />
          <span class="line-clamp-2 text-[11px] text-text-muted">{r.narrative}</span>
        </div>
      ),
    },
  ];

  return (
    <Page
      title="Dreams"
      subtitle="Memory consolidation cycles — manual triggers, recent runs, blocked-cycle inspector"
    >
      <section class="flex flex-col gap-3">
        <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Manual triggers</div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busy() !== null}
            onClick={() => void trigger('ingest')}
            class="rounded-md hairline px-3 py-1.5 text-[12px] text-text hover:bg-surface-elevated disabled:opacity-50"
            title="Pull agent transcripts into transcripts/. Auto-detect currently supports Claude Code; Codex, Cursor, and Gemini can be ingested with `opendream transcripts ingest --from <path>`."
          >
            {busy() === 'ingest' ? 'Ingesting…' : 'Ingest transcripts'}
          </button>
          <button
            type="button"
            disabled={busy() !== null}
            onClick={() => void trigger('full')}
            class="rounded-md bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
          >
            {busy() === 'full' ? 'Dreaming…' : 'Dream now'}
          </button>
          <button
            type="button"
            disabled={busy() !== null}
            onClick={() => void trigger('semantic')}
            class="rounded-md hairline px-3 py-1.5 text-[12px] text-text hover:bg-surface-elevated disabled:opacity-50"
          >
            {busy() === 'semantic' ? 'Dreaming…' : 'Dream (semantic)'}
          </button>
          <button
            type="button"
            disabled={busy() !== null}
            onClick={() => void trigger('hybrid')}
            class="rounded-md hairline px-3 py-1.5 text-[12px] text-text hover:bg-surface-elevated disabled:opacity-50"
          >
            {busy() === 'hybrid' ? 'Dreaming…' : 'Dream (hybrid)'}
          </button>
        </div>
        <Show when={err()}>
          <div class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-danger">{err()}</div>
        </Show>
        <Show when={lastIngest()}>
          {(r) => (
            <div class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text">
              <span class="font-mono text-text-subtle">ingest:</span> {r().status} · seen {r().files_seen ?? 0} ·
              written {r().files_written ?? 0} · skipped {r().files_skipped ?? 0} · rows in/out{' '}
              {r().rows_in ?? 0}/{r().rows_out ?? 0}
            </div>
          )}
        </Show>
        <Show when={lastDream()}>
          {(r) => (
            <div class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text">
              <span class="font-mono text-text-subtle">dream:</span> {r().status}
              <Show when={r().reason}>
                {' '}· <span class="text-warn">{r().reason}</span>
              </Show>{' '}
              · phases [{(r().phases ?? []).join(', ')}]
              <Show when={r().duration_ms !== undefined}> · {r().duration_ms}ms</Show>
              <Show when={r().run_id}>
                {' '}·{' '}
                <button
                  type="button"
                  onClick={() => navigate(`/runs?id=${encodeURIComponent(r().run_id!)}`)}
                  class="font-mono text-accent hover:underline"
                >
                  {r().run_id}
                </button>
              </Show>
            </div>
          )}
        </Show>
      </section>

      <Show when={skipped().length > 0}>
        <section class="flex flex-col gap-2">
          <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
            Skipped cycles · {skipped().length}
          </div>
          <p class="text-[11.5px] text-text-muted">
            These cycles short-circuited. Most common reasons:
            <code class="mx-1 rounded bg-surface-elevated px-1 font-mono text-[11px]">no-episodes</code>
            (transcripts not ingested) and
            <code class="mx-1 rounded bg-surface-elevated px-1 font-mono text-[11px]">insufficient-signal</code>
            (orientation tokens didn't match recent rows).
          </p>
          <div class="flex flex-col">
            <For each={skipped().slice(0, 5)}>
              {(r) => (
                <div class="hairline-b flex items-center gap-3 py-1.5 text-[12px]">
                  <Chip variant={reasonVariant((r as { reason?: string }).reason)}>
                    {(r as { reason?: string }).reason ?? 'unknown'}
                  </Chip>
                  <span class="font-mono text-[11px] text-text-muted">{r.run_id}</span>
                  <Show when={r.started_at}>
                    <span class="text-[11px] text-text-subtle">{formatDate(r.started_at!)}</span>
                  </Show>
                </div>
              )}
            </For>
          </div>
        </section>
      </Show>

      <section class="flex flex-wrap items-stretch gap-x-6 gap-y-2 rounded-md hairline bg-surface px-4 py-2.5">
        <CompactStat label="Cycles" value={formatNumber(dreams().length)} />
        <CompactStat label="Success" value={`${successRate(dreams())}%`} tone={successRate(dreams()) >= 80 ? 'ok' : successRate(dreams()) >= 50 ? 'warn' : 'danger'} />
        <CompactStat label="Avg duration" value={avgDuration(dreams())} />
        <CompactStat label="Approved" value={formatNumber(sumFunnel(dreams(), 'approved'))} />
        <CompactStat label="Skipped" value={formatNumber(skipped().length)} tone={skipped().length === 0 ? 'ok' : 'warn'} />
      </section>

      <section class="grid gap-3 lg:grid-cols-[1.1fr_1fr]">
        <div class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
          <div class="flex items-baseline justify-between">
            <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Proposal funnel</div>
            <div class="text-[10px] text-text-subtle">last 7d aggregate</div>
          </div>
          <Funnel counts={funnel()?.funnel ?? emptyFunnel()} />
        </div>
        <div class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
          <div class="flex items-baseline justify-between">
            <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Signal coverage</div>
            <div class="text-[10px] text-text-subtle">7d trend · per source class</div>
          </div>
          <CoverageTrend buckets={coverage()?.items ?? []} />
        </div>
      </section>

      <Show when={dreams().length > 0}>
        <section class="flex flex-col gap-2 rounded-md hairline bg-surface px-4 py-3">
          <div class="flex items-baseline justify-between">
            <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
              Phase progression · last {Math.min(dreams().length, phaseLimit())} of {dreams().length}
            </div>
            <Show when={dreams().length > 5}>
              <button
                type="button"
                onClick={() => setShowAllPhases((v) => !v)}
                class="text-[10px] text-accent hover:underline"
              >
                {showAllPhases() ? 'Show last 5' : `Show all ${dreams().length}`}
              </button>
            </Show>
          </div>
          <PhaseLegend phases={observedPhases()} />
          <div class="flex flex-col gap-1 pt-1">
            <For each={dreams().slice(0, phaseLimit())}>
              {(r) => (
                <button
                  type="button"
                  onClick={() => setSelected(r)}
                  class="row-hover grid grid-cols-[110px_1fr_70px] items-center gap-3 rounded px-1 text-left"
                  title={r.narrative ?? r.run_id}
                >
                  <span class="truncate font-mono text-[10px] text-text-subtle">{r.run_id}</span>
                  <PhaseBar durations={r.phase_durations ?? {}} height={6} />
                  <span class="text-right font-mono text-[10px] text-text-subtle">{durationOf(r)}</span>
                </button>
              )}
            </For>
          </div>
        </section>
      </Show>

      <section class="flex flex-col gap-2">
        <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
          Recent dream cycles · {dreams().length}
        </div>
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
            <Table
              items={dreams()}
              columns={columns}
              rowKey={(r) => r.run_id}
              onRowClick={(r) => setSelected(r)}
              empty={
                <EmptyState
                  icon={Moon}
                  title="No dream cycles yet"
                  description="Click Dream now to force a cycle, or wait for the runtime to schedule one."
                />
              }
            />
          </Show>
        </Show>
      </section>

      <SlideOver
        open={selected() !== null}
        onOpenChange={(o) => !o && setSelected(null)}
        title="Dream cycle"
        description={selected()?.run_id}
      >
        <Show when={selected()}>
          {(r) => <DreamDetail run={r()} onOpenRun={(id) => navigate(`/runs?id=${encodeURIComponent(id)}`)} />}
        </Show>
      </SlideOver>
    </Page>
  );
}

type FunnelKey = 'considered' | 'selected' | 'generated' | 'approved' | 'created';

function emptyFunnel() {
  return { considered: 0, selected: 0, generated: 0, approved: 0, created: 0 };
}

function successRate(items: DreamCycle[]): number {
  if (items.length === 0) return 0;
  const ok = items.filter((item) => (item.status ?? '').toLowerCase() === 'completed').length;
  return Math.round((ok / items.length) * 100);
}

function avgDuration(items: DreamCycle[]): string {
  const values = items.map((item) => item.duration_ms).filter((value): value is number => typeof value === 'number');
  if (values.length === 0) return '—';
  return formatDuration(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function sumFunnel(items: DreamCycle[], key: FunnelKey): number {
  return items.reduce((sum, item) => sum + (item.funnel?.[key] ?? 0), 0);
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

interface DreamSummary {
  cost_usd?: number;
  duration_ms?: number;
  ended_at?: string;
  started_at?: string;
  latest_signal_source?: string;
  latest_signal_timestamp?: string;
  learned_context_created?: number;
  learned_context_superseded?: number;
  mode?: string;
  model_id?: string;
  provider_id?: string;
  phases?: string[];
  proposals_approved?: number;
  proposals_generated?: number;
  proposals_rejected?: number;
  query_families_considered?: number;
  query_families_selected?: number;
  reason?: string;
  signal_row_count?: number;
  status?: string;
  tokens_used?: number;
  trigger_class?: string;
  semantic_summary?: Record<string, unknown>;
  audit?: { diff_path?: string; summary_path?: string };
  [k: string]: unknown;
}

function DreamDetail(props: { run: DreamCycle; onOpenRun: (id: string) => void }): JSX.Element {
  const summaryDict = (): DreamSummary => {
    const raw = (props.run as { summary?: unknown }).summary;
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as DreamSummary;
    return {};
  };

  const agent = (): string => {
    const r = props.run as {
      reporting_agent_label?: string;
      source_reporting_agents?: Array<{ agent_label?: string; agent_id?: string }>;
      agent_id?: string;
    };
    if (r.reporting_agent_label) return r.reporting_agent_label;
    const arr = r.source_reporting_agents ?? [];
    if (arr.length > 0) return arr.map((a) => a.agent_label ?? a.agent_id ?? '?').join(', ');
    return r.agent_id ?? '—';
  };

  const headlineStat = (label: string, value: string | number | undefined): JSX.Element => (
    <div class="flex flex-col">
      <span class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">{label}</span>
      <span class="font-mono text-[13px] text-text">{value === undefined || value === null ? '—' : String(value)}</span>
    </div>
  );

  const dur = (): string => {
    const ms = summaryDict().duration_ms;
    if (typeof ms === 'number') return formatDuration(ms);
    if (props.run.started_at && props.run.ended_at) {
      const a = Date.parse(props.run.started_at);
      const b = Date.parse(props.run.ended_at);
      if (!Number.isNaN(a) && !Number.isNaN(b)) return formatDuration(Math.max(0, b - a));
    }
    return '—';
  };

  return (
    <div class="flex flex-col gap-5 p-5">
      <header class="flex items-start gap-2">
        <span class="flex-1 break-all font-mono text-[12.5px] text-text">{props.run.run_id}</span>
        <CopyButton value={props.run.run_id} label="Copy run id" />
      </header>

      <section class="flex flex-wrap items-center gap-1.5">
        <Chip variant="neutral">{props.run.type ?? 'dream'}</Chip>
        <Chip
          variant={
            (props.run.status ?? '').toLowerCase() === 'completed'
              ? 'ok'
              : (props.run.status ?? '').toLowerCase() === 'skipped'
                ? 'warn'
                : 'neutral'
          }
        >
          {props.run.status ?? '—'}
        </Chip>
        <Show when={summaryDict().reason}>
          <Chip variant="warn">{summaryDict().reason}</Chip>
        </Show>
        <Show when={summaryDict().trigger_class}>
          <Chip variant="neutral">{summaryDict().trigger_class}</Chip>
        </Show>
      </section>

      <section class="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {headlineStat('Mode', summaryDict().mode)}
        {headlineStat('Duration', dur())}
        {headlineStat('Agent', agent())}
        {headlineStat('Model', summaryDict().model_id || summaryDict().provider_id)}
        {headlineStat(
          'Cost (USD)',
          typeof summaryDict().cost_usd === 'number' ? summaryDict().cost_usd!.toFixed(4) : undefined,
        )}
        {headlineStat(
          'Tokens',
          typeof summaryDict().tokens_used === 'number' ? formatNumber(summaryDict().tokens_used!) : undefined,
        )}
      </section>

      <section class="rounded-md hairline bg-surface p-3 text-[12.5px] leading-5 text-text">
        {props.run.narrative}
      </section>

      <Show when={Object.keys(props.run.phase_durations ?? {}).length > 0}>
        <section class="flex flex-col gap-1.5">
          <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Phases</h4>
          <PhaseBar durations={props.run.phase_durations ?? {}} height={18} showLabels />
        </section>
      </Show>

      <section class="flex flex-col gap-1.5">
        <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Signal + proposals</h4>
        <div class="rounded-md hairline bg-surface p-2.5 text-[12px]">
          <Funnel counts={props.run.funnel ?? emptyFunnel()} />
        </div>
        <div class="flex flex-col gap-1 rounded-md hairline bg-surface p-2.5 text-[12px]">
          <FunnelRow label="Signal rows scanned" value={summaryDict().signal_row_count} />
          <FunnelRow label="Query families considered" value={summaryDict().query_families_considered} />
          <FunnelRow label="Query families selected" value={summaryDict().query_families_selected} />
          <FunnelRow label="Proposals generated" value={summaryDict().proposals_generated} />
          <FunnelRow label="Proposals approved" value={summaryDict().proposals_approved} tone="ok" />
          <FunnelRow label="Proposals rejected" value={summaryDict().proposals_rejected} tone="warn" />
          <FunnelRow label="Learned context created" value={summaryDict().learned_context_created} />
          <FunnelRow label="Learned context superseded" value={summaryDict().learned_context_superseded} />
        </div>
      </section>

      <Show when={summaryDict().latest_signal_source || summaryDict().latest_signal_timestamp}>
        <section class="flex flex-col gap-1">
          <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Source signal</h4>
          <div class="flex flex-col gap-0.5 rounded-md hairline bg-surface p-2.5 text-[12px]">
            <Show when={summaryDict().latest_signal_source}>
              <span>
                <span class="text-text-subtle">source:</span>{' '}
                <span class="font-mono">{summaryDict().latest_signal_source}</span>
              </span>
            </Show>
            <Show when={summaryDict().latest_signal_timestamp}>
              <span>
                <span class="text-text-subtle">at:</span>{' '}
                {formatDateLong(summaryDict().latest_signal_timestamp!)}
              </span>
            </Show>
          </div>
        </section>
      </Show>

      <Show when={summaryDict().audit?.diff_path || summaryDict().audit?.summary_path}>
        <section class="flex flex-col gap-1">
          <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Audit artifacts</h4>
          <div class="flex flex-col gap-0.5 rounded-md hairline bg-surface p-2.5 font-mono text-[10.5px] text-text-muted">
            <Show when={summaryDict().audit?.summary_path}>
              <span class="break-all">{summaryDict().audit?.summary_path}</span>
            </Show>
            <Show when={summaryDict().audit?.diff_path}>
              <span class="break-all">{summaryDict().audit?.diff_path}</span>
            </Show>
          </div>
        </section>
      </Show>

      <button
        type="button"
        onClick={() => props.onOpenRun(props.run.run_id)}
        class="self-start rounded-md hairline px-3 py-1.5 text-[11.5px] text-text-muted hover:bg-surface-elevated hover:text-text"
      >
        Open raw run inspector
      </button>
    </div>
  );
}

function FunnelRow(props: {
  label: string;
  value: number | undefined;
  tone?: 'ok' | 'warn';
}): JSX.Element {
  return (
    <div class="flex items-center justify-between">
      <span class="text-text-muted">{props.label}</span>
      <Show
        when={typeof props.value === 'number'}
        fallback={<span class="text-text-subtle">—</span>}
      >
        <span
          class={
            props.tone === 'ok'
              ? 'font-mono text-success'
              : props.tone === 'warn'
                ? 'font-mono text-warn'
                : 'font-mono text-text'
          }
        >
          {formatNumber(props.value!)}
        </span>
      </Show>
    </div>
  );
}
