import { For, Show, type JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export type StatTone = 'default' | 'ok' | 'warn' | 'danger' | 'accent';

export interface Stat {
  label: string;
  value: JSX.Element;
  tone?: StatTone;
  hint?: string;
  onClick?: () => void;
}

const TONE_STYLES: Record<StatTone, string> = {
  default: 'text-text',
  ok: 'text-success',
  warn: 'text-warn',
  danger: 'text-danger',
  accent: 'text-accent',
};

export interface StatStripProps {
  stats: Stat[];
  class?: string;
}

export function StatStrip(props: StatStripProps): JSX.Element {
  return (
    <div class={cn('flex flex-wrap items-end gap-x-10 gap-y-4', props.class)}>
      <For each={props.stats}>
        {(stat) => (
          <Show
            when={stat.onClick}
            fallback={
              <div class="flex flex-col gap-1">
                <span class="text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                  {stat.label}
                </span>
                <span
                  class={cn(
                    'font-light tabular-nums leading-none',
                    'text-[28px]',
                    TONE_STYLES[stat.tone ?? 'default'],
                  )}
                >
                  {stat.value}
                </span>
              </div>
            }
          >
            <button
              type="button"
              onClick={stat.onClick}
              title={stat.hint ?? `Filter by ${stat.label}`}
              class="group flex cursor-pointer flex-col items-start gap-1 rounded-md px-1 -mx-1 transition-colors duration-150 hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <span class="text-[10px] uppercase tracking-[0.1em] text-text-subtle group-hover:text-accent">
                {stat.label}
              </span>
              <span
                class={cn(
                  'font-light tabular-nums leading-none',
                  'text-[28px]',
                  TONE_STYLES[stat.tone ?? 'default'],
                )}
              >
                {stat.value}
              </span>
            </button>
          </Show>
        )}
      </For>
    </div>
  );
}
