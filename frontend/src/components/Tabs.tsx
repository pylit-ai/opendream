import { Tabs as KTabs } from '@kobalte/core/tabs';
import { For, type JSX } from 'solid-js';

export interface TabItem {
  value: string;
  label: string;
}

export interface TabsProps {
  value: string;
  onChange: (value: string) => void;
  items: TabItem[];
  children?: JSX.Element;
}

export function Tabs(props: TabsProps): JSX.Element {
  return (
    <KTabs value={props.value} onChange={props.onChange}>
      <KTabs.List class="hairline-b relative flex flex-wrap items-center gap-x-4 gap-y-0">
        <For each={props.items}>
          {(item) => (
            <KTabs.Trigger
              value={item.value}
              class="relative h-9 cursor-pointer text-sm text-text-muted transition-colors duration-150 hover:text-text data-[selected]:text-text focus-visible:outline-none"
            >
              {item.label}
            </KTabs.Trigger>
          )}
        </For>
        <KTabs.Indicator class="absolute -bottom-px h-px bg-accent transition-[left,width] duration-280 ease-[var(--ease-apple)]" />
      </KTabs.List>
      {props.children}
    </KTabs>
  );
}
