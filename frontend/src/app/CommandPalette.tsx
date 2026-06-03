import { Dialog } from '@kobalte/core/dialog';
import { useNavigate } from '@solidjs/router';
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  onMount,
  Show,
} from 'solid-js';
import { cn } from '~/lib/cn';
import { Kbd } from '~/components/Kbd';
import { ROUTES } from './routes';

const RECENT_KEY = 'opendream:cmdk:recent';
const MAX_RECENT = 4;

function fuzzy(query: string, target: string): boolean {
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (!q) return true;
  let i = 0;
  for (const ch of t) {
    if (ch === q[i]) i++;
    if (i >= q.length) return true;
  }
  return false;
}

function readRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}

function writeRecent(paths: string[]): void {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(paths.slice(0, MAX_RECENT)));
  } catch {
    // ignore
  }
}

export function CommandPalette() {
  const [open, setOpen] = createSignal(false);
  const [query, setQuery] = createSignal('');
  const [highlight, setHighlight] = createSignal(0);
  const [recent, setRecent] = createSignal<string[]>(readRecent());
  const navigate = useNavigate();

  const filtered = createMemo(() => {
    const q = query();
    if (!q) {
      // Show recent first, then all routes
      const recents = recent()
        .map((p) => ROUTES.find((r) => r.path === p))
        .filter((r): r is (typeof ROUTES)[number] => r !== undefined);
      const others = ROUTES.filter((r) => !recent().includes(r.path));
      return { recents, others, all: [...recents, ...others] };
    }
    const matches = ROUTES.filter((r) => fuzzy(q, r.name) || fuzzy(q, r.path));
    return { recents: [], others: matches, all: matches };
  });

  const onKey = (e: KeyboardEvent) => {
    const isMeta = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
    if (isMeta) {
      e.preventDefault();
      setOpen((v) => !v);
      setQuery('');
      setHighlight(0);
    }
  };

  onMount(() => {
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  createEffect(() => {
    if (!open()) return;
    setRecent(readRecent());
  });

  const choose = (path: string) => {
    const next = [path, ...recent().filter((p) => p !== path)].slice(0, MAX_RECENT);
    writeRecent(next);
    setRecent(next);
    setOpen(false);
    navigate(path);
  };

  const onListKey = (e: KeyboardEvent) => {
    const items = filtered().all;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => (h + 1) % items.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => (h - 1 + items.length) % items.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = items[highlight()];
      if (target) choose(target.path);
    }
  };

  return (
    <Dialog open={open()} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay
          class={cn(
            'overlay-fade fixed inset-0 z-40 backdrop-blur-xl',
            'bg-[color-mix(in_oklab,rgb(var(--c-bg))_55%,transparent)]',
          )}
        />
        <div class="fixed inset-0 z-50 flex items-start justify-center pt-[14vh]">
          <Dialog.Content
            class={cn(
              'palette-enter w-full max-w-xl overflow-hidden rounded-xl bg-surface',
              'hairline shadow-[var(--shadow-elevated)]',
            )}
          >
            <input
              autofocus
              type="text"
              placeholder="Search routes, runs, memories…"
              value={query()}
              onInput={(e) => {
                setQuery(e.currentTarget.value);
                setHighlight(0);
              }}
              onKeyDown={onListKey}
              class="hairline-b w-full bg-transparent px-5 py-4 text-[15px] text-text outline-none placeholder:text-text-subtle"
            />
            <ul class="max-h-[60vh] overflow-y-auto py-2 scrollbar-thin">
              <Show when={!query() && filtered().recents.length > 0}>
                <li class="px-5 pb-1.5 pt-2 text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                  Recent
                </li>
                <For each={filtered().recents}>
                  {(route, i) => (
                    <PaletteItem
                      route={route}
                      index={i()}
                      highlight={highlight()}
                      onHover={setHighlight}
                      onPick={() => choose(route.path)}
                    />
                  )}
                </For>
                <li class="my-1.5 px-5">
                  <div class="hairline-b" />
                </li>
                <li class="px-5 pb-1.5 pt-1 text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                  All routes
                </li>
              </Show>
              <For each={filtered().others}>
                {(route, i) => {
                  const offset = !query() ? filtered().recents.length : 0;
                  return (
                    <PaletteItem
                      route={route}
                      index={i() + offset}
                      highlight={highlight()}
                      onHover={setHighlight}
                      onPick={() => choose(route.path)}
                    />
                  );
                }}
              </For>
              <Show when={filtered().all.length === 0}>
                <li class="px-5 py-6 text-center text-xs text-text-subtle">
                  No matches
                </li>
              </Show>
            </ul>
            <div class="hairline-t flex items-center justify-end gap-3 px-5 py-2 text-[10px] text-text-subtle">
              <span class="flex items-center gap-1">
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd>
                navigate
              </span>
              <span class="flex items-center gap-1">
                <Kbd>↵</Kbd>
                open
              </span>
              <span class="flex items-center gap-1">
                <Kbd>esc</Kbd>
                close
              </span>
            </div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog>
  );
}

function PaletteItem(props: {
  route: (typeof ROUTES)[number];
  index: number;
  highlight: number;
  onHover: (i: number) => void;
  onPick: () => void;
}) {
  const Icon = props.route.icon;
  const isActive = () => props.highlight === props.index;
  return (
    <li>
      <button
        type="button"
        onMouseEnter={() => props.onHover(props.index)}
        onClick={props.onPick}
        class={cn(
          'flex w-full items-center gap-3 px-5 py-2.5 text-left text-[13.5px] transition-colors duration-100',
          isActive()
            ? 'bg-[color-mix(in_oklab,rgb(var(--c-accent))_14%,transparent)] text-text'
            : 'text-text-muted',
        )}
      >
        <Icon size={14} stroke-width={1.5} class={isActive() ? 'text-accent' : 'text-text-subtle'} />
        <span class="flex-1">{props.route.name}</span>
        <span class="font-mono text-[11px] text-text-subtle">{props.route.path}</span>
      </button>
    </li>
  );
}
