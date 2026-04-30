import type { JSX } from 'solid-js';
import { Loader2 } from 'lucide-solid';
import { cn } from '~/lib/cn';

export function Loading(props: { size?: number; class?: string }): JSX.Element {
  return (
    <Loader2
      size={props.size ?? 14}
      class={cn('animate-spin text-text-subtle', props.class)}
    />
  );
}

export function LoadingPage(props: { label?: string }): JSX.Element {
  return (
    <div class="flex h-[40vh] flex-col items-center justify-center gap-3 text-text-subtle">
      <Loading size={18} />
      <span class="text-[11px] uppercase tracking-[0.1em]">
        {props.label ?? 'Loading'}
      </span>
    </div>
  );
}
