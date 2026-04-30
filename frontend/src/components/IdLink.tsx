import { type JSX } from 'solid-js';
import { cn } from '~/lib/cn';
import { shortId } from '~/lib/idTooltip';

export interface IdLinkProps {
  id: string | null | undefined;
  /** Optional one-line preview shown in title tooltip. */
  preview?: string;
  onClick?: () => void;
  onHover?: () => void;
  class?: string;
  full?: boolean;
}

/**
 * Clickable opaque ID with truncate-middle display + tooltip preview.
 * Click opens an inspector; hover triggers prefetch.
 */
export function IdLink(props: IdLinkProps): JSX.Element {
  const display = () => (props.full ? props.id ?? '—' : shortId(props.id));
  const title = () => {
    const parts: string[] = [];
    if (props.id) parts.push(props.id);
    if (props.preview) parts.push(props.preview);
    return parts.join('\n');
  };
  if (!props.id) return <span class="text-text-subtle">—</span>;
  return (
    <button
      type="button"
      title={title()}
      onClick={(e) => {
        e.stopPropagation();
        props.onClick?.();
      }}
      onMouseEnter={() => props.onHover?.()}
      class={cn(
        'group inline-flex max-w-full items-center gap-1 rounded px-1 -mx-1',
        'font-mono text-[11.5px] text-text-muted',
        'transition-colors duration-150',
        'hover:text-accent hover:bg-[color-mix(in_oklab,rgb(var(--c-accent))_8%,transparent)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
        props.class,
      )}
    >
      <span class="truncate">{display()}</span>
    </button>
  );
}
