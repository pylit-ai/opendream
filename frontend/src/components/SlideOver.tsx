import { Dialog } from '@kobalte/core/dialog';
import { X } from 'lucide-solid';
import type { JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export interface SlideOverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: JSX.Element;
  class?: string;
}

export function SlideOver(props: SlideOverProps): JSX.Element {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange} modal>
      <Dialog.Portal>
        <Dialog.Overlay class="overlay-fade fixed inset-0 z-40 bg-black/40 backdrop-blur-[3px]" />
        <div class="fixed inset-0 z-50 flex justify-end">
          <Dialog.Content
            class={cn(
              'flex h-full w-[460px] flex-col bg-surface',
              'hairline-l shadow-[var(--shadow-elevated)]',
              'data-[expanded]:animate-[slideOverIn_360ms_var(--ease-apple)]',
              props.class,
            )}
            style={{
              animation: 'slideOverIn 360ms var(--ease-apple)',
            }}
          >
            <header class="hairline-b flex h-14 items-center justify-between px-5">
              <div class="flex flex-col gap-0.5">
                <Dialog.Title class="text-sm font-semibold text-text">
                  {props.title}
                </Dialog.Title>
                {props.description ? (
                  <Dialog.Description class="font-mono text-[11px] tracking-tight text-text-muted">
                    {props.description}
                  </Dialog.Description>
                ) : null}
              </div>
              <Dialog.CloseButton
                aria-label="Close"
                class="flex h-7 w-7 items-center justify-center rounded-md text-text-subtle transition-colors hover:bg-surface-elevated hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
              >
                <X size={14} />
              </Dialog.CloseButton>
            </header>
            <div class="flex-1 overflow-y-auto scrollbar-thin">{props.children}</div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog>
  );
}
