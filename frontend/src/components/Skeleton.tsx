import { For, type JSX } from 'solid-js';
import { cn } from '~/lib/cn';
import { ProgressiveLoading } from './Loading';

export interface SkeletonProps {
  class?: string;
  width?: string;
  height?: string;
}

export function Skeleton(props: SkeletonProps): JSX.Element {
  return (
    <div
      class={cn(
        'animate-pulse rounded-sm bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_14%,transparent)]',
        props.class,
      )}
      style={{ width: props.width ?? '100%', height: props.height ?? '12px' }}
    />
  );
}

export function SkeletonRows(props: { rows?: number; class?: string; label?: string }): JSX.Element {
  const rows = () => Array.from({ length: props.rows ?? 4 });
  return (
    <div class={cn('flex flex-col gap-3', props.class)}>
      <ProgressiveLoading
        compact
        label={props.label ?? 'Loading rows'}
        detail="Waiting for records from the workspace."
      />
      <For each={rows()}>
        {(_, i) => (
          <div
            class="hairline-b flex h-9 items-center gap-3 px-3"
            style={{ opacity: 1 - i() * 0.12 }}
          >
            <Skeleton width="22%" height="10px" />
            <Skeleton width="18%" height="10px" />
            <Skeleton width="14%" height="10px" />
            <div class="flex-1" />
            <Skeleton width="60px" height="10px" />
          </div>
        )}
      </For>
    </div>
  );
}

export function SkeletonStats(props: { label?: string } = {}): JSX.Element {
  return (
    <div class="flex flex-col gap-3">
      <ProgressiveLoading
        compact
        label={props.label ?? 'Loading summary'}
        detail="Waiting for workspace summary data."
      />
      <div class="flex flex-wrap items-baseline gap-x-8 gap-y-3">
        <For each={[0, 1, 2, 3]}>
          {() => (
            <div class="flex flex-col gap-2">
              <Skeleton width="56px" height="9px" />
              <Skeleton width="44px" height="22px" />
            </div>
          )}
        </For>
      </div>
    </div>
  );
}
