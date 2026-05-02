import { A } from '@solidjs/router';
import {
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Link2,
  Sparkles,
  Target,
} from 'lucide-solid';
import { For, Show, createMemo, createResource, type JSX } from 'solid-js';
import { getShowcase } from '~/api/client';
import type {
  ShowcaseAgentAnswer,
  ShowcaseAnswerSignal,
  ShowcasePromptLink,
  ShowcaseReport,
  ShowcaseRetrievalReason,
  ShowcaseSourceRef,
} from '~/api/types';
import { EmptyState } from '~/components/EmptyState';
import { ErrorState } from '~/components/ErrorState';
import { IdLink } from '~/components/IdLink';
import { LoadingPage } from '~/components/Loading';
import { Page } from '~/components/Page';
import { Chip } from '~/components/Chip';

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

function asText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
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

function Stat(props: { label: string; value: string | number; tone?: 'success' | 'danger' | 'neutral' }): JSX.Element {
  const tone = () =>
    props.tone === 'success'
      ? 'text-success'
      : props.tone === 'danger'
        ? 'text-danger'
        : 'text-text';
  return (
    <div class="rounded-md border border-border bg-surface px-4 py-3">
      <div class="text-[11px] uppercase text-text-subtle">{props.label}</div>
      <div class={`mt-1 text-lg font-semibold ${tone()}`}>{props.value}</div>
    </div>
  );
}

export default function ShowcaseRoute(): JSX.Element {
  const [payload, { refetch }] = createResource(getShowcase);
  const report = createMemo(() => payload()?.report ?? undefined);

  return (
    <Page title="Showcase" subtitle="Task-grounded memory recall and dream evidence">
      <Show when={!payload.loading} fallback={<LoadingPage label="Loading showcase" />}>
        <Show
          when={!payload.error}
          fallback={
            <ErrorState
              title="Showcase unavailable"
              message={payload.error instanceof Error ? payload.error.message : String(payload.error)}
              onRetry={refetch}
            />
          }
        >
          <Show
            when={payload()?.available && report()}
            fallback={
              <EmptyState
                icon={Sparkles}
                title="No showcase report"
                description={
                  payload()?.command ??
                  'opendream demo --scenario coding-agent-showcase --workspace .tmp/opendream-showcase'
                }
              />
            }
          >
            {(r) => (
              <>
                <div class="grid gap-3 md:grid-cols-4">
                  <Stat label="Status" value={r().status ?? 'unknown'} tone={statusVariant(r().status)} />
                  <Stat label="Selected" value={selectedCount(r())} />
                  <Stat label="Before" value={r().before?.selected_memory_ids?.length ?? 0} />
                  <Stat label="After" value={r().after?.selected_memory_ids?.length ?? 0} />
                </div>

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
                                      {(terms) => <div>Missing: {terms().join(', ')}</div>}
                                    </Show>
                                    <Show when={signal.forbidden_matches?.length}>
                                      {(terms) => <div>Matched forbidden: {terms().join(', ')}</div>}
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
                    <div class="mb-4 grid grid-cols-2 gap-2">
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
            )}
          </Show>
        </Show>
      </Show>
    </Page>
  );
}
