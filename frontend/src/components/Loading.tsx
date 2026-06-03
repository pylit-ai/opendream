import {
  createMemo,
  createSignal,
  For,
  onCleanup,
  onMount,
  Show,
  type JSX,
} from 'solid-js';
import { Clock3, Loader2 } from 'lucide-solid';
import { getStatus } from '~/api/client';
import type { StatusSnapshot } from '~/api/types';
import { cn } from '~/lib/cn';
import { useTheme } from '~/app/ThemeProvider';
import logoMark from '../../assets/logo/mark/vector/opendream_mark_gradient.svg?url';
import rollingWavesDark from '../../assets/animation/svg/opendream_loop_dark_rolling_waves.svg?url';
import rollingWavesLight from '../../assets/animation/svg/opendream_loop_light_rolling_waves.svg?url';

interface LoadingStep {
  label: string;
  detail?: string;
  delayMs: number;
}

interface StatusLine {
  label: string;
  value: string;
  tone?: 'default' | 'warn' | 'ok';
}

const DEFAULT_STEPS: LoadingStep[] = [
  {
    label: 'Request sent',
    detail: 'Waiting for the backend response.',
    delayMs: 0,
  },
  {
    label: 'Workspace status check',
    detail: 'Reading lightweight workspace status while data loads.',
    delayMs: 1_500,
  },
  {
    label: 'Large workspace path',
    detail: 'Index or detail query still running.',
    delayMs: 8_000,
  },
  {
    label: 'Long backend request',
    detail: 'Keeping the view open and polling backend status.',
    delayMs: 30_000,
  },
];

export function Loading(props: { size?: number; class?: string }): JSX.Element {
  return (
    <Loader2
      size={props.size ?? 14}
      class={cn('animate-spin text-text-subtle', props.class)}
    />
  );
}

