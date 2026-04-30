import type { Component, JSX } from 'solid-js';
import type { LucideProps } from 'lucide-solid';

export interface EmptyStateProps {
  icon: Component<LucideProps>;
  title: string;
  description?: string;
  action?: JSX.Element;
}

export function EmptyState(props: EmptyStateProps): JSX.Element {
  const Icon = props.icon;
  return (
    <div class="flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <Icon size={40} stroke-width={1} class="text-text-subtle opacity-40" />
      <div class="flex flex-col gap-1">
        <div class="text-sm font-medium text-text">{props.title}</div>
        {props.description ? (
          <div class="max-w-sm text-sm text-text-muted">{props.description}</div>
        ) : null}
      </div>
      {props.action ? <div class="mt-2">{props.action}</div> : null}
    </div>
  );
}
