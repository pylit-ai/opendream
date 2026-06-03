import { createEffect, createResource, createSignal, For, on, Show, type JSX } from 'solid-js';
import { useNavigate, useSearchParams } from '@solidjs/router';
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
  // Idle reasons aren't failures — they mean the pipeline ran and correctly
  // found nothing new to consume. Render neutral, not warn.
  if (v === 'no-episodes' || v.includes('insufficient')) return 'neutral';
  if (v.includes('fail') || v.includes('error')) return 'danger';
  return 'neutral';
}

const IDLE_REASONS = new Set(['no-episodes', 'insufficient-signal']);
const SIGNAL_BUCKET_SIZE = 10;
const TRANSCRIPT_IMPORT_CONSENT_KEY = 'opendream.transcriptImportConsent.v1';

function loadTranscriptImportConsent(): boolean {
  try {
    return window.localStorage.getItem(TRANSCRIPT_IMPORT_CONSENT_KEY) === 'granted';
  } catch {
    return false;
  }
}

function saveTranscriptImportConsent(): void {
  try {
    window.localStorage.setItem(TRANSCRIPT_IMPORT_CONSENT_KEY, 'granted');
  } catch {
    // Local storage can be unavailable in restricted browser contexts.
  }
}

function isIdleReason(r: string | undefined): boolean {
  return r != null && IDLE_REASONS.has(r);
}

function reasonLabel(r: string | undefined): string {
  if (!r) return '—';
  if (r === 'no-episodes') return 'no transcripts';
  if (r === 'insufficient-signal') return 'no new signal';
  return r;
}

