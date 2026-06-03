import { AlertTriangle, RefreshCw } from 'lucide-solid';
import type { JSX } from 'solid-js';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState(props: ErrorStateProps): JSX.Element {
  return (
    <div class="flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <AlertTriangle size={36} stroke-width={1.25} class="text-danger opacity-70" />
      <div class="flex flex-col gap-1">
        <div class="text-sm font-medium text-text">
          {props.title ?? 'Something went wrong'}
        </div>
        {props.message ? (
          <div class="max-w-md text-sm text-text-muted">{props.message}</div>
        ) : null}
      </div>
      {props.onRetry ? (
        <button
          type="button"
          onClick={props.onRetry}
          class="inline-flex items-center gap-1.5 rounded-md bg-surface px-3 py-1.5 text-xs text-text transition-colors duration-150 hairline hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      ) : null}
    </div>
  );
}
