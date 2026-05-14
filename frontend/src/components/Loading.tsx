import { createSignal, onCleanup, onMount, Show, type JSX } from 'solid-js';
import { Loader2 } from 'lucide-solid';
import { cn } from '~/lib/cn';
import { useTheme } from '~/app/ThemeProvider';
import logoMark from '../../assets/logo/mark/vector/opendream_mark_gradient.svg?url';
import rollingWavesDark from '../../assets/animation/svg/opendream_loop_dark_rolling_waves.svg?url';
import rollingWavesLight from '../../assets/animation/svg/opendream_loop_light_rolling_waves.svg?url';

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

export function LoadingPage(props: { label?: string }): JSX.Element {
  return (
    <div class="flex h-[40vh] flex-col items-center justify-center gap-3 text-text-subtle">
      <LoadingBrand />
      <Loading size={16} />
      <span class="text-[11px] uppercase tracking-[0.1em]">
        {props.label ?? 'Loading'}
      </span>
    </div>
  );
}