function reasonExplainer(r: string | undefined): string | null {
  if (r === 'no-episodes') {
    return 'No agent transcripts are available yet. Use Allow import and dream or Ingest transcripts to grant one-time local transcript import consent.';
  }
  if (r === 'insufficient-signal') {
    return 'Dream completed but found no new content to consume. Pipeline is healthy and idle — it will produce new events once your agents generate fresh sessions.';
  }
  return null;
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

function shortId(id: string | undefined): string {
  if (!id) return '—';
  if (id.length <= 14) return id;
  return `${id.slice(0, 10)}…${id.slice(-4)}`;
}

function cycleMode(r: DreamCycle): string {
  return String(r.mode ?? r.type ?? 'dream');
}

function numericField(r: DreamCycle, key: string): number {
  const direct = r[key];
  if (typeof direct === 'number') return direct;
  const summary = r.summary;
  if (summary && typeof summary[key] === 'number') return summary[key];
  return 0;
}

function funnelValue(r: DreamCycle, key: keyof DreamCycle['funnel']): number {
  return typeof r.funnel?.[key] === 'number' ? r.funnel[key] : 0;
}

function effectCount(r: DreamCycle): number {
  return (
    funnelValue(r, 'generated') +
    funnelValue(r, 'approved') +
    funnelValue(r, 'created') +
    numericField(r, 'learned_context_superseded') +
    numericField(r, 'proposals_rejected') +
    numericField(r, 'appended_events')
  );
}

function hasMaterialEffect(r: DreamCycle): boolean {
  if (r.change_point) return r.change_point.kind === 'material';
  return effectCount(r) > 0;
}

function isFailureCycle(r: DreamCycle): boolean {
  if (r.change_point) return r.change_point.kind === 'failure';
  return (r.status ?? '').toLowerCase() === 'skipped' && !isIdleReason(r.reason);
}

function isNoopCycle(r: DreamCycle): boolean {
  if (r.change_point) return r.change_point.is_noop;
  return !hasMaterialEffect(r) && !isFailureCycle(r);
}

function changePointLabel(r: DreamCycle): string | undefined {
  return r.change_point?.is_noop ? undefined : r.change_point?.label;
}

function changePointKind(r: DreamCycle): string | undefined {
  return r.change_point?.kind;
}

function changePointVariant(r: DreamCycle): ChipVariant {
  const cp = r.change_point;
  if (!cp) return 'accent';
  if (cp.kind === 'material') return 'ok';
  if (cp.kind === 'failure') return 'danger';
  if (cp.severity === 'high') return 'danger';
  if (cp.severity === 'medium') return 'accent';
  return 'neutral';
}

function scoreText(r: DreamCycle): string {
  const score = r.change_point?.score;
  return typeof score === 'number' ? String(score) : '—';
}

function scoreExplainer(r: DreamCycle): string {
  const cp = r.change_point;
  if (!cp) return 'No backend score available; row uses local fallback grouping.';
  return `${cp.kind.replace('_', ' ')} · ${cp.severity} · ${cp.label}`;
}

function noopLabel(r: DreamCycle): string {
  if (r.change_point?.label) return r.change_point.label;
  if ((r.status ?? '').toLowerCase() === 'skipped' && isIdleReason(r.reason)) {
    return reasonExplainer(r.reason) ?? reasonLabel(r.reason);
  }
  return 'No memory changes, staged events, failures, drift, or phase anomalies.';
}

function traceNoMaterializationReason(r: DreamCycle): string | undefined {
  const trace = r.trace_summary;
  if (!trace) return undefined;
  const created = trace.learned_context_created ?? funnelValue(r, 'created');
  if (created > 0) return undefined;
  return trace.no_materialization_reason || r.reason || undefined;
}

function verifierSummary(r: DreamCycle): string {
  const verdicts = r.trace_summary?.verifier_verdicts ?? {};
  const parts = Object.entries(verdicts)
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .map(([key, value]) => `${key} ${value}`);
  return parts.length > 0 ? parts.join(' · ') : '—';
}

function rowAccentClass(r: DreamCycle): string | undefined {
  const cp = r.change_point;
  if (!cp) {
    if (hasMaterialEffect(r)) return 'border-l-2 border-l-success bg-[color-mix(in_oklab,rgb(var(--c-success))_5%,transparent)]';
    if (isFailureCycle(r)) return 'border-l-2 border-l-danger bg-[color-mix(in_oklab,rgb(var(--c-danger))_5%,transparent)]';
    return undefined;
  }
  if (cp.kind === 'noop') return undefined;
  if (cp.kind === 'material') return 'border-l-2 border-l-success bg-[color-mix(in_oklab,rgb(var(--c-success))_5%,transparent)]';
  if (cp.kind === 'failure') return 'border-l-2 border-l-danger bg-[color-mix(in_oklab,rgb(var(--c-danger))_5%,transparent)]';
  return 'border-l-2 border-l-accent bg-[color-mix(in_oklab,rgb(var(--c-accent))_5%,transparent)]';
}

function signalBucket(r: DreamCycle): string {
  const count = typeof r.signal_row_count === 'number' ? r.signal_row_count : 0;
  const start = Math.floor(count / SIGNAL_BUCKET_SIZE) * SIGNAL_BUCKET_SIZE;
  const end = start + SIGNAL_BUCKET_SIZE - 1;
  return `${start}-${end}`;
}

function signalLabel(r: DreamCycle): string {
  const count = typeof r.signal_row_count === 'number' ? r.signal_row_count : 0;
  const source = String(r.signal_source ?? r.summary?.latest_signal_source ?? '');
  if (source === 'explicit_events') return `${formatNumber(count)} explicit-event rows`;
  if (source === 'transcript_episodes') return `${formatNumber(count)} transcript rows`;
  return `${formatNumber(count)} signal rows`;
}

function latestSignalTimestamp(r: DreamCycle): string | undefined {
  return (
    r.latest_signal_timestamp ??
    (r.summary as { latest_signal_timestamp?: string } | undefined)?.latest_signal_timestamp
  );
}

function dreamProofParts(r: DreamCycle): string[] {
  const count = typeof r.signal_row_count === 'number' ? r.signal_row_count : 0;
  const source = String(r.signal_source ?? r.summary?.latest_signal_source ?? '');
  const unit =
    source === 'explicit_events'
      ? 'explicit-event rows'
      : source === 'transcript_episodes'
        ? 'transcript rows'
        : 'signal rows';
  const parts = [
    `scanned ${formatNumber(count)} ${unit}`,
  ];
  const ts = latestSignalTimestamp(r);
  if (ts) parts.push(`latest ${formatDateLong(ts)}`);
  parts.push(`proposals ${funnelValue(r, 'generated')}`);
  parts.push(`learned ${funnelValue(r, 'created')}`);
  return parts;
}

function dreamProofSentence(r: DreamCycle): string {
  const generated = funnelValue(r, 'generated');
  const created = funnelValue(r, 'created');
  if (created > 0) return `Materialized: ${dreamProofParts(r).join(' · ')}.`;
  if (generated > 0) return `Ran but did not promote learned context: ${dreamProofParts(r).join(' · ')}.`;
  return `Ran but did not learn yet: ${dreamProofParts(r).join(' · ')}.`;
}

function phaseSignature(r: DreamCycle): string {
  return (r.phases ?? []).join('>');
}

function effectSignature(r: DreamCycle): string {
  if (r.change_point?.signature) return r.change_point.signature;
  return [
    cycleMode(r),
    (r.status ?? '').toLowerCase(),
    r.reason ?? '',
    signalBucket(r),
    phaseSignature(r),
  ].join('|');
}

export default function DreamsRoute(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cycles, { refetch }] = createResource<DreamCycleListResponse>(() =>
    cachedFetch('dream-cycles', () => getDreamCycles({ limit: 1000 }), 15_000),
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
  const [expandedGroups, setExpandedGroups] = createSignal<Set<string>>(new Set());
  const [collapseIdle, setCollapseIdle] = createSignal(true);
  type ViewFilter = 'all' | 'changes' | 'material' | 'failures';
  const [viewFilter, setViewFilter] = createSignal<ViewFilter>('all');

  const toggleGroup = (key: string): void => {
    const next = new Set(expandedGroups());
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setExpandedGroups(next);
  };

  const openCycle = (c: DreamCycle | null): void => {
    setSelected(c);
    setSearchParams({ id: c ? c.run_id ?? undefined : undefined }, { replace: false });
  };

  // ?id= deep-link: open SlideOver for the referenced cycle once data loads
  createEffect(
    on(
      () => [cycles(), searchParams.id] as const,
      ([data, id]) => {
        const wanted = typeof id === 'string' ? id : null;
        if (!wanted) {
          if (selected() !== null) setSelected(null);
          return;
        }
        const items = (data?.items ?? []) as DreamCycle[];
        const found = items.find((c) => c.run_id === wanted || c.id === wanted) ?? null;
        if (found && selected()?.run_id !== found.run_id) setSelected(found);
      },
    ),
  );
  const [showAllPhases, setShowAllPhases] = createSignal(false);
  const phaseLimit = () => (showAllPhases() ? dreams().length : 5);
  const [transcriptImportConsented, setTranscriptImportConsented] = createSignal(loadTranscriptImportConsent());
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
        saveTranscriptImportConsent();
        setTranscriptImportConsented(true);
        setLastIngest(await ingestTranscripts(false));
      } else {
        const autoIngestTranscripts = transcriptImportConsented() || action === 'full';
        if (autoIngestTranscripts && !transcriptImportConsented()) {
          saveTranscriptImportConsent();
          setTranscriptImportConsented(true);
        }
        setLastDream(await runDream(action, { autoIngestTranscripts }));
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
  const skippedFailures = (): DreamCycle[] =>
    skipped().filter((r) => !isIdleReason(r.reason));
  const idleStreakLength = (): number => {
    let n = 0;
    for (const r of dreams()) {
      if ((r.status ?? '').toLowerCase() === 'skipped' && isIdleReason(r.reason)) n += 1;
      else break;
    }
    return n;
  };
  const idleStreakActive = (): boolean => idleStreakLength() >= 1;
  const lastSignalTimestamp = (): string | undefined => {
    for (const r of dreams()) {
      const ts =
        (r as { latest_episode_timestamp?: string }).latest_episode_timestamp ??
        (r.summary as { latest_signal_timestamp?: string } | undefined)?.latest_signal_timestamp;
      if (ts) return ts;
    }
    return undefined;
  };

  type EffectGroup = {
    kind: 'effect-group';
    key: string;
    cycles: DreamCycle[];
    reason: string | undefined;
    label: string;
    mode: string;
    signal: string;
    proof: string;
    latestRunId: string | undefined;
    oldestRunId: string | undefined;
    firstTs: string | undefined;
    lastTs: string | undefined;
    totalMs: number;
  };
  type CycleRow = { kind: 'cycle'; cycle: DreamCycle; change?: string };
  type ExpandedHeader = {
    kind: 'expanded-header';
    key: string;
    count: number;
    label: string;
  };
  type Row = CycleRow | EffectGroup | ExpandedHeader;

  const filteredDreams = (): DreamCycle[] => {
    const f = viewFilter();
    const items = dreams();
    if (f === 'all') return items;
    if (f === 'changes') return items.filter((c) => !isNoopCycle(c));
    if (f === 'material') return items.filter((c) => hasMaterialEffect(c));
    if (f === 'failures') return items.filter((c) => isFailureCycle(c));
    return items;
  };

  const groupedRows = (): Row[] => {
    const items = filteredDreams();
    // When filter strips noop cycles, grouping has nothing to collapse — render plain rows.
    if (viewFilter() !== 'all') return items.map((c) => ({ kind: 'cycle', cycle: c }));
    if (!collapseIdle()) return items.map((c) => ({ kind: 'cycle', cycle: c }));
    const expanded = expandedGroups();
    const out: Row[] = [];
    let i = 0;
    while (i < items.length) {
      const c = items[i]!;
      if (!isNoopCycle(c)) {
        out.push({ kind: 'cycle', cycle: c, change: changePointLabel(c) });
        i += 1;
        continue;
      }
      const signature = effectSignature(c);
      let j = i;
      while (j < items.length) {
        const n = items[j]!;
        if (!isNoopCycle(n) || effectSignature(n) !== signature) break;
        j += 1;
      }
      const run = items.slice(i, j);
      const first = run[0]!;
      const last = run[run.length - 1]!;
      const key = `effect:${signature}:${first.run_id}:${last.run_id}`;
      if (run.length === 1 || expanded.has(key)) {
        if (run.length > 1 && expanded.has(key)) {
          out.push({
            kind: 'expanded-header',
            key,
            count: run.length,
            label: noopLabel(c),
          });
        }
        for (let offset = 0; offset < run.length; offset += 1) {
          const x = run[offset]!;
          const next = items[i + offset + 1];
          const changed =
            !x.change_point && next && isNoopCycle(x) && signalBucket(x) !== signalBucket(next)
              ? `${signalLabel(next)} -> ${signalLabel(x)}`
              : undefined;
          out.push({ kind: 'cycle', cycle: x, change: changed });
        }
      } else {
        const totalMs = run.reduce(
          (s, x) => s + (typeof x.duration_ms === 'number' ? x.duration_ms : 0),
          0,
        );
        out.push({
          kind: 'effect-group',
          key,
          cycles: run,
          reason: c.reason,
          label: noopLabel(c),
          mode: cycleMode(c),
          signal: signalLabel(c),
          proof: dreamProofSentence(c),
          latestRunId: first.run_id,
          oldestRunId: last.run_id,
          firstTs: last.started_at,
          lastTs: first.started_at,
          totalMs,
        });
      }
      i = j;
    }
    return out;
  };

  const collapsedCount = (): number => {
    return groupedRows().reduce(
      (n, r) => n + (r.kind === 'effect-group' ? r.cycles.length - 1 : 0),
      0,
    );
  };
  const highSignalCycles = (): DreamCycle[] =>
    dreams().filter((r) => (r.change_point?.score ?? 0) >= 45 && !r.change_point?.is_noop);
  const topChangePoint = (): DreamCycle | undefined =>
    highSignalCycles().slice().sort((a, b) => (b.change_point?.score ?? 0) - (a.change_point?.score ?? 0))[0];

  const columns: TableColumn<Row>[] = [
    {
      key: 'when',
      header: 'When',
      width: '150px',
      render: (row) => {
        if (row.kind === 'expanded-header') {
          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                toggleGroup(row.key);
              }}
              class="text-[11px] text-accent hover:underline"
              title={row.label}
            >
              ▾ Collapse {row.count}
            </button>
          );
        }
        if (row.kind === 'effect-group') {
          return (
            <span class="text-xs text-text-muted" title={`${row.firstTs ?? ''} → ${row.lastTs ?? ''}`}>
              {row.firstTs ? formatDate(row.firstTs) : '—'}
              <span class="text-text-subtle"> → </span>
              {row.lastTs ? formatDate(row.lastTs) : '—'}
            </span>
          );
        }
        const r = row.cycle;
        return r.started_at ? (
          <span title={formatDateLong(r.started_at)} class="text-xs text-text">
            {formatDate(r.started_at)}
          </span>
        ) : (
          <span class="text-text-subtle">—</span>
        );
      },
    },
    {
      key: 'mode',
      header: 'Mode',
      width: '110px',
      render: (row) => {
        if (row.kind === 'expanded-header') return <span class="text-text-subtle">—</span>;
        if (row.kind === 'effect-group') return <Chip variant="neutral">{row.mode}</Chip>;
        const r = row.cycle;
        return <Chip variant="neutral">{cycleMode(r)}</Chip>;
      },
    },
    {
      key: 'status',
      header: 'Change',
      width: '120px',
      render: (row) => {
        if (row.kind === 'expanded-header') {
          return <Chip variant="neutral">{`expanded × ${row.count}`}</Chip>;
        }
        if (row.kind === 'effect-group') {
          return <Chip variant="neutral">{`collapsed × ${row.cycles.length}`}</Chip>;
        }
        const kind = changePointKind(row.cycle);
        if (kind && kind !== 'noop') return <Chip variant={changePointVariant(row.cycle)}>{kind.replace('_', ' ')}</Chip>;
        if (hasMaterialEffect(row.cycle)) return <Chip variant="ok">material</Chip>;
        if (isFailureCycle(row.cycle)) return <Chip variant="danger">failure</Chip>;
        if (row.change) return <Chip variant="accent">drift</Chip>;
        return <Chip variant={statusVariant(row.cycle.status)}>{row.cycle.status ?? '—'}</Chip>;
      },
    },
    {
      key: 'score',
      header: 'Score',
      width: '78px',
      align: 'right',
      numeric: true,
      render: (row) => {
        if (row.kind === 'expanded-header') return <span class="text-text-subtle">—</span>;
        if (row.kind === 'effect-group') {
          return <span class="font-mono text-[11px] text-text-subtle">0</span>;
        }
        return (
          <span class="font-mono text-[11px] text-text-muted" title={scoreExplainer(row.cycle)}>
            {scoreText(row.cycle)}
          </span>
        );
      },
    },
    {
      key: 'reason',
      header: 'Rationale',
      width: '260px',
      render: (row) => {
        if (row.kind === 'expanded-header') {
          return (
            <span class="text-[11px] text-text-muted line-clamp-1" title={row.label}>
              Showing {row.count} expanded no-op cycles. Click ▾ to re-collapse.
            </span>
          );
        }
        if (row.kind === 'effect-group') {
          return (
            <div class="flex flex-col gap-0.5 text-[11px] text-text-muted">
              <span class="text-text">No material memory change across {row.cycles.length} equivalent cycles.</span>
              <span class="line-clamp-1">
                {row.mode} · {row.signal} · same phases · {row.proof}
              </span>
            </div>
          );
        }
        if (row.cycle.change_point && !row.cycle.change_point.is_noop) {
          return (
            <span class="line-clamp-2 text-[11px] text-text" title={scoreExplainer(row.cycle)}>
              {row.cycle.change_point.label}
            </span>
          );
        }
        const reason = row.cycle.reason;
        if (!reason) return <span class="text-text-subtle">—</span>;
        return (
          <Chip variant={reasonVariant(reason)}>
            <span title={reasonExplainer(reason) ?? reason}>{reasonLabel(reason)}</span>
          </Chip>
        );
      },
    },
    {
      key: 'phases',
      header: 'Phases',
      render: (row) => {
        if (row.kind === 'expanded-header') return <span class="text-text-subtle">—</span>;
        if (row.kind === 'effect-group') {
          return (
            <div class="flex flex-col gap-0.5 text-[11px] text-text-muted">
              <span>{row.signal} steady across {row.cycles.length} no-op cycles</span>
              <span class="font-mono text-[10.5px] text-text-subtle">
                {(row.cycles[0]?.phases ?? []).join(' -> ') || '—'}
              </span>
            </div>
          );
        }
        const r = row.cycle;
        const phases = r.phases ?? [];
        return (
          <div class="min-w-[160px]">
            <PhaseBar durations={r.phase_durations ?? {}} height={10} />
            <div class="mt-1 truncate font-mono text-[10.5px] text-text-muted">
              {phases.length > 0 ? phases.join(' -> ') : '—'}
            </div>
            <Show when={row.change}>
              <div class="mt-0.5 text-[10.5px] text-accent">{row.change}</div>
            </Show>
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
      render: (row) => {
        if (row.kind === 'expanded-header') return <span class="text-text-subtle">—</span>;
        const txt =
          row.kind === 'effect-group'
            ? row.totalMs > 0
              ? formatDuration(row.totalMs)
              : '—'
            : durationOf(row.cycle);
        return <span class="font-mono text-xs text-text-muted">{txt}</span>;
      },
    },
    {
      key: 'agent',
      header: 'Agent',
      width: '120px',
      render: (row) => {
        if (row.kind !== 'cycle') return <span class="text-text-subtle">—</span>;
        const r = row.cycle;
        const ag = r.reporting_agent_label ?? (r as { agent_id?: string }).agent_id ?? '—';
        return <span class="font-mono text-[11px] text-text-muted">{ag}</span>;
      },
    },
    {
      key: 'model',
      header: 'Model',
      width: '120px',
      render: (row) => {
        if (row.kind !== 'cycle') return <span class="text-text-subtle">—</span>;
        return <span class="font-mono text-[11px] text-text-muted">{row.cycle.model_id || '—'}</span>;
      },
    },
    {
      key: 'id',
      header: 'Run',
      width: '170px',
      render: (row) => {
        if (row.kind === 'expanded-header') {
          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                toggleGroup(row.key);
              }}
              class="text-[11px] text-accent hover:underline"
            >
              Re-collapse
            </button>
          );
        }
        if (row.kind === 'effect-group') {
          return (
            <div class="flex flex-col gap-0.5">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleGroup(row.key);
                }}
                class="self-start text-[11px] text-accent hover:underline"
              >
                Expand {row.cycles.length} cycles
              </button>
              <span class="font-mono text-[10px] text-text-muted" title={`${row.latestRunId ?? ''} → ${row.oldestRunId ?? ''}`}>
                {shortId(row.latestRunId)} → {shortId(row.oldestRunId)}
              </span>
            </div>
          );
        }
        const r = row.cycle;
        return (
          <div class="flex flex-col gap-0.5">
            <IdLink id={r.run_id} onClick={() => openCycle(r)} />
            <span class="line-clamp-2 text-[11px] text-text-muted">{r.narrative}</span>
          </div>
        );
      },
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
            title="Grant one-time browser consent and pull detectable local agent transcripts into transcripts/."
          >
            {busy() === 'ingest' ? 'Ingesting…' : 'Ingest transcripts'}
          </button>
          <button
            type="button"
            disabled={busy() !== null}
            onClick={() => void trigger('full')}
            class="rounded-md bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
            title="First use grants local transcript import consent; later dream runs reuse that browser consent."
          >
            {busy() === 'full' ? 'Dreaming…' : transcriptImportConsented() ? 'Import and dream' : 'Allow import and dream'}
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
          {(r) => {
            const idle = () => isIdleReason(r().reason);
            const headline = () => (idle() ? 'Idle cycle' : (r().status ?? 'completed'));
            return (
              <div class="flex flex-col gap-1.5 rounded-md hairline bg-surface px-3 py-2 text-[11.5px]">
                <div class="flex flex-wrap items-center gap-2 text-text">
                  <Chip variant={idle() ? 'neutral' : statusVariant(r().status)}>
                    {headline()}
                  </Chip>
                  <Show when={r().reason}>
                    <span class="font-mono text-[10.5px] text-text-subtle">
                      {reasonLabel(r().reason)}
                    </span>
                  </Show>
                  <span class="text-text-subtle">·</span>
                  <span class="font-mono text-[10.5px] text-text-muted">
                    {(r().phases ?? []).join(' → ') || '—'}
                  </span>
                  <Show when={r().duration_ms !== undefined}>
                    <span class="text-text-subtle">·</span>
                    <span class="font-mono text-[10.5px] text-text-muted">
                      {r().duration_ms}ms
                    </span>
                  </Show>
                  <Show when={r().run_id}>
                    <span class="text-text-subtle">·</span>
                    <button
                      type="button"
                      onClick={() => navigate(`/runs?id=${encodeURIComponent(r().run_id!)}`)}
                      class="font-mono text-[10.5px] text-accent hover:underline"
                    >
                      {r().run_id}
                    </button>
                  </Show>
                </div>
                <Show when={reasonExplainer(r().reason)}>
                  <p class="text-[11px] leading-snug text-text-muted">
                    {reasonExplainer(r().reason)}
                  </p>
                </Show>
                <p
                  class={`text-[11px] leading-snug ${
                    funnelValue(r(), 'created') > 0 ? 'text-success' : 'text-text-muted'
                  }`}
                >
                  {dreamProofSentence(r())}
                </p>
              </div>
            );
          }}
        </Show>
      </section>

      <Show when={idleStreakActive()}>
        <section class="flex items-start gap-3 rounded-md border border-border-subtle bg-surface px-4 py-3">
          <div class="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-text-subtle" />
          <div class="flex flex-col gap-0.5">
            <div class="text-[12.5px] font-medium text-text">
              Idle and healthy · {idleStreakLength()} consecutive cycle
              {idleStreakLength() === 1 ? '' : 's'} with no new signal
            </div>
            <p class="text-[11.5px] leading-snug text-text-muted">
              The dream pipeline is running on schedule but nothing new to consume.
              Transcripts last contained signal at{' '}
              <Show
                when={lastSignalTimestamp()}
                fallback={<span class="font-mono">unknown</span>}
              >
                <span class="font-mono">{formatDateLong(lastSignalTimestamp()!)}</span>
              </Show>
              . New cycles will produce events automatically once your agents generate
              fresh sessions. No action required.
            </p>
          </div>
        </section>
      </Show>

      <Show when={skippedFailures().length > 0}>
        <section class="flex flex-col gap-2">
          <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
            Cycles that failed unexpectedly · {skippedFailures().length}
          </div>
          <div class="flex flex-col">
            <For each={skippedFailures().slice(0, 5)}>
              {(r) => (
                <div class="hairline-b flex items-center gap-3 py-1.5 text-[12px]">
                  <Chip variant={reasonVariant(r.reason)}>{r.reason ?? 'unknown'}</Chip>
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
        <CompactStat label="Success" value={`${successRate(dreams())}%`} tone={successRate(dreams()) >= 80 ? 'ok' : successRate(dreams()) > 50 ? 'warn' : successRate(dreams()) > 0 ? 'danger' : 'default'} />
        <CompactStat label="Avg duration" value={avgDuration(dreams())} />
        <CompactStat label="Approved" value={formatNumber(sumFunnel(dreams(), 'approved'))} />
        <CompactStat
          label="Idle"
          value={formatNumber(skipped().length - skippedFailures().length)}
        />
        <CompactStat
          label="Failed"
          value={formatNumber(skippedFailures().length)}
          tone={skippedFailures().length === 0 ? 'default' : 'danger'}
        />
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
                  onClick={() => openCycle(r)}
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

      <Show when={highSignalCycles().length > 0}>
        <section class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-accent/40 bg-[color-mix(in_oklab,rgb(var(--c-accent))_7%,rgb(var(--c-surface)))] px-4 py-3">
          <div class="flex flex-col gap-0.5">
            <div class="text-[10px] uppercase tracking-[0.08em] text-accent">Change points</div>
            <div class="text-[12.5px] text-text">
              {highSignalCycles().length} high-signal cycle{highSignalCycles().length === 1 ? '' : 's'} in this window
            </div>
            <Show when={topChangePoint()}>
              {(r) => (
                <div class="text-[11px] text-text-muted">
                  Top: <span class="font-mono">{r().run_id}</span> · {r().change_point?.label}
                </div>
              )}
            </Show>
          </div>
          <Show when={topChangePoint()}>
            {(r) => (
              <button
                type="button"
                onClick={() => openCycle(r())}
                class="rounded-md hairline px-3 py-1.5 text-[11.5px] text-text hover:bg-surface-elevated"
              >
                Inspect top change
              </button>
            )}
          </Show>
        </section>
      </Show>

      <section class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
            Dream cycles · showing {filteredDreams().length} of {dreams().length}
            <Show when={viewFilter() !== 'all'}>
              <span class="ml-1 normal-case tracking-normal text-text-muted">
                ({viewFilter()})
              </span>
            </Show>
            <Show when={viewFilter() === 'all' && collapseIdle() && collapsedCount() > 0}>
              <span class="ml-1 normal-case tracking-normal text-text-muted">
                ({collapsedCount()} no-op collapsed)
              </span>
            </Show>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <div role="tablist" class="flex items-center rounded-md hairline bg-surface text-[11px]">
              {(
                [
                  ['all', `All cycles · ${dreams().length}`],
                  [
                    'changes',
                    `Changed memory · ${dreams().filter((c) => !isNoopCycle(c)).length}`,
                  ],
                  [
                    'material',
                    `Material writes · ${dreams().filter((c) => hasMaterialEffect(c)).length}`,
                  ],
                  [
                    'failures',
                    `Failures only · ${dreams().filter((c) => isFailureCycle(c)).length}`,
                  ],
                ] as const
              ).map(([value, label]) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewFilter() === value}
                  onClick={() => setViewFilter(value)}
                  title={
                    value === 'all'
                      ? 'All dream cycles, including no-op and skipped cycles.'
                      : value === 'changes'
                        ? 'Dream cycles that produced a change point instead of a no-op.'
                        : value === 'material'
                          ? 'Dream cycles that wrote or changed memory records.'
                          : 'Dream cycles that failed for a non-idle reason.'
                  }
                  class={
                    viewFilter() === value
                      ? 'rounded-md bg-accent px-2.5 py-1 text-accent-fg'
                      : 'px-2.5 py-1 text-text-muted hover:text-text'
                  }
                >
                  {label}
                </button>
              ))}
            </div>
            <label
              class="flex items-center gap-1.5 text-[11px] text-text-muted"
              title="When viewing All, group adjacent score-0 cycles into a single collapsed row."
            >
              <input
                type="checkbox"
                checked={collapseIdle()}
                disabled={viewFilter() !== 'all'}
                onChange={(e) => setCollapseIdle(e.currentTarget.checked)}
              />
              Collapse no-op runs
            </label>
          </div>
        </div>
        <details class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text-muted">
          <summary class="cursor-pointer text-[11.5px] font-medium text-text">
            Dream-cycle glossary
          </summary>
          <div class="mt-2 grid gap-2 sm:grid-cols-2">
            <p>
              <span class="font-medium text-text">Dream cycles</span> are only runs with kind <span class="font-mono">dream</span> or <span class="font-mono">semantic_dream</span>.
              Background <span class="font-mono">consolidation</span> jobs are listed on Runs instead.
            </p>
            <p>
              <span class="font-medium text-text">Collapsed groups</span> appear as table rows labeled <span class="font-mono">collapsed × N</span>.
              They are adjacent score-0 cycles with the same effect signature and expand from the Run column.
            </p>
            <p>
              <span class="font-medium text-text">Scores</span> are deterministic review priority from 0 to 100. Zero means no observable dream effect.
              Medium/high rows are candidates for inspection, not proof of a causal regime change.
            </p>
            <p>
              <span class="font-medium text-text">Material</span> means memory actually changed: proposals generated or approved,
              learned context created, superseded, or rejected. Query-family selection alone is not material.
            </p>
            <p>
              <span class="font-medium text-text">Drift/anomaly</span> means transcript volume, mode/status/model/phases, funnel counts,
              or phase duration changed versus recent cycles.
            </p>
          </div>
        </details>
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
              items={groupedRows()}
              columns={columns}
              rowKey={(r) =>
                r.kind === 'cycle' ? r.cycle.run_id : r.kind === 'expanded-header' ? `header:${r.key}` : r.key
              }
              rowClass={(r) => {
                if (r.kind === 'expanded-header') {
                  return 'bg-[color-mix(in_oklab,rgb(var(--c-accent))_6%,transparent)] text-[11px]';
                }
                if (r.kind === 'effect-group') return 'bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_4%,transparent)]';
                const accent = rowAccentClass(r.cycle);
                if (accent) return accent;
                if (r.change) return 'border-l-2 border-l-accent bg-[color-mix(in_oklab,rgb(var(--c-accent))_5%,transparent)]';
                return undefined;
              }}
              onRowClick={(r) => {
                if (r.kind === 'cycle') openCycle(r.cycle);
                else toggleGroup(r.key);
              }}
              empty={
                <EmptyState
                  icon={Moon}
                  title="No dream cycles yet"
                  description="Import detectable local transcripts and run the first dream cycle."
                />
              }
            />
          </Show>
        </Show>
      </section>

      <SlideOver
        open={selected() !== null}
        onOpenChange={(o) => !o && openCycle(null)}
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

