import { createResource, createSignal, For, onMount, Show, type JSX } from 'solid-js';
import { useSearchParams } from '@solidjs/router';
import { Tabs as KTabs } from '@kobalte/core/tabs';
import { Tabs } from '~/components/Tabs';
import { Collapsible } from '@kobalte/core/collapsible';
import { ChevronDown } from 'lucide-solid';
import { getAutoReviewerStats, getSettings, getUiMeta, ingestTranscripts, runAutoReviewerDryRun, runDream, setSemanticDreamMode, updateAutoReviewerConfig, updateSemanticConfig } from '~/api/client';
import type { DreamRunResult, TranscriptsIngestResult } from '~/api/client';
import type { AutoReviewerDryRun, AutoReviewerRule, AutoReviewerStats, OverviewPayload, SettingsPayload, UiMeta } from '~/api/types';
import { Page } from '~/components/Page';
import { Chip } from '~/components/Chip';
import { LoadingPage } from '~/components/Loading';
import { ErrorState } from '~/components/ErrorState';

type ReadinessLike = {
  mode?: string;
  posture?: string;
  next_action?: string;
  next_step?: string;
  status?: string;
  mode_reason?: string;
  [k: string]: unknown;
};

function readinessOf(p: OverviewPayload | undefined): ReadinessLike | null {
  if (!p) return null;
  // Old shape: a single readiness object. Newer overview spreads the same
  // signals as flat top-level fields plus a runtime_management block.
  const explicit = (p as { readiness?: unknown }).readiness;
  if (explicit && typeof explicit === 'object') return explicit as ReadinessLike;

  const px = p as {
    product_posture?: string;
    next_action?: string | null;
    semantic_capability_state?: string;
    semantic_unavailability_reason?: string | null;
    runtime_management?: { policy_mode?: string; active_phase?: string; health?: string };
  };
  const runtime = px.runtime_management ?? {};
  const composed: ReadinessLike = {};
  if (px.product_posture) composed.posture = px.product_posture;
  if (px.next_action !== undefined && px.next_action !== null) {
    composed.next_action = px.next_action;
  }
  if (runtime.policy_mode) composed.mode = runtime.policy_mode;
  if (px.semantic_capability_state) composed.status = px.semantic_capability_state;
  if (px.semantic_unavailability_reason) {
    composed.mode_reason = px.semantic_unavailability_reason;
  }
  if (runtime.active_phase) {
    (composed as Record<string, unknown>)['active_phase'] = runtime.active_phase;
  }
  if (runtime.health) {
    (composed as Record<string, unknown>)['runtime_health'] = runtime.health;
  }
  return Object.keys(composed).length > 0 ? composed : null;
}

function readinessTone(s: string | undefined): 'ok' | 'warn' | 'danger' | 'neutral' {
  const v = (s ?? '').toLowerCase();
  if (v.includes('ok') || v.includes('ready') || v.includes('healthy')) return 'ok';
  if (v.includes('warn') || v.includes('degrad')) return 'warn';
  if (v.includes('error') || v.includes('fail') || v.includes('blocked')) return 'danger';
  return 'neutral';
}

const MODE_OPTIONS = ['auto', 'full', 'lite', 'disabled'] as const;
type SemanticMode = (typeof MODE_OPTIONS)[number];

