import type { JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export interface PageProps {
  title: string;
  subtitle?: string;
  actions?: JSX.Element;
  children?: JSX.Element;
  class?: string;
}

export function Page(props: PageProps): JSX.Element {
  return (
    <div class={cn('page-enter flex flex-col gap-8 pb-16 pt-2', props.class)}>
      <header class="flex items-end justify-between gap-4">
        <div class="flex flex-col gap-1">
          <h1 class="text-2xl font-semibold tracking-tight text-text">{props.title}</h1>
          {props.subtitle ? (
            <p class="text-sm text-text-muted">{props.subtitle}</p>
          ) : null}
        </div>
        {props.actions ? (
          <div class="flex items-center gap-1.5">{props.actions}</div>
        ) : null}
      </header>
      <div class="flex flex-col gap-6">{props.children}</div>
    </div>
  );
}
