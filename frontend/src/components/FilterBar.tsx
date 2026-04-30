import { Popover } from '@kobalte/core/popover';
import { ChevronDown, Search, SlidersHorizontal } from 'lucide-solid';
import { For, Show, type JSX } from 'solid-js';
import { Chip } from './Chip';

export interface ActiveFilter {
  key: string;
  label: string;
  onRemove: () => void;
}

export interface SortOption {
  value: string;
  label: string;
}

export interface FilterBarProps {
  search?: string;
  onSearchChange?: (v: string) => void;
  searchPlaceholder?: string;
  activeFilters?: ActiveFilter[];
  filterForm?: JSX.Element;
  sort?: string;
  onSortChange?: (v: string) => void;
  sortOptions?: SortOption[];
}

export function FilterBar(props: FilterBarProps): JSX.Element {
  const filterCount = () => props.activeFilters?.length ?? 0;

  return (
    <div class="flex flex-col gap-2.5">
      <div class="flex items-center gap-2">
        <Show when={props.onSearchChange}>
          <label class="relative flex h-9 flex-1 items-center">
            <Search
              size={13}
              class="pointer-events-none absolute left-3 text-text-subtle"
            />
            <input
              type="text"
              value={props.search ?? ''}
              placeholder={props.searchPlaceholder ?? 'Search'}
              onInput={(e) => props.onSearchChange?.(e.currentTarget.value)}
              class="h-9 w-full rounded-md bg-surface pl-8 pr-3 text-sm text-text placeholder:text-text-subtle hairline transition-shadow duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            />
          </label>
        </Show>

        <Show when={props.filterForm}>
          <Popover>
            <Popover.Trigger class="inline-flex h-9 items-center gap-1.5 rounded-md bg-surface px-3 text-xs text-text-muted hairline transition-colors duration-150 hover:bg-surface-elevated hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60">
              <SlidersHorizontal size={12} />
              <span>Filters</span>
              <Show when={filterCount() > 0}>
                <span class="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-medium text-accent-fg">
                  {filterCount()}
                </span>
              </Show>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content class="overlay-fade z-50 w-80 rounded-md bg-surface p-3 hairline shadow-[var(--shadow-elevated)]">
                <Popover.Arrow />
                {props.filterForm}
              </Popover.Content>
            </Popover.Portal>
          </Popover>
        </Show>

        <Show when={props.sortOptions && props.onSortChange}>
          <label class="relative inline-flex h-9 items-center">
            <select
              value={props.sort ?? ''}
              onChange={(e) => props.onSortChange?.(e.currentTarget.value)}
              class="h-9 appearance-none rounded-md bg-surface pl-3 pr-7 text-xs text-text-muted hairline transition-colors duration-150 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <For each={props.sortOptions}>
                {(opt) => <option value={opt.value}>{opt.label}</option>}
              </For>
            </select>
            <ChevronDown
              size={12}
              class="pointer-events-none absolute right-2 text-text-subtle"
            />
          </label>
        </Show>
      </div>

      <Show when={(props.activeFilters?.length ?? 0) > 0}>
        <div class="flex flex-wrap items-center gap-1.5">
          <For each={props.activeFilters}>
            {(f) => (
              <Chip variant="accent" onRemove={f.onRemove}>
                {f.label}
              </Chip>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}
