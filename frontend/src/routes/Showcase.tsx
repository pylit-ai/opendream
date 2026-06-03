import { A } from '@solidjs/router';
import {
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Link2,
  Target,
} from 'lucide-solid';
import { For, Show, createMemo, createResource, type JSX } from 'solid-js';
import { getOverview, getShowcase } from '~/api/client';
import type {
  OverviewPayload,
  ShowcaseAgentAnswer,
  ShowcaseAnswerSignal,
  ShowcasePromptLink,
  ShowcaseReport,
  ShowcaseRetrievalReason,
  ShowcaseSourceRef,
} from '~/api/types';
import { ErrorState } from '~/components/ErrorState';
import { IdLink } from '~/components/IdLink';
import { LoadingPage } from '~/components/Loading';
import { Page } from '~/components/Page';
import { Chip, type ChipVariant } from '~/components/Chip';
import { CopyButton } from '~/components/CopyButton';
import { cachedFetch } from '~/lib/cache';
import { formatNumber } from '~/lib/format';

type SummaryTone = 'success' | 'warn' | 'danger' | 'neutral';

interface SummaryCardProps {
  label: string;
  value: string;
  detail: string;
  tone: SummaryTone;
  icon: JSX.Element;
  children?: JSX.Element;
}

function statusVariant(status: string | undefined): 'success' | 'danger' | 'neutral' {
  if (status === 'passed' || status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

function selectedCount(report: ShowcaseReport | undefined): number {
  return report?.selected_memory_ids?.length ?? 0;
}

function sourceRefs(report: ShowcaseReport | undefined): ShowcaseSourceRef[] {
  return report?.proof?.source_refs ?? [];
}

function checks(report: ShowcaseReport | undefined): Array<[string, { passed?: boolean; detail?: string }]> {
  return Object.entries(report?.checks ?? {});
}

function promptLinks(report: ShowcaseReport | undefined): ShowcasePromptLink[] {
  return report?.context?.links ?? [];
}

function retrievalReasons(report: ShowcaseReport | undefined): ShowcaseRetrievalReason[] {
  return report?.retrieval_rationale ?? [];
}

function recordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    : [];
}

function scoreBars(report: ShowcaseReport | undefined): Array<{ key?: string; label?: string; score?: number; passed?: boolean }> {
  return report?.score_visualization?.bars ?? [];
}

function traceSpans(report: ShowcaseReport | undefined): Array<Record<string, unknown>> {
  return report?.agent_observability_trace?.spans ?? [];
}

function drilldownSelected(report: ShowcaseReport | undefined): Array<Record<string, unknown>> {
  return recordArray(report?.evidence_drilldown?.selected);
}

function drilldownExcluded(report: ShowcaseReport | undefined): Array<Record<string, unknown>> {
  return recordArray(report?.evidence_drilldown?.excluded);
}

function claimItems(report: ShowcaseReport | undefined): Array<Record<string, unknown>> {
  return recordArray(report?.claim_verification?.claims);
}

function safetyItems(report: ShowcaseReport | undefined): Array<Record<string, unknown>> {
  return recordArray(report?.memory_safety?.risk_categories);
}

function glossaryEntries(report: ShowcaseReport | undefined): Array<[string, string]> {
  return Object.entries(report?.glossary ?? {});
}

function agentAnswerEntries(
  report: ShowcaseReport | undefined,
): Array<{ key: 'stateless' | 'memory_assisted'; answer: ShowcaseAgentAnswer }> {
  const answers = report?.agent_answers;
  const entries: Array<{ key: 'stateless' | 'memory_assisted'; answer?: ShowcaseAgentAnswer }> = [
    { key: 'stateless', answer: answers?.stateless },
    { key: 'memory_assisted', answer: answers?.memory_assisted },
  ];
  return entries.filter(
    (entry): entry is { key: 'stateless' | 'memory_assisted'; answer: ShowcaseAgentAnswer } =>
      Boolean(entry.answer),
  );
}

function failedSignals(answer: ShowcaseAgentAnswer): ShowcaseAnswerSignal[] {
  return answer.measurement?.signals?.filter((signal) => !signal.passed) ?? [];
}

function answerScore(answer: ShowcaseAgentAnswer): string {
  const score = answer.measurement?.score;
  return typeof score === 'number' ? `${Math.round(score * 100)}%` : 'n/a';
}

function answerStatusVariant(answer: ShowcaseAgentAnswer): 'ok' | 'danger' | 'neutral' {
  if (answer.measurement?.passed === true) return 'ok';
  if (answer.measurement?.passed === false) return 'danger';
  return 'neutral';
}

function answerScoreDelta(report: ShowcaseReport | undefined): string {
  const delta = report?.agent_answers?.comparison?.score_delta;
  if (typeof delta !== 'number') return '';
  return `delta +${Math.round(delta * 100)} pts`;
}

function memoryAssistedAnswer(report: ShowcaseReport | undefined): ShowcaseAgentAnswer | undefined {
  return report?.agent_answers?.memory_assisted;
}

function checkSummary(report: ShowcaseReport | undefined): { passed: number; total: number } {
  const entries = checks(report);
  return {
    passed: entries.filter(([, check]) => check.passed === true).length,
    total: entries.length,
  };
}

function chipVariant(tone: SummaryTone): ChipVariant {
  if (tone === 'success') return 'ok';
  if (tone === 'warn') return 'warn';
  if (tone === 'danger') return 'danger';
  return 'neutral';
}

function toneTextClass(tone: SummaryTone): string {
  if (tone === 'success') return 'text-success';
  if (tone === 'warn') return 'text-warn';
  if (tone === 'danger') return 'text-danger';
  return 'text-text';
}

function verdictSummary(report: ShowcaseReport | undefined): {
  label: string;
  detail: string;
  tone: SummaryTone;
} {
  const comparison = report?.agent_answers?.comparison;
  const memoryPassed = comparison?.memory_assisted_passed ?? memoryAssistedAnswer(report)?.measurement?.passed;
  const statelessPassed = comparison?.stateless_passed;
  const status = report?.status;

  if (status === 'failed' || comparison?.passed === false || memoryPassed === false) {
    return {
      label: 'Needs evidence',
      detail: 'Memory-assisted answer still misses required signals or report checks.',
      tone: 'danger',
    };
  }

  if (comparison?.passed === true || memoryPassed === true) {
    return {
      label: 'Memory earns the answer',
      detail: statelessPassed
        ? 'Scored answer passes; trust comes from source-linked auditability.'
        : 'Memory-assisted answer passes where stateless context does not.',
      tone: 'success',
    };
  }

  if (status === 'passed' || status === 'completed') {
    return {
      label: 'Report complete',
      detail: 'Report generated, but scored answer comparison is unavailable.',
      tone: 'warn',
    };
  }

  return {
    label: 'No verdict yet',
    detail: 'Run the demo scenario to generate scored memory evidence.',
    tone: 'neutral',
  };
}

function coverageSummary(report: ShowcaseReport | undefined): {
  label: string;
  detail: string;
  tone: SummaryTone;
  selected: number;
  sourceRefs: number;
  promptLinks: number;
} {
  const measurement = memoryAssistedAnswer(report)?.measurement;
  const passed = measurement?.passed_count ?? 0;
  const total = measurement?.total_count ?? 0;
  const sourceRefCount = measurement?.source_ref_count ?? sourceRefs(report).length;
  const selected = measurement?.selected_memory_count ?? selectedCount(report);
  const promptLinkCount = promptLinks(report).length;
  const ratio = total > 0 ? passed / total : 0;
  const tone: SummaryTone =
    total === 0 ? 'neutral' : ratio === 1 && sourceRefCount > 0 ? 'success' : ratio >= 0.5 ? 'warn' : 'danger';

  return {
    label: total > 0 ? `${passed}/${total} signals` : `${sourceRefCount} source refs`,
    detail: `${selected} selected memories, ${sourceRefCount} source refs, ${promptLinkCount} prompt links`,
    tone,
    selected,
    sourceRefs: sourceRefCount,
    promptLinks: promptLinkCount,
  };
}

function trustSummary(report: ShowcaseReport | undefined): {
  label: string;
  detail: string;
  tone: SummaryTone;
  checksLabel: string;
} {
  const verdict = verdictSummary(report);
  const coverage = coverageSummary(report);
  const check = checkSummary(report);
  const checksLabel = check.total > 0 ? `${check.passed}/${check.total} checks` : 'no checks';
  const allChecksPassed = check.total > 0 && check.passed === check.total;
  const hasSources = coverage.sourceRefs > 0 && coverage.selected > 0;
  const claimTrust = report?.claim_verification?.trust_level;

  if (claimTrust === 'strong') {
    return {
      label: 'Strong trust',
      detail: `${checksLabel} plus source-linked retrieval, answer, dream, and safety claims.`,
      tone: 'success',
      checksLabel,
    };
  }

  if (verdict.tone === 'success' && allChecksPassed && hasSources) {
    return {
      label: 'High trust',
      detail: `${checksLabel} resolved with selected memories and source refs visible.`,
      tone: 'success',
      checksLabel,
    };
  }

  if (verdict.tone !== 'danger' && (hasSources || check.passed > 0)) {
    return {
      label: 'Medium trust',
      detail: `${checksLabel}; review coverage gaps before relying on this answer.`,
      tone: 'warn',
      checksLabel,
    };
  }

  return {
    label: 'Low trust',
    detail: `${checksLabel}; evidence chain is incomplete or failing.`,
    tone: verdict.tone === 'neutral' ? 'neutral' : 'danger',
    checksLabel,
  };
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
}

function asCompactText(value: unknown): string {
  const text = asText(value);
  if (text) return text;
  if (value && typeof value === 'object') return JSON.stringify(value);
  return '';
}

function displayCheckName(name: string): string {
  if (name === 'decoy_excluded') return 'decoy excluded from selected durable memory';
  return name.replaceAll('_', ' ');
}

function eventPreview(ref: ShowcaseSourceRef): string {
  const first = ref.source_events?.[0];
  if (!first) return '';
  const messageRef = typeof first.message_ref === 'string' ? first.message_ref : undefined;
  const content = typeof first.content === 'string' ? first.content : undefined;
  return [messageRef, content].filter(Boolean).join(' · ');
}

function SummaryCard(props: SummaryCardProps): JSX.Element {
  return (
    <div class="rounded-md border border-border bg-surface p-5">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div class="flex min-w-0 items-center gap-2 text-sm font-medium text-text">
          <span class={toneTextClass(props.tone)}>{props.icon}</span>
          <span>{props.label}</span>
        </div>
        <Chip variant={chipVariant(props.tone)}>{props.value}</Chip>
      </div>
      <p class={`text-xl font-semibold leading-7 ${toneTextClass(props.tone)}`}>{props.value}</p>
      <p class="mt-2 text-sm leading-6 text-text-muted">{props.detail}</p>
      <Show when={props.children}>
        <div class="mt-4 flex flex-wrap gap-2">{props.children}</div>
      </Show>
    </div>
  );
}

function numeric(value: unknown): number {
  return typeof value === 'number' ? value : Number(value ?? 0) || 0;
}

function LiveShowcaseFallback(props: { command?: string }): JSX.Element {
  const [overview, { refetch }] = createResource<OverviewPayload>(() =>
    cachedFetch('insights-live-overview', getOverview, 15_000),
  );
  const memoryTotal = (): number => numeric(overview()?.memory_counts?.total);
  const activeMemories = (): number => numeric(overview()?.memory_counts?.by_status?.active);
  const contestedMemories = (): number => numeric(overview()?.contested_memories);
  const retrievals = (): { total?: number; successful?: number; failed?: number } =>
    (overview()?.retrievals as { total?: number; successful?: number; failed?: number } | undefined) ?? {};
  const pruning = (): Record<string, unknown> =>
    (overview()?.context_pruning as Record<string, unknown> | undefined) ?? {};
  const semanticChange = (): Record<string, unknown> =>
    (overview()?.semantic_change_summary as Record<string, unknown> | undefined) ?? {};
  const latestContextId = (): string | undefined => {
    const id = semanticChange().latest_context_id;
    return typeof id === 'string' && id ? id : undefined;
  };

  return (
    <Show when={!overview.loading} fallback={<LoadingPage label="Loading live overview" />}>
      <Show
        when={!overview.error}
        fallback={
          <ErrorState
            title="Live insights unavailable"
            message={overview.error instanceof Error ? overview.error.message : String(overview.error)}
            onRetry={refetch}
          />
        }
      >
        <div class="flex flex-col gap-4">
          <section class="grid gap-4 xl:grid-cols-3">
            <SummaryCard
              label="Memory surface"
              value={formatNumber(memoryTotal())}
              detail={`${formatNumber(activeMemories())} active, ${formatNumber(contestedMemories())} contested`}
              tone={memoryTotal() > 0 ? 'success' : 'neutral'}
              icon={<BrainCircuit size={18} />}
            />
            <SummaryCard
              label="Retrieval evidence"
              value={formatNumber(numeric(retrievals().total))}
              detail={`${formatNumber(numeric(retrievals().successful))} successful, ${formatNumber(numeric(retrievals().failed))} failed`}
              tone={numeric(retrievals().failed) === 0 ? 'success' : 'warn'}
              icon={<FileSearch size={18} />}
            />
            <SummaryCard
              label="Context pruning"
              value={formatNumber(numeric(pruning().injected_count))}
              detail={`${formatNumber(numeric(pruning().suppressed_count))} suppressed, ${formatNumber(numeric(pruning().saved_token_estimate))} tokens saved`}
              tone={pruning().status === 'available' ? 'success' : 'neutral'}
              icon={<Target size={18} />}
            />
          </section>

          <section class="rounded-lg hairline bg-surface p-4">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div class="flex flex-col gap-1">
                <h2 class="text-sm font-semibold text-text">Live observability snapshot</h2>
                <p class="max-w-3xl text-[12.5px] leading-5 text-text-muted">
                  No scored demo report exists for this workspace, so this page is showing current
                  memory, retrieval, and context-pruning evidence.
                </p>
              </div>
              <div class="flex flex-wrap gap-2 text-[12px]">
                <A class="rounded-md border border-border px-3 py-1.5 text-text hover:bg-surface-elevated" href="/memories">
                  Memories
                </A>
                <A class="rounded-md border border-border px-3 py-1.5 text-text hover:bg-surface-elevated" href="/retrievals">
                  Retrievals
                </A>
                <A
                  class="rounded-md border border-border px-3 py-1.5 text-text hover:bg-surface-elevated"
                  href={latestContextId() ? `/context?id=${encodeURIComponent(latestContextId()!)}` : '/context'}
                >
                  Context
                </A>
              </div>
            </div>
            <Show when={props.command}>
              <div class="mt-4 rounded-md border border-border-subtle bg-surface-muted p-3">
                <div class="mb-1 text-[10px] uppercase tracking-[0.08em] text-text-subtle">
                  Demo report command
                </div>
                <code class="block break-words text-[12px] text-text">{props.command}</code>
              </div>
            </Show>
          </section>
        </div>
      </Show>
    </Show>
  );
}

export default function InsightsRoute(): JSX.Element {
  const [payload, { refetch }] = createResource(getShowcase);
  const report = createMemo(() => payload()?.report ?? undefined);

  return (
    <Page title="Insights" subtitle="Live memory health, retrieval evidence, and dream-cycle behavior">
      <Show when={!payload.loading} fallback={<LoadingPage label="Loading insights" />}>
        <Show
          when={!payload.error}
          fallback={
            <ErrorState
              title="Insights unavailable"
              message={payload.error instanceof Error ? payload.error.message : String(payload.error)}
              onRetry={refetch}
            />
          }
        >
          <Show
            when={payload()?.available && report()}
            fallback={<LiveShowcaseFallback command={payload()?.command} />}
          >
            {(r) => {
              const verdict = () => verdictSummary(r());
              const coverage = () => coverageSummary(r());
              const trust = () => trustSummary(r());

              return (
                <>
                  <section class="grid gap-4 xl:grid-cols-[1.2fr_0.9fr_0.9fr]">
                    <SummaryCard
                      label="Verdict"
                      value={verdict().label}
                      detail={verdict().detail}
                      tone={verdict().tone}
                      icon={verdict().tone === 'danger' ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}
                    >
                      <Chip variant={chipVariant(statusVariant(r().status))}>report {r().status ?? 'unknown'}</Chip>
                      <Show when={answerScoreDelta(r())}>
                        {(delta) => <Chip variant="accent">{delta()}</Chip>}
                      </Show>
                    </SummaryCard>

                    <SummaryCard
                      label="Coverage"
                      value={coverage().label}
                      detail={coverage().detail}
                      tone={coverage().tone}
                      icon={<FileSearch size={16} />}
                    >
                      <Chip variant="neutral">{coverage().selected} selected</Chip>
                      <Chip variant={coverage().sourceRefs > 0 ? 'ok' : 'warn'}>
                        {coverage().sourceRefs} source refs
                      </Chip>
                      <Chip variant="neutral">{coverage().promptLinks} prompt links</Chip>
                    </SummaryCard>

                    <SummaryCard
                      label="Trust level"
                      value={trust().label}
                      detail={trust().detail}
                      tone={trust().tone}
                      icon={<BrainCircuit size={16} />}
                    >
                      <Chip variant={chipVariant(trust().tone)}>{trust().checksLabel}</Chip>
                      <Chip variant={selectedCount(r()) > 0 ? 'ok' : 'warn'}>
                        {selectedCount(r())} durable memories
                      </Chip>
                    </SummaryCard>
                  </section>

                  <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
                    <div class="rounded-md border border-border bg-surface p-5">
                      <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                        <CheckCircle2 size={16} />
                        Claim verification
                      </div>
                      <p class="mb-4 text-sm leading-6 text-text-muted">
                        {r().claim_verification?.summary}
                      </p>
                      <div class="grid gap-2">
                        <For each={claimItems(r())}>
                          {(claim) => (
                            <div class="rounded-md border border-border bg-surface-muted p-3">
                              <div class="mb-2 flex flex-wrap items-center gap-2">
                                <Chip variant={Boolean(claim.passed) ? 'ok' : 'warn'}>
                                  {Boolean(claim.passed) ? 'proven' : 'gap'}
                                </Chip>
                                <span class="text-sm font-medium text-text">{asText(claim.label)}</span>
                              </div>
                              <div class="text-xs leading-5 text-text-muted">{asCompactText(claim.evidence)}</div>
                            </div>
                          )}
                        </For>
                      </div>
                    </div>

                    <div class="rounded-md border border-border bg-surface p-5">
                      <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                        <CircleAlert size={16} />
                        Memory safety
                      </div>
                      <div class="mb-4 flex flex-wrap gap-2">
                        <Chip variant={r().memory_safety?.passed ? 'ok' : 'danger'}>
                          {r().memory_safety?.risk_level ?? 'unknown'} risk
                        </Chip>
                        <Chip variant="neutral">{safetyItems(r()).length} probes</Chip>
                      </div>
                      <div class="grid gap-2">
                        <For each={safetyItems(r())}>
                          {(item) => (
                            <div class="rounded-md border border-border bg-surface-muted p-3">
                              <div class="mb-1 flex flex-wrap items-center gap-2">
                                <Chip variant={Boolean(item.passed) ? 'ok' : 'warn'}>
                                  {Boolean(item.passed) ? 'passed' : 'gap'}
                                </Chip>
                                <span class="text-sm font-medium text-text">{asText(item.label)}</span>
                              </div>
                              <div class="text-xs leading-5 text-text-subtle">{asText(item.key)}</div>
                            </div>
                          )}
                        </For>
                      </div>
                    </div>
                  </section>

                  <section class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <Link2 size={16} />
                      Reproducibility
                    </div>
                    <div class="grid gap-3 lg:grid-cols-[1.2fr_1fr]">
                      <div class="min-w-0 rounded-md bg-surface-muted p-3">
                        <div class="mb-1 flex items-center justify-between gap-2 text-xs uppercase text-text-subtle">
                          <span>Command</span>
                          <CopyButton value={r().copy_actions?.command ?? ''} label="Copy command" />
                        </div>
                        <code class="block break-words text-sm text-text">{r().copy_actions?.command}</code>
                      </div>
                      <div class="grid min-w-0 gap-3">
                        <div class="rounded-md bg-surface-muted p-3">
                          <div class="mb-1 flex items-center justify-between gap-2 text-xs uppercase text-text-subtle">
                            <span>Report path</span>
                            <CopyButton value={r().copy_actions?.report_path ?? ''} label="Copy report path" />
                          </div>
                          <code class="block break-words text-sm text-text">
                            {r().copy_actions?.report_path}
                          </code>
                        </div>
                        <div class="rounded-md bg-surface-muted p-3">
                          <div class="mb-1 flex items-center justify-between gap-2 text-xs uppercase text-text-subtle">
                            <span>Fixture path</span>
                            <CopyButton value={r().copy_actions?.fixture_path ?? ''} label="Copy fixture path" />
                          </div>
                          <code class="block break-words text-sm text-text">
                            {r().copy_actions?.fixture_path}
                          </code>
                        </div>
                      </div>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-2">
                      <a
                        href={r().copy_actions?.report_json_url ?? '/api/showcase'}
                        class="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-text-muted hover:text-text"
                      >
                        <Link2 size={12} />
                        Open report JSON
                      </a>
                      <Chip variant="neutral">git {asText(r().reproducibility?.git_commit) || 'unknown'}</Chip>
                      <Chip variant={r().reproducibility?.git_dirty ? 'warn' : 'ok'}>
                        {r().reproducibility?.git_dirty ? 'dirty tree' : 'clean tree'}
                      </Chip>
                    </div>
                  </section>

                  <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                    <Target size={16} />
                    Objective
                  </div>
                  <div class="grid gap-4 xl:grid-cols-[1fr_1fr]">
                    <div class="grid gap-3">
                      <div>
                        <div class="text-[11px] uppercase text-text-subtle">What this proves</div>
                        <p class="mt-1 text-sm leading-6 text-text">{r().objective?.description}</p>
                      </div>
                      <div>
                        <div class="text-[11px] uppercase text-text-subtle">Task prompt</div>
                        <pre class="mt-1 whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-sm leading-6 text-text">
                          {r().evaluation_case?.user_prompt}
                        </pre>
                      </div>
                      <div>
                        <div class="text-[11px] uppercase text-text-subtle">Expected answer shape</div>
                        <p class="mt-1 text-sm leading-6 text-text-muted">
                          {r().evaluation_case?.expected_response}
                        </p>
                      </div>
                    </div>
                    <div class="grid gap-3">
                      <div>
                        <div class="text-[11px] uppercase text-text-subtle">Why memory is required</div>
                        <p class="mt-1 text-sm leading-6 text-text-muted">
                          {r().evaluation_case?.why_this_tests_memory}
                        </p>
                      </div>
                      <div>
                        <div class="text-[11px] uppercase text-text-subtle">Likely stateless failure</div>
                        <p class="mt-1 text-sm leading-6 text-text-muted">
                          {r().evaluation_case?.failure_without_memory}
                        </p>
                      </div>
                      <ul class="grid gap-2 text-sm text-text-muted">
                        <For each={r().objective?.success_criteria ?? []}>
                          {(criterion) => (
                            <li class="flex gap-2">
                              <CheckCircle2 size={15} class="mt-1 shrink-0 text-success" />
                              <span>{criterion}</span>
                            </li>
                          )}
                        </For>
                      </ul>
                    </div>
                  </div>
                </section>

                <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-3 flex items-center gap-2 text-sm font-medium text-text">
                    <Sparkles size={16} />
                    Agent-facing memory snippet
                  </div>
                  <pre class="whitespace-pre-wrap rounded-md bg-surface-muted p-4 text-sm leading-6 text-text">
                    {r().agent_snippet}
                  </pre>
                </section>

                <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-2 text-sm font-medium text-text">
                      <Sparkles size={16} />
                      Measured agent answers
                    </div>
                    <Show when={answerScoreDelta(r())}>
                      {(delta) => <Chip variant="accent">{delta()}</Chip>}
                    </Show>
                  </div>
                  <div class="grid gap-4 xl:grid-cols-[1fr_1fr]">
                    <For each={agentAnswerEntries(r())}>
                      {(entry) => (
                        <div class="rounded-md border border-border bg-surface-muted p-4">
                          <div class="mb-3 flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div class="text-sm font-medium text-text">
                                {entry.answer.label ?? entry.key.replaceAll('_', ' ')}
                              </div>
                              <div class="mt-1 text-xs leading-5 text-text-muted">{entry.answer.input}</div>
                            </div>
                            <div class="flex flex-wrap gap-2">
                              <Chip variant={answerStatusVariant(entry.answer)}>
                                {entry.answer.measurement?.passed ? 'passed' : 'gap'}
                              </Chip>
                              <Chip variant="neutral">{answerScore(entry.answer)}</Chip>
                              <Chip variant="neutral">
                                {entry.answer.measurement?.passed_count ?? 0}/
                                {entry.answer.measurement?.total_count ?? 0} signals
                              </Chip>
                            </div>
                          </div>
                          <pre class="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-surface p-3 text-sm leading-6 text-text">
                            {entry.answer.answer}
                          </pre>
                          <Show when={failedSignals(entry.answer).length}>
                            <div class="mt-3 grid gap-2">
                              <For each={failedSignals(entry.answer)}>
                                {(signal) => (
                                  <div class="rounded-md border border-border bg-surface p-3 text-xs leading-5 text-text-muted">
                                    <div class="mb-1 font-medium text-text">{signal.label ?? signal.key}</div>
                                    <Show when={signal.missing_terms?.length}>
                                      <div>Missing: {signal.missing_terms?.join(', ')}</div>
                                    </Show>
                                    <Show when={signal.forbidden_matches?.length}>
                                      <div>Matched forbidden: {signal.forbidden_matches?.join(', ')}</div>
                                    </Show>
                                    <Show when={signal.requires_source_refs}>
                                      <div>Missing selected source refs.</div>
                                    </Show>
                                  </div>
                                )}
                              </For>
                            </div>
                          </Show>
                        </div>
                      )}
                    </For>
                  </div>
                </section>

                <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <FileSearch size={16} />
                      Prompt context inspection
                    </div>
                    <div class="mb-4 grid gap-2">
                      <div class="text-xs text-text-subtle">Context ID</div>
                      <div class="font-mono text-sm text-text">{r().context?.context_id}</div>
                    </div>
                    <div class="mb-4 flex flex-col divide-y divide-border rounded-md border border-border">
                      <For each={promptLinks(r())}>
                        {(link) => (
                          <div class="grid gap-2 py-4 first:pt-0 last:pb-0">
                            <div class="flex flex-wrap items-center gap-2 px-3">
                              <Show when={link.memory_id}>
                                {(id) => (
                                  <A href={`/memories?id=${encodeURIComponent(id())}`} class="inline-flex">
                                    <IdLink id={id()} preview={link.summary} />
                                  </A>
                                )}
                              </Show>
                              <Chip variant="neutral">score {link.score?.toFixed?.(3) ?? 'n/a'}</Chip>
                            </div>
                            <div class="px-3 text-sm font-medium text-text">{link.title}</div>
                            <div class="px-3 text-sm leading-6 text-text-muted">{link.why_included}</div>
                            <Show when={link.source_event_ids?.length}>
                              <div class="px-3 text-xs text-text-subtle">
                                Source events: {link.source_event_ids?.join(', ')}
                              </div>
                            </Show>
                          </div>
                        )}
                      </For>
                    </div>
                    <pre class="max-h-[460px] overflow-auto whitespace-pre-wrap rounded-md bg-surface-muted p-4 text-xs leading-5 text-text">
                      {r().context?.prompt_context}
                    </pre>
                  </div>

                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <BrainCircuit size={16} />
                      Retrieval rationale
                    </div>
                    <div class="flex flex-col gap-3">
                      <For each={retrievalReasons(r())}>
                        {(reason) => (
                          <div class="rounded-md border border-border bg-surface-muted p-3">
                            <div class="mb-2 flex flex-wrap items-center gap-2">
                              <Show when={reason.memory_id}>
                                {(id) => (
                                  <A href={`/memories?id=${encodeURIComponent(id())}`} class="inline-flex">
                                    <IdLink id={id()} />
                                  </A>
                                )}
                              </Show>
                              <Chip variant={reason.status === 'active' ? 'ok' : 'neutral'}>
                                {reason.status ?? 'unknown'}
                              </Chip>
                              <Chip variant="neutral">score {reason.score?.toFixed?.(3) ?? 'n/a'}</Chip>
                            </div>
                            <p class="text-sm leading-6 text-text">{reason.why_included}</p>
                            <Show when={reason.matched_evidence}>
                              <div class="mt-2 text-xs leading-5 text-text-subtle">
                                Matched evidence: {JSON.stringify(reason.matched_evidence)}
                              </div>
                            </Show>
                          </div>
                        )}
                      </For>
                    </div>
                  </div>
                </section>

                <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <FileSearch size={16} />
                      Evidence drilldown
                    </div>
                    <div class="grid gap-4 md:grid-cols-2">
                      <div>
                        <div class="mb-2 text-xs font-medium uppercase text-text-subtle">Selected</div>
                        <div class="grid gap-2">
                          <For each={drilldownSelected(r()).slice(0, 6)}>
                            {(item) => (
                              <div class="rounded-md border border-border bg-surface-muted p-3">
                                <Show when={asText(item.memory_id)}>
                                  {(id) => (
                                    <A href={`/memories?id=${encodeURIComponent(id())}`} class="inline-flex">
                                      <IdLink id={id()} preview={asText(item.summary)} />
                                    </A>
                                  )}
                                </Show>
                                <div class="mt-2 text-sm font-medium text-text">{asText(item.title)}</div>
                                <div class="mt-1 text-xs leading-5 text-text-subtle">
                                  sources {recordArray(item.source_events).length}
                                </div>
                              </div>
                            )}
                          </For>
                        </div>
                      </div>
                      <div>
                        <div class="mb-2 text-xs font-medium uppercase text-text-subtle">Excluded</div>
                        <div class="grid gap-2">
                          <For each={drilldownExcluded(r()).slice(0, 6)}>
                            {(item) => (
                              <div class="rounded-md border border-border bg-surface-muted p-3">
                                <div class="flex flex-wrap gap-2">
                                  <Show when={asText(item.memory_id)}>
                                    {(id) => <IdLink id={id()} />}
                                  </Show>
                                  <Chip variant="neutral">{asText(item.reason_code) || asText(item.status) || 'excluded'}</Chip>
                                </div>
                                <div class="mt-2 text-sm font-medium text-text">{asText(item.title)}</div>
                                <div class="mt-1 text-xs leading-5 text-text-subtle">{asText(item.why_excluded)}</div>
                              </div>
                            )}
                          </For>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <BrainCircuit size={16} />
                      Score and trace
                    </div>
                    <div class="grid gap-2">
                      <For each={scoreBars(r())}>
                        {(bar) => (
                          <div>
                            <div class="mb-1 flex justify-between gap-3 text-xs text-text-subtle">
                              <span>{bar.label ?? bar.key}</span>
                              <span>{Math.round((bar.score ?? 0) * 100)}%</span>
                            </div>
                            <div class="h-2 overflow-hidden rounded-full bg-surface-muted">
                              <div
                                class={`h-full ${bar.passed ? 'bg-success' : 'bg-danger'}`}
                                style={{ width: `${Math.round((bar.score ?? 0) * 100)}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </For>
                    </div>
                    <div class="mt-5 border-t border-border pt-4">
                      <div class="mb-2 flex flex-wrap gap-2">
                        <Chip variant={r().stability_check?.passed ? 'ok' : 'warn'}>stability</Chip>
                        <Chip variant={r().agent_observability_trace?.spans?.length ? 'ok' : 'warn'}>
                          {traceSpans(r()).length} trace spans
                        </Chip>
                      </div>
                      <div class="grid gap-2">
                        <For each={traceSpans(r()).slice(0, 6)}>
                          {(span) => (
                            <div class="rounded-md bg-surface-muted p-2 text-xs leading-5 text-text-muted">
                              {asText(span.operation)} · {asText(span.name)}
                            </div>
                          )}
                        </For>
                      </div>
                    </div>
                  </div>
                </section>

                <section class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <BrainCircuit size={16} />
                      Dream effectiveness
                    </div>
                    <p class="mb-4 text-sm leading-6 text-text-muted">{r().dream_effectiveness?.summary}</p>
                    <div class="grid gap-3">
                      <For each={r().dream_effectiveness?.pipeline ?? []}>
                        {(stage) => (
                          <div class="rounded-md border border-border bg-surface-muted p-3">
                            <div class="text-sm font-medium text-text">{asText(stage.stage)}</div>
                            <div class="mt-1 text-xs leading-5 text-text-muted">{asText(stage.evidence)}</div>
                            <div class="mt-2 text-xs text-text-subtle">
                              input {asText(stage.input)} → output {asText(stage.output)}
                            </div>
                          </div>
                        )}
                      </For>
                    </div>
                  </div>

                  <div class="rounded-md border border-border bg-surface p-5">
                    <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                      <CheckCircle2 size={16} />
                      Checks
                    </div>
                    <div class="mb-4 grid gap-2 sm:grid-cols-2">
                      <For each={Object.entries(r().dream_effectiveness?.effective ?? {})}>
                        {([name, passed]) => {
                          const CheckIcon = passed ? CheckCircle2 : CircleAlert;
                          return (
                            <div class="flex gap-3 rounded-md border border-border bg-surface-muted p-3">
                              <CheckIcon
                                size={16}
                                class={passed ? 'mt-0.5 text-success' : 'mt-0.5 text-warn'}
                              />
                              <div class="min-w-0">
                                <div class="flex flex-wrap items-center gap-2 text-sm font-medium text-text">
                                  <span>{displayCheckName(name)}</span>
                                  <Chip variant={passed ? 'ok' : 'warn'}>{passed ? 'resolved' : 'gap'}</Chip>
                                </div>
                              </div>
                            </div>
                          );
                        }}
                      </For>
                    </div>
                    <div class="flex flex-col gap-3">
                      <For each={checks(r())}>
                        {([name, check]) => {
                          const passed = () => check.passed === true;
                          const CheckIcon = passed() ? CheckCircle2 : CircleAlert;
                          return (
                            <div class="flex gap-3 rounded-md border border-border bg-surface-muted p-3">
                              <CheckIcon size={16} class={passed() ? 'mt-0.5 text-success' : 'mt-0.5 text-warn'} />
                              <div class="min-w-0">
                                <div class="flex flex-wrap items-center gap-2 text-sm font-medium text-text">
                                  <span>{displayCheckName(name)}</span>
                                  <Chip variant={passed() ? 'ok' : 'warn'}>{passed() ? 'resolved' : 'gap'}</Chip>
                                </div>
                                <div class="text-xs leading-5 text-text-muted">{check.detail}</div>
                              </div>
                            </div>
                          );
                        }}
                      </For>
                    </div>
                  </div>
                </section>

                <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                    <Link2 size={16} />
                    Source evidence
                  </div>
                  <div class="flex flex-col divide-y divide-border">
                    <For each={sourceRefs(r())}>
                      {(ref) => (
                        <div class="grid gap-2 py-4 first:pt-0 last:pb-0">
                          <div class="flex flex-wrap items-center gap-2">
                            <Show when={ref.memory_id}>
                              {(id) => (
                                <A href={`/memories?id=${encodeURIComponent(id())}`} class="inline-flex">
                                  <IdLink id={id()} preview={ref.summary} />
                                </A>
                              )}
                            </Show>
                            <Chip variant="neutral">{ref.type ?? 'memory'}</Chip>
                            <Chip variant={ref.status === 'active' ? 'ok' : 'neutral'}>
                              {ref.status ?? 'unknown'}
                            </Chip>
                          </div>
                          <div class="text-sm font-medium text-text">{ref.title ?? 'Untitled memory'}</div>
                          <div class="text-sm leading-6 text-text-muted">{ref.summary}</div>
                          <Show when={eventPreview(ref)}>
                            {(preview) => <div class="text-xs leading-5 text-text-subtle">{preview()}</div>}
                          </Show>
                        </div>
                      )}
                    </For>
                  </div>
                </section>

                <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-4 flex items-center gap-2 text-sm font-medium text-text">
                    <BrainCircuit size={16} />
                    Glossary
                  </div>
                  <dl class="grid gap-3 md:grid-cols-2">
                    <For each={glossaryEntries(r())}>
                      {([term, definition]) => (
                        <div class="rounded-md bg-surface-muted p-3">
                          <dt class="text-sm font-medium text-text">{term}</dt>
                          <dd class="mt-1 text-xs leading-5 text-text-muted">{definition}</dd>
                        </div>
                      )}
                    </For>
                  </dl>
                </section>

                <section class="rounded-md border border-border bg-surface p-5">
                  <div class="mb-3 flex items-center gap-2 text-sm font-medium text-text">
                    <CircleAlert size={16} />
                    Report
                  </div>
                  <dl class="grid gap-3 text-sm md:grid-cols-2">
                    <div>
                      <dt class="text-text-subtle">Scenario</dt>
                      <dd class="mt-1 font-mono text-text">{r().scenario}</dd>
                    </div>
                    <div>
                      <dt class="text-text-subtle">Generated</dt>
                      <dd class="mt-1 font-mono text-text">{r().generated_at ?? 'unknown'}</dd>
                    </div>
                    <div class="md:col-span-2">
                      <dt class="text-text-subtle">Report path</dt>
                      <dd class="mt-1 break-all font-mono text-text">
                        {r().report_path ?? payload()?.report_path}
                      </dd>
                    </div>
                  </dl>
                </section>
                </>
              );
            }}
          </Show>
        </Show>
      </Show>
    </Page>
  );
}