function ReadinessSection(props: { overview: OverviewPayload | undefined }): JSX.Element {
  const rd = () => readinessOf(props.overview);

  return (
    <Show
      when={rd()}
      fallback={
        <div class="flex flex-col gap-2 text-sm">
          <p class="text-text">Readiness signals haven't been emitted yet for this workspace.</p>
          <p class="text-text-muted text-[12.5px]">
            Readiness reports the runtime posture, semantic dream mode, and the
            recommended next action. It populates after the first dream cycle
            runs (semantic or full). Until then the workspace is healthy by
            default — no action needed.
          </p>
          <p class="text-text-muted text-[12.5px]">
            To force a readiness sample, run:{' '}
            <code class="rounded bg-surface-elevated px-1 py-0.5 font-mono text-[11.5px]">
              opendream dream run --workspace &lt;path&gt;
            </code>
          </p>
        </div>
      }
    >
      {(r) => {
        const status = () => r().status ?? r().posture ?? 'unknown';
        return (
          <div class="flex flex-col gap-2 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-text-muted">Mode</span>
              <span class="font-mono text-xs">{r().mode ?? '—'}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-text-muted">Posture</span>
              <Chip variant={readinessTone(status())}>{String(r().posture ?? status())}</Chip>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-text-muted">Next action</span>
              <span class="text-xs">{r().next_action ?? r().next_step ?? '—'}</span>
            </div>
            <Show when={r().mode_reason}>
              <div class="flex items-center justify-between">
                <span class="text-text-muted">Mode reason</span>
                <span class="text-xs">{String(r().mode_reason)}</span>
              </div>
            </Show>
          </div>
        );
      }}
    </Show>
  );
}

function RetentionSettings(props: { overview: SettingsPayload | undefined; onAfter: () => void }): JSX.Element {
  const retention = () => props.overview?.semantic_config?.retention ?? {};
  const [days, setDays] = createSignal(String(retention().learned_context_archive_grace_days ?? 7));
  const [contexts, setContexts] = createSignal(String(retention().learned_context_archive_grace_contexts ?? 0));
  const [saving, setSaving] = createSignal(false);
  const [msg, setMsg] = createSignal('');

  async function handleSave() {
    setSaving(true);
    setMsg('');
    try {
      await updateSemanticConfig({
        retention: {
          learned_context_archive_grace_days: Math.max(0, Number(days()) || 0),
          learned_context_archive_grace_contexts: Math.max(0, Number(contexts()) || 0),
        },
      });
      setMsg('Saved.');
      props.onAfter();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div class="rounded-md hairline bg-surface p-4">
      <div class="flex flex-col gap-3">
        <div>
          <h3 class="text-sm font-medium text-text">Learned-context retention</h3>
          <p class="mt-1 max-w-3xl text-[11.5px] leading-5 text-text-muted">
            Archive stale learned context after the calendar grace has elapsed, and optionally
            after enough new context assemblies prove the workspace has been active.
          </p>
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <label class="flex flex-col gap-1 text-[11px] text-text-muted">
            Calendar grace · days
            <input
              type="number"
              min="0"
              value={days()}
              onInput={(e) => setDays(e.currentTarget.value)}
              class="h-9 rounded-md border border-border bg-surface-elevated px-2 text-sm text-text focus:border-accent focus:outline-none"
            />
          </label>
          <label class="flex flex-col gap-1 text-[11px] text-text-muted">
            Activity grace · contexts
            <input
              type="number"
              min="0"
              value={contexts()}
              onInput={(e) => setContexts(e.currentTarget.value)}
              class="h-9 rounded-md border border-border bg-surface-elevated px-2 text-sm text-text focus:border-accent focus:outline-none"
            />
          </label>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving()}
            class="rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 disabled:opacity-50"
          >
            {saving() ? 'Saving…' : 'Save retention'}
          </button>
          <Show when={msg()}>
            <span class="text-xs text-text-muted">{msg()}</span>
          </Show>
        </div>
      </div>
    </div>
  );
}

