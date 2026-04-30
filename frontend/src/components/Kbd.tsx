import type { JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export interface KbdProps {
  children: JSX.Element;
  class?: string;
}

export function Kbd(props: KbdProps): JSX.Element {
  return (
    <kbd
      class={cn(
        'inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] px-1.5 font-mono text-[10px] font-medium text-text-subtle',
        'bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_10%,transparent)]',
        'shadow-[inset_0_-1px_0_color-mix(in_oklab,rgb(var(--c-text-muted))_18%,transparent)]',
        props.class,
      )}
    >
      {props.children}
    </kbd>
  );
}
