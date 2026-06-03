import { createSignal, onCleanup, onMount, Show, type JSX } from 'solid-js';
import { useLocation } from '@solidjs/router';

/**
 * Dev-only floating perf indicator.
 * Tracks last route change duration via location.pathname signal + RAF.
 * Only renders when import.meta.env.DEV is true.
 */
export function PerfBanner(): JSX.Element {
  if (!import.meta.env.DEV) return <></>;
  const location = useLocation();
  const [last, setLast] = createSignal<{ path: string; ms: number } | null>(null);
  let lastPath = location.pathname;
  let pendingStart: number | null = null;

  const tick = (): void => {
    if (location.pathname !== lastPath) {
      lastPath = location.pathname;
      pendingStart = performance.now();
      // Wait two frames for content to commit.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          if (pendingStart != null) {
            const ms = performance.now() - pendingStart;
            setLast({ path: lastPath, ms });
            pendingStart = null;
          }
        }),
      );
    }
  };

  let interval: number | undefined;
  onMount(() => {
    interval = window.setInterval(tick, 80);
  });
  onCleanup(() => {
    if (interval != null) window.clearInterval(interval);
  });

  return (
    <Show when={last()}>
      {(v) => (
        <div class="pointer-events-none fixed bottom-2 right-2 z-50 rounded-md hairline bg-surface px-2 py-1 font-mono text-[10px] text-text-muted shadow-sm">
          <span class="text-text-subtle">nav</span>{' '}
          <span class="text-accent">{v().ms.toFixed(0)}ms</span>{' '}
          <span class="text-text-subtle">{v().path}</span>
        </div>
      )}
    </Show>
  );
}
