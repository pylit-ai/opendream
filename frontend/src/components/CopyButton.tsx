import { Check, Copy } from 'lucide-solid';
import { createSignal, type JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export interface CopyButtonProps {
  value: string;
  class?: string;
  label?: string;
  size?: number;
}

export function CopyButton(props: CopyButtonProps): JSX.Element {
  const [copied, setCopied] = createSignal(false);
  const onClick = async (e: MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(props.value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1100);
    } catch {
      // ignore
    }
  };
  return (
    <button
      type="button"
      aria-label={props.label ?? 'Copy'}
      title={props.label ?? 'Copy'}
      onClick={onClick}
      class={cn(
        'inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-text-subtle transition-colors duration-150',
        'hover:bg-surface-elevated hover:text-text',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
        props.class,
      )}
    >
      {copied() ? <Check size={props.size ?? 11} /> : <Copy size={props.size ?? 11} />}
    </button>
  );
}
