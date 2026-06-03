import { For, type JSX } from 'solid-js';
import type { DreamFunnelCounts } from '~/api/types';
import { formatNumber } from '~/lib/format';

const STAGES: Array<[keyof DreamFunnelCounts, string, string]> = [
  ['considered', 'Considered', 'rgb(var(--c-accent))'],
  ['selected', 'Selected', 'rgb(var(--c-accent))'],
  ['generated', 'Generated', 'rgb(var(--c-accent))'],
  ['approved', 'Approved', 'rgb(var(--c-success))'],
  ['created', 'Created', 'rgb(var(--c-success))'],
];

/** Compact horizontal stage bars. One row per stage with width proportional to
 * the largest stage. Drop-off pct shown next to bar. */
export function Funnel(props: { counts: DreamFunnelCounts }): JSX.Element {
  const max = () => Math.max(...STAGES.map(([k]) => props.counts[k] || 0), 1);
  return (
    <div class="flex flex-col gap-0.5 text-[11px]">
      <For each={STAGES}>
        {([key, label, color], i) => {
          const value = props.counts[key] || 0;
          const prev = i() === 0 ? value : props.counts[STAGES[i() - 1]![0]] || 0;
          const pct = prev > 0 ? Math.round((value / prev) * 100) : 0;
          const widthPct = Math.max(1, (value / max()) * 100);
          return (
            <div class="grid grid-cols-[80px_1fr_56px] items-center gap-2">
              <span class="text-text-muted">{label}</span>
              <div class="relative h-4 w-full overflow-hidden rounded-sm bg-surface-elevated">
                <div
                  class="h-full transition-all duration-300"
                  style={{
                    width: `${widthPct}%`,
                    'background-color': color,
                    opacity: value === 0 ? 0.15 : 0.85,
                  }}
                />
                <span class="absolute inset-0 flex items-center pl-1.5 font-mono text-[10.5px] text-text">
                  {formatNumber(value)}
                </span>
              </div>
              <span class="text-right font-mono text-[10px] text-text-subtle">
                {i() === 0 ? '—' : `${pct}%`}
              </span>
            </div>
          );
        }}
      </For>
    </div>
  );
}
