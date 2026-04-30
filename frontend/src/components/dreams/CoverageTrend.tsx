import { For, type JSX } from 'solid-js';
import type { DreamCoverageBucket } from '~/api/types';

const SERIES: Array<[
  keyof Pick<DreamCoverageBucket, 'explicit_events' | 'transcript_episodes' | 'automation'>,
  string,
  string,
]> = [
  ['explicit_events', 'Explicit events', '#14b8a6'],
  ['transcript_episodes', 'Transcripts', '#6366f1'],
  ['automation', 'Automation', '#f59e0b'],
];

export function CoverageTrend(props: { buckets: DreamCoverageBucket[] }): JSX.Element {
  const items = () => props.buckets ?? [];
  const isEmpty = () => items().length === 0;
  // Shared y-scale across series so heights are comparable.
  const yMax = () =>
    Math.max(
      ...items().flatMap((b) => SERIES.map(([k]) => b[k] || 0)),
      1,
    );
  const points = (key: (typeof SERIES)[number][0]) => {
    const list = items();
    if (list.length === 0) return '';
    if (list.length === 1) {
      const y = 24 - ((list[0]![key] || 0) / yMax()) * 22;
      return `0,${y} 100,${y}`;
    }
    return list
      .map((item, i) => {
        const x = (i / (list.length - 1)) * 100;
        const y = 24 - ((item[key] || 0) / yMax()) * 22;
        return `${x},${y}`;
      })
      .join(' ');
  };
  return (
    <div class="flex flex-col gap-1.5">
      <svg
        viewBox="0 0 100 28"
        preserveAspectRatio="none"
        role="img"
        aria-label="Signal coverage trend over the last 7 days"
        class="h-14 w-full"
      >
        <line x1="0" y1="24" x2="100" y2="24" stroke="rgb(var(--c-border))" stroke-width="0.5" />
        <For each={SERIES}>
          {([key, , color]) => (
            <polyline
              points={points(key)}
              fill="none"
              stroke={color}
              stroke-width="1.5"
              stroke-linejoin="round"
              vector-effect="non-scaling-stroke"
              opacity={isEmpty() ? 0 : 0.95}
            />
          )}
        </For>
      </svg>
      <div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-text-muted">
        <For each={SERIES}>
          {([, label, color]) => (
            <span class="inline-flex items-center gap-1">
              <span class="h-1.5 w-1.5 rounded-sm" style={{ 'background-color': color }} />
              {label}
            </span>
          )}
        </For>
      </div>
    </div>
  );
}
