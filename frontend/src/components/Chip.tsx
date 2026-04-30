import { Show, type JSX } from 'solid-js';
import { X } from 'lucide-solid';
import { cn } from '~/lib/cn';

export type ChipVariant = 'neutral' | 'ok' | 'warn' | 'danger' | 'accent';

export interface ChipProps {
  variant?: ChipVariant;
  onRemove?: () => void;
  children: JSX.Element;
  class?: string;
}

const VARIANT_STYLES: Record<ChipVariant, string> = {
  neutral:
    'bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_10%,transparent)] text-text-muted',
  ok: 'bg-[color-mix(in_oklab,rgb(var(--c-success))_12%,transparent)] text-success',
  warn: 'bg-[color-mix(in_oklab,rgb(var(--c-warn))_14%,transparent)] text-warn',
  danger:
    'bg-[color-mix(in_oklab,rgb(var(--c-danger))_12%,transparent)] text-danger',
  accent:
    'bg-[color-mix(in_oklab,rgb(var(--c-accent))_12%,transparent)] text-accent',
};

export function Chip(props: ChipProps): JSX.Element {
  return (
    <span
      class={cn(
        'inline-flex h-[20px] items-center gap-1 rounded-full px-2 text-[10.5px] font-medium tracking-wide',
        VARIANT_STYLES[props.variant ?? 'neutral'],
        props.class,
      )}
    >
      <span class="truncate">{props.children}</span>
      <Show when={props.onRemove}>
        <button
          type="button"
          aria-label="Remove"
          onClick={(e) => {
            e.stopPropagation();
            props.onRemove?.();
          }}
          class="flex h-3 w-3 items-center justify-center rounded-sm opacity-60 transition-opacity hover:opacity-100"
        >
          <X size={10} />
        </button>
      </Show>
    </span>
  );
}
