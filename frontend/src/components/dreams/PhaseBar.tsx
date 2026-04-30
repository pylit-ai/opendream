import { For, type JSX } from 'solid-js';
import { formatDuration } from '~/lib/format';

// Stable phase -> color map. Same phase keeps the same color across cycles
// so the operator can scan the chart vertically. Unknown phases fall back
// to the OVERFLOW palette by hash bucket.
export const PHASE_COLORS: Record<string, string> = {
  orient: '#14b8a6',
  gather_recent_signal: '#6366f1',
  infer_families: '#8b5cf6',
  synthesize: '#f59e0b',
  verify: '#22c55e',
  promote: '#06b6d4',
  prune_and_reindex: '#a855f7',
  consolidate: '#ef4444',
};

const OVERFLOW = ['#64748b', '#0ea5e9', '#84cc16', '#f97316', '#ec4899'];

export function colorForPhase(phase: string): string {
  if (phase in PHASE_COLORS) return PHASE_COLORS[phase]!;
  // deterministic fallback: hash-bucket into overflow palette
  let h = 0;
  for (let i = 0; i < phase.length; i++) h = (h * 31 + phase.charCodeAt(i)) | 0;
  return OVERFLOW[Math.abs(h) % OVERFLOW.length]!;
}

export function PhaseBar(props: {
  durations: Record<string, number>;
  height?: number;
  showLabels?: boolean;
}): JSX.Element {
  const entries = () => Object.entries(props.durations).filter(([, ms]) => ms >= 0);
  const total = () => entries().reduce((sum, [, ms]) => sum + ms, 0);
  const segments = () => {
    let x = 0;
    return entries().map(([phase, ms]) => {
      const width = total() > 0 ? Math.max(2, (ms / total()) * 100) : 100 / Math.max(entries().length, 1);
      const segment = { phase, ms, x, width: Math.min(width, 100 - x) };
      x += width;
      return segment;
    });
  };
  const h = () => props.height ?? 10;
  return (
    <div class="flex flex-col gap-1">
      <svg
        viewBox={`0 0 100 ${h()}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Phase duration breakdown"
        class="w-full overflow-hidden rounded-sm"
        style={{ height: `${h()}px` }}
      >
        <For each={segments()}>
          {(segment) => (
            <rect
              x={segment.x}
              y="0"
              width={segment.width}
              height={h()}
              fill={colorForPhase(segment.phase)}
            >
              <title>{`${segment.phase}: ${formatDuration(segment.ms)}`}</title>
            </rect>
          )}
        </For>
      </svg>
      {props.showLabels ? (
        <div class="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-text-muted">
          <For each={entries()}>
            {([phase, ms]) => (
              <span class="inline-flex items-center gap-1">
                <span
                  class="h-1.5 w-1.5 rounded-sm"
                  style={{ 'background-color': colorForPhase(phase) }}
                />
                <span>{phase}</span>
                <span class="font-mono text-text-subtle">{formatDuration(ms)}</span>
              </span>
            )}
          </For>
        </div>
      ) : null}
    </div>
  );
}

/** Standalone legend chip row. Show all known phases or the union over a list of cycles. */
export function PhaseLegend(props: { phases?: string[] }): JSX.Element {
  const phases = () => {
    if (props.phases && props.phases.length > 0) return props.phases;
    return Object.keys(PHASE_COLORS);
  };
  return (
    <div class="flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-text-muted">
      <For each={phases()}>
        {(phase) => (
          <span class="inline-flex items-center gap-1.5">
            <span
              class="h-2 w-2 rounded-sm"
              style={{ 'background-color': colorForPhase(phase) }}
            />
            <span class="font-mono">{phase}</span>
          </span>
        )}
      </For>
    </div>
  );
}