function AdvancedTab(props: { overview: OverviewPayload | undefined; onRefetch: () => void }): JSX.Element {
  const rd = () => readinessOf(props.overview);
  const currentMode = (): SemanticMode => (rd()?.mode as SemanticMode) ?? 'auto';
  const [mode, setMode] = createSignal<SemanticMode>(currentMode());
  const [saving, setSaving] = createSignal(false);
  const [saveMsg, setSaveMsg] = createSignal('');

  async function handleSave() {
    setSaving(true);
    setSaveMsg('');
    try {
      await setSemanticDreamMode({ mode: mode() });
      setSaveMsg('Saved.');
      props.onRefetch();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div class="flex flex-col gap-5">
      <div class="flex flex-col gap-2">
        <div class="text-xs font-medium text-text">Semantic dream mode</div>
        <div class="inline-flex items-center gap-px rounded-md bg-surface p-0.5 hairline w-fit">
          {MODE_OPTIONS.map((m) => (
            <button
              type="button"
              onClick={() => setMode(m)}
              class={`rounded px-3 py-1 text-xs transition-colors duration-150 ${
                mode() === m
                  ? 'bg-surface-elevated text-text'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving()}
            class="rounded-md bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-fg transition-all duration-150 hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          >
            {saving() ? 'Saving…' : 'Apply'}
          </button>
          <Show when={saveMsg()}>
            <span class="text-xs text-text-muted">{saveMsg()}</span>
          </Show>
        </div>
      </div>

      <RetentionSettings overview={props.overview as SettingsPayload | undefined} onAfter={props.onRefetch} />

      <DreamControls onAfter={props.onRefetch} />

      <DiagnosticsSection overview={props.overview} />

      <Show when={props.overview}>
        {(ov) => (
          <Collapsible>
            <Collapsible.Trigger class="flex items-center gap-1 text-xs text-text-muted hover:text-text">
              <ChevronDown size={12} class="ui-expanded:rotate-180 transition-transform" />
              Raw readiness JSON
            </Collapsible.Trigger>
            <Collapsible.Content>
              <pre class="mt-2 overflow-x-auto rounded bg-surface-elevated p-3 text-2xs text-text-muted">
                {JSON.stringify(readinessOf(ov()), null, 2)}
              </pre>
            </Collapsible.Content>
          </Collapsible>
        )}
      </Show>
    </div>
  );
}

function DreamControls(props: { onAfter: () => void }): JSX.Element {
  const [busy, setBusy] = createSignal<string | null>(null);
  const [dream, setDream] = createSignal<DreamRunResult | null>(null);
  const [ingest, setIngest] = createSignal<TranscriptsIngestResult | null>(null);
  const [err, setErr] = createSignal<string | null>(null);

  async function trigger(action: 'full' | 'semantic' | 'hybrid' | 'ingest') {
    setBusy(action);
    setErr(null);
    try {
      if (action === 'ingest') {
        const r = await ingestTranscripts(false);
        setIngest(r);
      } else {
        const r = await runDream(action);
        setDream(r);
      }
      props.onAfter();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div class="flex flex-col gap-3">
      <div class="text-xs font-medium text-text">Dream + ingest</div>
      <p class="text-[11.5px] text-text-muted">
        Force a dream cycle or pull in fresh agent session transcripts without
        dropping to the CLI. Ingest auto-detect currently supports Claude Code (
        <code class="mx-1 rounded bg-surface-elevated px-1 font-mono text-[11px]">
          ~/.claude/projects/&lt;slug&gt;
        </code>
        ). Codex, Cursor, Gemini, and GitHub Copilot can be imported with{' '}
        <code class="mx-1 rounded bg-surface-elevated px-1 font-mono text-[11px]">
          opendream transcripts ingest --from &lt;path&gt;
        </code>
        .
      </p>
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy() !== null}
          onClick={() => void trigger('ingest')}
          class="rounded-md hairline px-3 py-1.5 text-[11.5px] text-text hover:bg-surface-elevated disabled:opacity-50"
        >
          {busy() === 'ingest' ? 'Ingesting…' : 'Ingest transcripts'}
        </button>
        <button
          type="button"
          disabled={busy() !== null}
          onClick={() => void trigger('full')}
          class="rounded-md bg-accent px-3 py-1.5 text-[11.5px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
        >
          {busy() === 'full' ? 'Dreaming…' : 'Dream now (full)'}
        </button>
        <button
          type="button"
          disabled={busy() !== null}
          onClick={() => void trigger('semantic')}
          class="rounded-md hairline px-3 py-1.5 text-[11.5px] text-text hover:bg-surface-elevated disabled:opacity-50"
        >
          {busy() === 'semantic' ? 'Dreaming…' : 'Dream (semantic)'}
        </button>
        <button
          type="button"
          disabled={busy() !== null}
          onClick={() => void trigger('hybrid')}
          class="rounded-md hairline px-3 py-1.5 text-[11.5px] text-text hover:bg-surface-elevated disabled:opacity-50"
        >
          {busy() === 'hybrid' ? 'Dreaming…' : 'Dream (hybrid)'}
        </button>
      </div>
      <Show when={err()}>
        <div class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-danger">
          {err()}
        </div>
      </Show>
      <Show when={ingest()}>
        {(r) => (
          <div class="rounded-md hairline bg-surface px-3 py-2 text-[11.5px] text-text">
            <span class="font-mono text-text-subtle">ingest:</span>{' '}
            {r().status} · seen {r().files_seen ?? 0} · written {r().files_written ?? 0}{' '}
            · skipped {r().files_skipped ?? 0} · rows in/out{' '}
            {r().rows_in ?? 0}/{r().rows_out ?? 0}
          </div>
        )}
      </Show>
      <Show when={dream()}>
        {(r) => {
          const idle =
            r().reason === 'no-episodes' || r().reason === 'insufficient-signal';
          const reasonLabel =
            r().reason === 'no-episodes'
              ? 'no transcripts'
              : r().reason === 'insufficient-signal'
                ? 'no new signal'
                : r().reason ?? null;
          const explainer = idle
            ? r().reason === 'no-episodes'
              ? 'No agent transcripts to consume yet. Click "Ingest transcripts" or run more agent sessions.'
              : 'Pipeline ran and found nothing new — healthy idle state. New events appear once agents generate fresh sessions.'
            : null;
          return (
            <div class="flex flex-col gap-1.5 rounded-md hairline bg-surface px-3 py-2 text-[11.5px]">
              <div class="flex flex-wrap items-center gap-2 text-text">
                <Chip variant={idle ? 'neutral' : 'ok'}>
                  {idle ? 'Idle cycle' : (r().status ?? 'completed')}
                </Chip>
                <Show when={reasonLabel}>
                  <span class="font-mono text-[10.5px] text-text-subtle">{reasonLabel}</span>
                </Show>
                <span class="text-text-subtle">·</span>
                <span class="font-mono text-[10.5px] text-text-muted">
                  {(r().phases ?? []).join(' → ') || '—'}
                </span>
                <Show when={r().duration_ms !== undefined}>
                  <span class="text-text-subtle">·</span>
                  <span class="font-mono text-[10.5px] text-text-muted">{r().duration_ms}ms</span>
                </Show>
                <Show when={r().appended_events !== undefined}>
                  <span class="text-text-subtle">·</span>
                  <span class="font-mono text-[10.5px] text-text-muted">
                    appended {r().appended_events}
                  </span>
                </Show>
                <Show when={r().gathered_rows !== undefined}>
                  <span class="text-text-subtle">·</span>
                  <span class="font-mono text-[10.5px] text-text-muted">
                    gathered {r().gathered_rows}
                  </span>
                </Show>
              </div>
              <Show when={explainer}>
                <p class="text-[11px] leading-snug text-text-muted">{explainer}</p>
              </Show>
            </div>
          );
        }}
      </Show>
    </div>
  );
}

function coverageTone(value: unknown): 'ok' | 'warn' | 'danger' | 'neutral' {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'neutral';
  const pct = value <= 1 ? value * 100 : value;
  if (pct >= 90) return 'ok';
  if (pct >= 60) return 'warn';
  return 'danger';
}

function formatScalar(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (v <= 1 && v >= 0 && !Number.isInteger(v)) return `${(v * 100).toFixed(1)}%`;
    return String(v);
  }
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (typeof v === 'string') return v || '—';
  return String(v);
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function DiagValue(props: { value: unknown; depth?: number; coverageKey?: boolean }): JSX.Element {
  const depth = props.depth ?? 0;
  const v = props.value;
  if (Array.isArray(v)) {
    if (v.length === 0) return <span class="font-mono text-[11.5px] text-text-subtle">[]</span>;
    return (
      <div class="flex flex-col gap-0.5">
        <For each={v as unknown[]}>
          {(item, i) => (
            <div class="flex items-start gap-2">
              <span class="font-mono text-[10.5px] text-text-subtle pt-0.5">{i()}</span>
              <DiagValue value={item} depth={depth + 1} />
            </div>
          )}
        </For>
      </div>
    );
  }
  if (isPlainObject(v)) {
    const entries = Object.entries(v);
    if (entries.length === 0) {
      return <span class="font-mono text-[11.5px] text-text-subtle">{'{}'}</span>;
    }
    return (
      <div
        class={`flex flex-col gap-0.5 ${depth > 0 ? 'border-l border-border pl-2 ml-1' : ''}`}
      >
        <For each={entries}>
          {([ck, cv]) => (
            <div class="flex flex-wrap items-baseline gap-x-2">
              <span class="font-mono text-[10.5px] text-text-subtle">{ck}</span>
              <span class="flex-1 min-w-0 break-words">
                <DiagValue value={cv} depth={depth + 1} />
              </span>
            </div>
          )}
        </For>
      </div>
    );
  }
  if (props.coverageKey && typeof v === 'number') {
    return <Chip variant={coverageTone(v)}>{formatScalar(v)}</Chip>;
  }
  return (
    <span class="font-mono text-[11.5px] text-text break-words">{formatScalar(v)}</span>
  );
}

function DiagnosticsBlock(props: {
  title: string;
  data: Record<string, unknown> | undefined;
}): JSX.Element {
  const entries = (): Array<[string, unknown]> => {
    const d = props.data;
    if (!d || typeof d !== 'object') return [];
    return Object.entries(d);
  };
  return (
    <Show when={entries().length > 0}>
      <div class="flex flex-col gap-1.5">
        <div class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">{props.title}</div>
        <div class="flex flex-col gap-1 rounded-md hairline bg-surface p-2.5 overflow-x-auto">
          <For each={entries()}>
            {([k, v]) => {
              const isCoverageKey = /coverage|ratio|rate|score|percent/i.test(k);
              return (
                <div class="flex flex-wrap items-baseline gap-x-3 text-[12px] border-b border-border-subtle/40 last:border-b-0 py-0.5">
                  <span class="font-mono text-text-muted whitespace-nowrap">{k}</span>
                  <span class="flex-1 min-w-0">
                    <DiagValue value={v} coverageKey={isCoverageKey} />
                  </span>
                </div>
              );
            }}
          </For>
        </div>
      </div>
    </Show>
  );
}

function DiagnosticsSection(props: { overview: OverviewPayload | undefined }): JSX.Element {
  const ov = (): (OverviewPayload & {
    signal_coverage?: Record<string, unknown>;
    activation_diagnostics?: Record<string, unknown>;
  }) | undefined => props.overview as never;
  const sig = () => ov()?.signal_coverage;
  const act = () => ov()?.activation_diagnostics;
  return (
    <Show when={sig() || act()}>
      <div class="flex flex-col gap-3">
        <div class="text-xs font-medium text-text">Fidelity diagnostics</div>
        <DiagnosticsBlock title="Signal coverage" data={sig()} />
        <DiagnosticsBlock title="Activation diagnostics" data={act()} />
      </div>
    </Show>
  );
}

function AboutTab(props: { meta: UiMeta | undefined }): JSX.Element {
  return (
    <div class="flex flex-col gap-4 text-sm">
      <Show
        when={props.meta}
        fallback={<p class="text-text-muted">No version info available.</p>}
      >
        {(m) => (
          <div class="flex flex-col gap-2">
            {Object.entries(m()).map(([k, v]) => (
              <div class="flex items-center justify-between">
                <span class="text-text-muted">{k}</span>
                <span class="font-mono text-xs">{String(v)}</span>
              </div>
            ))}
          </div>
        )}
      </Show>
      <div class="flex flex-col gap-1">
        <div class="text-xs font-medium text-text">Documentation</div>
        <a
          href="https://github.com/pylit-ai/opendream"
          target="_blank"
          rel="noopener noreferrer"
          class="text-xs text-accent hover:underline"
        >
          GitHub — pylit-ai/opendream
        </a>
      </div>
    </div>
  );
}

function formatTs(ts: string | undefined): string {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

const RULE_LABELS: Record<string, { name: string; explainer: string }> = {
  low_confidence_age: {
    name: 'Low-confidence + aged',
    explainer:
      'Auto-suppresses durable memories whose confidence dropped below the threshold AND that have been sitting in the review queue past the age cutoff. Catches stale low-signal facts so operators do not have to triage them.',
  },
  contested_dominant: {
    name: 'Contested dominant winner',
    explainer:
      'When two memories conflict and one has a clear confidence advantage, this auto-approves the dominant side. The losing side stays available via lineage for audit. Off by default; turn on once you trust the confidence delta tuning.',
  },
  stale_diff: {
    name: 'Stale large-diff runs',
    explainer:
      'Marks `large_diff` and `failed_run` review items stale once they exceed the age threshold without operator action. Keeps the queue from accumulating runs nobody is going to review. Off by default.',
  },
  unused_retrieval: {
    name: 'Unused suspicious retrieval',
    explainer:
      'Suppresses `suspicious_retrieval` items that no downstream context assembly references after the grace window. If a retrieval was never used, the suspicion is moot. Off by default.',
  },
  fallback_mark_stale: {
    name: 'Fallback · defer (mark stale)',
    explainer:
      'Catch-all for queue items no specific rule matched. Recommends mark_stale so the queue stays bounded; operator can override per row. Off by default — turn on if you want a deterministic suggestion for every queue row.',
  },
};

function AutomationRuleRow(props: {
  rule: AutoReviewerRule;
  onSave: (rule_id: string, enabled: boolean, thresholds: Record<string, unknown>) => Promise<void>;
}): JSX.Element {
  const meta = () => RULE_LABELS[props.rule.rule_id];
  const description = () =>
    (props.rule as { description?: string }).description ?? meta()?.explainer ?? '';
  const [enabled, setEnabled] = createSignal(props.rule.enabled);
  const [thresholds, setThresholds] = createSignal<Record<string, unknown>>(
    { ...props.rule.threshold_summary },
  );
  const [saving, setSaving] = createSignal(false);
  const [msg, setMsg] = createSignal('');
  const isDirty = () =>
    enabled() !== props.rule.enabled ||
    JSON.stringify(thresholds()) !== JSON.stringify(props.rule.threshold_summary);
  const handleReset = () => {
    setEnabled(props.rule.enabled);
    setThresholds({ ...props.rule.threshold_summary });
    setMsg('');
  };

  async function handleSave() {
    setSaving(true);
    setMsg('');
    try {
      await props.onSave(props.rule.rule_id, enabled(), thresholds());
      setMsg('Saved.');
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const thresholdEntries = (): Array<[string, unknown]> =>
    Object.entries(thresholds());

  return (
    <div class="flex flex-col gap-2 rounded-md hairline bg-surface p-3">
      <div class="flex items-start justify-between gap-3">
        <div class="flex flex-col gap-0.5 min-w-0 flex-1">
          <span class="text-[12.5px] font-medium text-text">
            {meta()?.name ?? props.rule.rule_id}
          </span>
          <span class="font-mono text-[10.5px] text-text-subtle">{props.rule.rule_id}</span>
          <Show when={description()}>
            <p class="text-[11.5px] leading-snug text-text-muted">{description()}</p>
          </Show>
        </div>
        <label class="flex items-center gap-2 cursor-pointer select-none shrink-0">
          <span class="text-[11px] text-text-muted">{enabled() ? 'on' : 'off'}</span>
          <button
            type="button"
            role="switch"
            aria-checked={enabled()}
            onClick={() => setEnabled(!enabled())}
            class={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
              enabled() ? 'bg-accent' : 'bg-surface-elevated hairline'
            }`}
          >
            <span
              class={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform duration-150 ${
                enabled() ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </button>
        </label>
      </div>
      <Show when={thresholdEntries().length > 0}>
        <div class="flex flex-col gap-1.5">
          <For each={thresholdEntries()}>
            {([k, v]) => (
              <div class="flex items-center gap-2 text-[12px]">
                <span class="w-32 shrink-0 text-text-muted">{k}</span>
                <input
                  type="text"
                  value={typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')}
                  onInput={(e) => {
                    const raw = e.currentTarget.value;
                    let parsed: unknown = raw;
                    try { parsed = JSON.parse(raw); } catch { parsed = raw; }
                    setThresholds((prev) => ({ ...prev, [k]: parsed }));
                  }}
                  class="h-6 flex-1 rounded border border-border bg-surface px-2 text-[12px] text-text focus:border-accent focus:outline-none"
                />
              </div>
            )}
          </For>
        </div>
      </Show>
      <div class="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving()}
          class="rounded-md bg-accent px-3 py-1 text-[11px] font-medium text-accent-fg transition-all duration-150 hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
        >
          {saving() ? 'Saving…' : 'Save'}
        </button>
        <Show when={isDirty() && !saving()}>
          <button
            type="button"
            onClick={handleReset}
            class="rounded-md hairline px-3 py-1 text-[11px] text-text-muted hover:bg-surface-elevated hover:text-text"
          >
            Reset
          </button>
        </Show>
        <Show when={msg()}>
          <span class="text-[11px] text-text-muted">{msg()}</span>
        </Show>
      </div>
    </div>
  );
}

function AutomationTab(): JSX.Element {
  const [stats, { refetch: refetchStats }] = createResource<AutoReviewerStats | null>(getAutoReviewerStats);
  const [dryRunResult, setDryRunResult] = createSignal<AutoReviewerDryRun | null>(null);
  const [dryRunPending, setDryRunPending] = createSignal(false);
  const [dryRunError, setDryRunError] = createSignal('');

  const unavailable = () => !stats.loading && stats() === null;

  async function handleDryRun() {
    setDryRunPending(true);
    setDryRunError('');
    setDryRunResult(null);
    try {
      const result = await runAutoReviewerDryRun();
      setDryRunResult(result);
    } catch (e) {
      setDryRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setDryRunPending(false);
    }
  }

  async function handleRuleSave(rule_id: string, enabled: boolean, threshold_summary: Record<string, unknown>) {
    await updateAutoReviewerConfig({ rule_id, enabled, threshold_summary });
    refetchStats();
  }

  return (
    <div class="flex flex-col gap-6">
      <div class="flex flex-col gap-1">
        <div class="text-sm font-medium text-text">Auto-reviewer</div>
        <p class="text-[12.5px] text-text-muted">
          Automatically triages the review queue using configured rules, reducing manual operator
          burden. Configure rules and thresholds below.
        </p>
      </div>

      <Show when={unavailable()}>
        <div class="rounded-md hairline bg-surface p-4 text-[12.5px] text-text-muted">
          Automation backend not yet active. Promote and implement spec 445 Phase 2 to enable.
        </div>
      </Show>

      <Show when={!unavailable()}>
        <Show when={stats()}>
          {(s) => (
            <>
              <div class="flex flex-col gap-2">
                <div class="text-xs font-medium text-text">Last run</div>
                <div class="flex flex-col gap-1 rounded-md hairline bg-surface p-3 text-[12px]">
                  <Show
                    when={s().last_run}
                    fallback={<span class="text-text-muted">No runs recorded yet.</span>}
                  >
                    {(lr) => (
                      <>
                        <div class="flex items-center justify-between">
                          <span class="text-text-muted">Started</span>
                          <span class="font-mono text-[11px]">{formatTs(lr().started_at)}</span>
                        </div>
                        <div class="flex items-center justify-between">
                          <span class="text-text-muted">Finished</span>
                          <span class="font-mono text-[11px]">{formatTs(lr().finished_at)}</span>
                        </div>
                        <div class="flex items-center justify-between">
                          <span class="text-text-muted">Applied</span>
                          <Chip variant="ok">{String(lr().applied_count)}</Chip>
                        </div>
                        <Show when={Object.keys(lr().by_rule ?? {}).length > 0}>
                          <div class="mt-1 flex flex-col gap-0.5 border-t border-border pt-1.5">
                            <For each={Object.entries(lr().by_rule)}>
                              {([rule, count]) => (
                                <div class="flex items-center justify-between">
                                  <span class="font-mono text-[11px] text-text-muted">{rule}</span>
                                  <span class="text-[11px] text-text">{String(count)}</span>
                                </div>
                              )}
                            </For>
                          </div>
                        </Show>
                      </>
                    )}
                  </Show>
                </div>
              </div>

              <Show when={s().rules.length > 0}>
                <div class="flex flex-col gap-2">
                  <div class="text-xs font-medium text-text">Rules</div>
                  <div class="flex flex-col gap-2">
                    <For each={s().rules}>
                      {(rule) => (
                        <AutomationRuleRow rule={rule} onSave={handleRuleSave} />
                      )}
                    </For>
                  </div>
                </div>
              </Show>
            </>
          )}
        </Show>

        <div class="flex flex-col gap-2">
          <div class="text-xs font-medium text-text">Dry run</div>
          <div class="flex flex-col gap-2 rounded-md hairline bg-surface p-3">
            <p class="text-[12px] text-text-muted">
              Preview what would be resolved without making any changes.
            </p>
            <div class="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDryRun}
                disabled={dryRunPending()}
                class="rounded-md bg-accent px-3.5 py-1.5 text-[11px] font-medium text-accent-fg transition-all duration-150 hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
              >
                {dryRunPending() ? 'Running…' : 'Run now (dry run)'}
              </button>
            </div>
            <Show when={dryRunError()}>
              <p class="text-[12px] text-danger">{dryRunError()}</p>
            </Show>
            <Show when={dryRunResult()}>
              {(result) => (
                <div class="flex flex-col gap-1 rounded-md bg-surface-elevated p-2.5 text-[12px]">
                  <div class="flex items-center justify-between">
                    <span class="text-text-muted">Would resolve</span>
                    <Chip variant="neutral">{String(result().proposed_count)}</Chip>
                  </div>
                  <Show when={Object.keys(result().by_rule ?? {}).length > 0}>
                    <div class="flex flex-col gap-0.5 border-t border-border pt-1.5 mt-0.5">
                      <For each={Object.entries(result().by_rule)}>
                        {([rule, count]) => (
                          <div class="flex items-center justify-between">
                            <span class="font-mono text-[11px] text-text-muted">{rule}</span>
                            <span class="text-[11px] text-text">{String(count)}</span>
                          </div>
                        )}
                      </For>
                    </div>
                  </Show>
                </div>
              )}
            </Show>
          </div>
        </div>
      </Show>
    </div>
  );
}

const TAB_ITEMS = [
  { value: 'readiness', label: 'Readiness' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'automation', label: 'Automation' },
  { value: 'about', label: 'About' },
];

export default function SettingsRoute(): JSX.Element {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = createSignal('readiness');
  const [overview, { refetch }] = createResource<SettingsPayload>(getSettings);
  const [meta] = createResource<UiMeta>(getUiMeta);

  onMount(() => {
    const qTab = searchParams.tab as string | undefined;
    if (qTab && TAB_ITEMS.some((t) => t.value === qTab)) {
      setTab(qTab);
    }
  });

  return (
    <Page title="Settings">
      <Show when={overview.loading}>
        <LoadingPage />
      </Show>
      <Show when={overview.error}>
        <ErrorState
          message={overview.error instanceof Error ? overview.error.message : String(overview.error)}
          onRetry={refetch}
        />
      </Show>
      <Show when={!overview.loading}>
        <KTabs value={tab()} onChange={setTab}>
          <Tabs items={TAB_ITEMS} value={tab()} onChange={setTab} />

          <KTabs.Content value="readiness" class="pt-6">
            <ReadinessSection overview={overview()} />
          </KTabs.Content>

          <KTabs.Content value="advanced" class="pt-6">
            <AdvancedTab overview={overview()} onRefetch={refetch} />
          </KTabs.Content>

          <KTabs.Content value="automation" class="pt-6">
            <AutomationTab />
          </KTabs.Content>

          <KTabs.Content value="about" class="pt-6">
            <Show when={!meta.loading} fallback={<p class="text-[12.5px] text-text-muted">Loading version info…</p>}>
              <AboutTab meta={meta()} />
            </Show>
          </KTabs.Content>
        </KTabs>
      </Show>
    </Page>
  );
}
