import type { Component, JSX } from 'solid-js';
import { Tooltip } from '@kobalte/core/tooltip';
import type { LucideProps } from 'lucide-solid';
import { cn } from '~/lib/cn';

export interface IconButtonProps {
  icon: Component<LucideProps>;
  label: string;
  onClick?: (e: MouseEvent) => void;
  disabled?: boolean;
  active?: boolean;
  class?: string;
}

export function IconButton(props: IconButtonProps): JSX.Element {
  const Icon = props.icon;
  return (
    <Tooltip openDelay={300} closeDelay={0}>
      <Tooltip.Trigger
        as="button"
        type="button"
        aria-label={props.label}
        disabled={props.disabled}
        onClick={props.onClick}
        class={cn(
          'inline-flex h-7 w-7 items-center justify-center rounded-md text-text-subtle transition-colors duration-150',
          'hover:bg-surface-elevated hover:text-text',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-1 focus-visible:ring-offset-bg',
          'disabled:cursor-not-allowed disabled:opacity-40',
          props.active && 'bg-surface-elevated text-text',
          props.class,
        )}
      >
        <Icon size={14} />
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content class="z-50 rounded-md bg-surface-elevated px-2 py-1 text-[11px] text-text shadow-[var(--shadow-elevated)] hairline">
          {props.label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip>
  );
}