function LoadingBrand(): JSX.Element {
  const { resolved } = useTheme();
  const [reduceMotion, setReduceMotion] = createSignal(false);
  const motionSrc = () => (resolved() === 'dark' ? rollingWavesDark : rollingWavesLight);

  onMount(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduceMotion(mql.matches);
    sync();
    mql.addEventListener('change', sync);
    onCleanup(() => mql.removeEventListener('change', sync));
  });

  return (
    <div class="flex h-20 w-36 items-center justify-center overflow-hidden rounded-md border border-border-subtle bg-surface-elevated">
      <Show when={!reduceMotion()} fallback={<img src={logoMark} alt="" aria-hidden="true" class="h-10 w-10" />}>
        <img src={motionSrc()} alt="" aria-hidden="true" class="h-full w-full object-cover" />
      </Show>
    </div>
  );
}

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`;
}

function workspaceName(workspace?: string): string | null {
  if (!workspace) return null;
  const parts = workspace.split(/[\\/]/).filter(Boolean);
  return parts.at(-1) ?? workspace;
}

function formatCount(n: number | undefined): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '0';
  return new Intl.NumberFormat().format(n);
}

function statusLines(snapshot: StatusSnapshot | null): StatusLine[] {
  if (!snapshot) return [];
  const lines: StatusLine[] = [];
  const workspace = workspaceName(snapshot.workspace);
  if (workspace) lines.push({ label: 'Workspace', value: workspace });
  lines.push({
    label: 'Store',
    value: snapshot.initialized === false ? 'not initialized' : snapshot.state ?? 'unknown',
    tone: snapshot.state === 'pending' ? 'warn' : snapshot.state === 'idle' ? 'ok' : 'default',
  });
  lines.push({
    label: 'Pending work',
    value: `${formatCount(snapshot.pending_events)} events, ${formatCount(snapshot.pending_candidates)} candidates`,
    tone:
      (snapshot.pending_events ?? 0) + (snapshot.pending_candidates ?? 0) > 0
        ? 'warn'
        : 'ok',
  });

  const dream = snapshot.dream;
  if (dream) {
    const queue = typeof dream.queue_depth === 'number' ? dream.queue_depth : 0;
    const worker = dream.worker?.active_phase ?? dream.worker?.state;
    const health = dream.worker_health?.active_phase ?? dream.worker_health?.health;
    lines.push({
      label: 'Dream worker',
      value: [worker, health, queue > 0 ? `${queue} queued` : null]
        .filter(Boolean)
        .join(' / ') || dream.state || 'idle',
      tone: queue > 0 ? 'warn' : 'default',
    });
  }

  const dueJobs = snapshot.automation?.due_job_ids?.length ?? 0;
  if (dueJobs > 0) {
    lines.push({ label: 'Automation', value: `${formatCount(dueJobs)} due`, tone: 'warn' });
  }
  return lines.slice(0, 5);
}

function activeStep(steps: LoadingStep[], elapsedMs: number): LoadingStep {
  return [...steps].reverse().find((step) => elapsedMs >= step.delayMs) ?? steps[0];
}

export function ProgressiveLoading(props: {
  label?: string;
  detail?: string;
  compact?: boolean;
  class?: string;
  steps?: LoadingStep[];
}): JSX.Element {
  const [elapsedMs, setElapsedMs] = createSignal(0);
  const [snapshot, setSnapshot] = createSignal<StatusSnapshot | null>(null);
  const [statusError, setStatusError] = createSignal<string | null>(null);
  const steps = createMemo(() => props.steps ?? DEFAULT_STEPS);
  const current = createMemo(() => activeStep(steps(), elapsedMs()));
  const lines = createMemo(() => statusLines(snapshot()));

  onMount(() => {
    const startedAt = Date.now();
    let cancelled = false;
    let statusTimer: ReturnType<typeof setInterval> | undefined;

    const tick = (): void => setElapsedMs(Date.now() - startedAt);
    const fetchStatus = async (): Promise<void> => {
      try {
        const next = await getStatus();
        if (!cancelled) {
          setSnapshot(next);
          setStatusError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setStatusError(err instanceof Error ? err.message : 'Backend status unavailable');
        }
      }
    };

    tick();
    const elapsedTimer = setInterval(tick, 1000);
    const statusDelay = setTimeout(() => {
      void fetchStatus();
      statusTimer = setInterval(() => {
        void fetchStatus();
      }, 5_000);
    }, 1_200);

    onCleanup(() => {
      cancelled = true;
      clearInterval(elapsedTimer);
      clearTimeout(statusDelay);
      if (statusTimer) clearInterval(statusTimer);
    });
  });

  return (
    <section
      role="status"
      aria-busy="true"
      aria-label={props.label ?? 'Loading'}
      class={cn(
        props.compact
          ? 'rounded-md border border-border-subtle bg-surface-elevated p-3 text-text-subtle'
          : 'mx-auto flex min-h-[40vh] w-full max-w-xl flex-col items-center justify-center gap-4 px-4 py-8 text-text-subtle',
        props.class,
      )}
    >
      <Show when={!props.compact}>
        <LoadingBrand />
      </Show>

      <div class="flex w-full flex-col gap-3">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="text-[11px] font-medium uppercase text-text">
              {props.label ?? 'Loading'}
            </div>
            <p class="mt-0.5 text-[12px] leading-5 text-text-muted">
              {props.detail ?? current().detail ?? current().label}
            </p>
          </div>
          <div
            class="flex shrink-0 items-center gap-1 rounded-full border border-border-subtle px-2 py-1 font-mono text-[11px] text-text-muted"
            aria-hidden="true"
          >
            <Clock3 size={12} />
            {formatElapsed(elapsedMs())}
          </div>
        </div>

        <div
          role="progressbar"
          aria-valuetext={current().label}
          class="h-1.5 overflow-hidden rounded-full bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_14%,transparent)]"
        >
          <div class="loading-progress-sweep h-full w-1/2 rounded-full bg-accent" />
        </div>

        <ol class="grid gap-1.5">
          <For each={steps()}>
            {(step) => {
              const reached = () => elapsedMs() >= step.delayMs;
              return (
                <li
                  class={cn(
                    'grid grid-cols-[10px_1fr] items-start gap-2 text-[12px]',
                    reached() ? 'text-text' : 'text-text-subtle',
                  )}
                >
                  <span
                    class={cn(
                      'mt-[7px] h-1.5 w-1.5 rounded-full',
                      reached() ? 'bg-accent' : 'bg-border',
                    )}
                  />
                  <span>
                    {step.label}
                    <Show when={reached() && step.detail}>
                      <span class="block text-[11.5px] leading-4 text-text-muted">
                        {step.detail}
                      </span>
                    </Show>
                  </span>
                </li>
              );
            }}
          </For>
        </ol>

        <Show when={lines().length > 0}>
          <div class="grid gap-1 rounded-md border border-border-subtle bg-surface px-3 py-2">
            <For each={lines()}>
              {(line) => (
                <div class="grid grid-cols-[96px_1fr] gap-2 text-[11.5px]">
                  <span class="text-text-subtle">{line.label}</span>
                  <span
                    class={cn(
                      'min-w-0 truncate font-mono',
                      line.tone === 'ok'
                        ? 'text-success'
                        : line.tone === 'warn'
                          ? 'text-warn'
                          : 'text-text-muted',
                    )}
                    title={line.value}
                  >
                    {line.value}
                  </span>
                </div>
              )}
            </For>
          </div>
        </Show>

        <Show when={!snapshot() && elapsedMs() > 3_000 && statusError()}>
          <p class="text-[11.5px] leading-4 text-text-muted">
            Backend status unavailable; main request still active.
          </p>
        </Show>
      </div>
    </section>
  );
}

export function LoadingPage(props: {
  label?: string;
  detail?: string;
  compact?: boolean;
  class?: string;
  steps?: LoadingStep[];
}): JSX.Element {
  return (
    <ProgressiveLoading
      label={props.label}
      detail={props.detail}
      compact={props.compact}
      class={props.class}
      steps={props.steps}
    />
  );
}
