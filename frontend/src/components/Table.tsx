import { For, type JSX } from 'solid-js';
import { cn } from '~/lib/cn';

export interface TableColumn<T> {
  key: string;
  header: string;
  render: (item: T) => JSX.Element;
  width?: string;
  align?: 'left' | 'right' | 'center';
  numeric?: boolean;
}

export interface TableProps<T> {
  items: T[];
  columns: TableColumn<T>[];
  onRowClick?: (item: T) => void;
  rowKey?: (item: T, index: number) => string | number;
  empty?: JSX.Element;
}

export function Table<T>(props: TableProps<T>): JSX.Element {
  return (
    <div class="overflow-x-auto">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="hairline-b text-[10px] uppercase tracking-[0.08em] text-text-subtle">
            <For each={props.columns}>
              {(col) => (
                <th
                  class={cn(
                    'h-9 px-3 text-left font-medium',
                    (col.align === 'right' || col.numeric) && 'text-right',
                    col.align === 'center' && 'text-center',
                  )}
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.header}
                </th>
              )}
            </For>
          </tr>
        </thead>
        <tbody>
          {props.items.length === 0 && props.empty ? (
            <tr>
              <td colspan={props.columns.length} class="py-10">
                {props.empty}
              </td>
            </tr>
          ) : (
            <For each={props.items}>
              {(item, idx) => (
                <tr
                  onClick={
                    props.onRowClick ? () => props.onRowClick?.(item) : undefined
                  }
                  onKeyDown={
                    props.onRowClick
                      ? (e: KeyboardEvent) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            props.onRowClick?.(item);
                          }
                        }
                      : undefined
                  }
                  tabIndex={props.onRowClick ? 0 : undefined}
                  role={props.onRowClick ? 'button' : undefined}
                  class={cn(
                    'row-hover hairline-b text-text',
                    props.onRowClick &&
                      'cursor-pointer hover:bg-[color-mix(in_oklab,rgb(var(--c-surface-elevated))_70%,transparent)]',
                  )}
                  data-row-key={
                    props.rowKey ? props.rowKey(item, idx()) : idx()
                  }
                >
                  <For each={props.columns}>
                    {(col) => (
                      <td
                        class={cn(
                          'h-11 truncate px-3 text-sm',
                          (col.align === 'right' || col.numeric) && 'text-right',
                          col.align === 'center' && 'text-center',
                          col.numeric && 'tabular-nums',
                        )}
                      >
                        {col.render(item)}
                      </td>
                    )}
                  </For>
                </tr>
              )}
            </For>
          )}
        </tbody>
      </table>
    </div>
  );
}