function TraceRow(props: { label: string; value: string | number | boolean | undefined | null; tone?: 'ok' | 'warn' | 'danger' }): JSX.Element {
  const display = (): string => {
    const v = props.value;
    if (v === undefined || v === null || v === '') return '—';
    if (typeof v === 'boolean') return v ? 'yes' : 'no';
    return String(v);
  };
  const tone =
    props.tone === 'ok'
      ? 'text-success'
      : props.tone === 'warn'
        ? 'text-warn'
        : props.tone === 'danger'
          ? 'text-danger'
          : 'text-text';
  return (
    <div class="flex items-baseline justify-between gap-3 border-b border-border-subtle/40 py-1 last:border-b-0">
      <span class="text-text-subtle">{props.label}</span>
      <span class={`min-w-0 break-words text-right font-mono text-[11px] ${tone}`}>{display()}</span>
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
          <Chip variant={isIdleReason(summaryDict().reason as string) ? 'neutral' : 'warn'}>
            {reasonLabel(summaryDict().reason as string)}
          </Chip>
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

      <Show when={props.run.change_point && !props.run.change_point.is_noop ? props.run.change_point : null}>
        {(cp) => (
          <section class="flex flex-col gap-2 rounded-md border border-accent/40 bg-[color-mix(in_oklab,rgb(var(--c-accent))_7%,rgb(var(--c-surface)))] p-3">
            <div class="flex flex-wrap items-center gap-2">
              <Chip variant={changePointVariant(props.run)}>{cp().kind.replace('_', ' ')}</Chip>
              <span class="font-mono text-[11px] text-text-muted">score {cp().score}</span>
              <span class="text-[11px] text-text-muted">{cp().severity}</span>
            </div>
            <p class="text-[12px] leading-5 text-text">{cp().label}</p>
            <p class="text-[11px] leading-5 text-text-muted">
              Score rationale: material memory changes and non-idle failures rank highest; drift and slow phases are medium-priority inspection candidates.
            </p>
            <div class="flex flex-wrap gap-1">
              <For each={cp().contributors.slice(0, 4)}>
                {(item) => (
                  <span class="rounded-sm bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-muted" title={JSON.stringify(item)}>
                    {item.key}
                  </span>
                )}
              </For>
            </div>
          </section>
        )}
      </Show>

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

      <Show when={props.run.trace_summary}>
        {(trace) => (
          <section class="flex flex-col gap-1.5">
            <div class="flex flex-wrap items-center gap-1.5">
              <h4 class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">Dream trace</h4>
              <Chip variant={trace().input_consumed ? 'ok' : 'neutral'}>
                input {trace().input_consumed ? 'consumed' : 'idle'}
              </Chip>
              <Show when={traceNoMaterializationReason(props.run)}>
                {(reason) => <Chip variant="warn">{reason()}</Chip>}
              </Show>
            </div>
            <div class="flex flex-col rounded-md hairline bg-surface p-2.5 text-[12px]">
              <TraceRow label="Rows scanned" value={trace().rows_scanned} />
              <TraceRow label="Rows gathered" value={trace().rows_gathered} />
              <TraceRow label="Families selected" value={`${trace().families_selected ?? 0}/${trace().families_considered ?? 0}`} />
              <TraceRow label="Proposals" value={trace().proposals_generated} />
              <TraceRow label="Verifier" value={verifierSummary(props.run)} />
              <TraceRow label="Learned records" value={trace().learned_context_created} tone={trace().learned_context_created ? 'ok' : undefined} />
              <TraceRow label="Retention" value={trace().retention_status} />
              <TraceRow label="Fallback" value={trace().fallback_reason} />
            </div>
            <Show when={(trace().drop_reasons ?? []).length > 0 || (trace().promoted_record_ids ?? []).length > 0}>
              <div class="flex flex-wrap gap-1">
                <For each={(trace().drop_reasons ?? []).slice(0, 4)}>
                  {(reason) => <Chip variant="neutral">{reason}</Chip>}
                </For>
                <For each={(trace().promoted_record_ids ?? []).slice(0, 3)}>
                  {(id) => <Chip variant="ok">{shortId(id)}</Chip>}
                </For>
              </div>
            </Show>
          </section>
        )}
      </Show>

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
