import { A, useLocation } from '@solidjs/router';
import { ChevronLeft, ChevronRight, Laptop, Moon, MousePointer2, Pin, PinOff, Search, Sun, type LucideProps } from 'lucide-solid';
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  onMount,
  Show,
  type Component,
  type JSX,
} from 'solid-js';
import { cn } from '~/lib/cn';
import { truncateMiddle } from '~/lib/format';
import { CommandPalette } from './CommandPalette';
import { GROUP_LABELS, GROUP_ORDER, ROUTES, type RouteDef, type RouteGroup } from './routes';
import { useTheme, type ThemeMode } from './ThemeProvider';
import { Kbd } from '~/components/Kbd';
import { prefetch } from '~/lib/cache';
import {
  getEvals,
  getExports,
  getGraph,
  getMemories,
  getOverview,
  getRetrievals,
  getReviews,
  getRuns,
  getSessions,
  getWorkspaces,
} from '~/api/client';

// 446-observability-perf: hover-prefetch primary endpoint per route so
// the panel renders from cache when the user clicks.
const ROUTE_PREFETCH: Record<string, () => void> = {
  '/overview': () => prefetch('overview', getOverview, 15_000),
  '/runs': () => prefetch('runs', () => getRuns(), 15_000),
  '/memories': () =>
    prefetch('memories:{"limit":20}', () => getMemories({ limit: 20 }), 15_000),
  '/dreams': () => prefetch('runs', () => getRuns(), 15_000),
  '/retrievals': () => prefetch('retrievals', () => getRetrievals(), 15_000),
  '/sessions': () => prefetch('sessions', getSessions, 15_000),
  '/reviews': () => prefetch('reviews', getReviews, 15_000),
  '/workspaces': () => prefetch('workspaces', getWorkspaces, 30_000),
  '/graph': () =>
    prefetch(
      'graph:{"depth":1,"layout":"hierarchical","limit":100}',
      () => getGraph({ depth: 1, layout: 'hierarchical', limit: 100 }),
      30_000,
    ),
  '/evals': () => prefetch('evals', getEvals, 30_000),
  '/exports': () => prefetch('exports', getExports, 30_000),
};

const SIDEBAR_COLLAPSED = 60;
const SIDEBAR_EXPANDED = 220;
const PIN_KEY = 'opendream:sidebar:pinned';
const HOVER_KEY = 'opendream:sidebar:hover-expand';

function ThemeToggle(): JSX.Element {
  const { mode, setMode } = useTheme();
  const opts: Array<{ value: ThemeMode; icon: Component<LucideProps>; label: string }> = [
    { value: 'light', icon: Sun, label: 'Light' },
    { value: 'system', icon: Laptop, label: 'System' },
    { value: 'dark', icon: Moon, label: 'Dark' },
  ];
  return (
    <div role="group" class="inline-flex items-center rounded-md bg-surface p-0.5 hairline">
      <For each={opts}>
        {(opt) => {
          const Icon = opt.icon;
          const active = () => mode() === opt.value;
          return (
            <button
              type="button"
              aria-label={opt.label}
              aria-pressed={active()}
              onClick={() => setMode(opt.value)}
              class={cn(
                'flex h-6 w-6 items-center justify-center rounded text-text-subtle transition-colors duration-150 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
                active() && 'bg-surface-elevated text-text',
              )}
            >
              <Icon size={13} />
            </button>
          );
        }}
      </For>
    </div>
  );
}

function readPinned(): boolean {
  try {
    return localStorage.getItem(PIN_KEY) === '1';
  } catch {
    return false;
  }
}

function readHoverExpand(): boolean {
  try {
    return localStorage.getItem(HOVER_KEY) === '1';
  } catch {
    return false;
  }
}

interface GroupedRoutes {
  group: RouteGroup;
  routes: RouteDef[];
}

const GROUPED: GroupedRoutes[] = GROUP_ORDER.map((g) => ({
  group: g,
  routes: ROUTES.filter((r) => r.group === g),
})).filter((g) => g.routes.length > 0);

function Sidebar(): JSX.Element {
  const [pinned, setPinned] = createSignal(readPinned());
  const [hoverExpand, setHoverExpand] = createSignal(readHoverExpand());
  const [hover, setHover] = createSignal(false);
  const location = useLocation();
  const expanded = () => pinned() || (hoverExpand() && hover());

  createEffect(() => {
    try {
      localStorage.setItem(PIN_KEY, pinned() ? '1' : '0');
    } catch {
      // ignore
    }
  });
  createEffect(() => {
    try {
      localStorage.setItem(HOVER_KEY, hoverExpand() ? '1' : '0');
    } catch {
      // ignore
    }
  });

  const onKey = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
      e.preventDefault();
      setPinned((v) => !v);
    }
  };

  onMount(() => {
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  return (
    <aside
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: `${expanded() ? SIDEBAR_EXPANDED : SIDEBAR_COLLAPSED}px`,
      }}
      class="hairline-r fixed inset-y-0 left-0 z-30 flex flex-col bg-surface transition-[width] duration-200 ease-[var(--ease-apple)]"
    >
      <div class="flex h-14 items-center justify-center">
        <div class="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-[11px] font-semibold tracking-tight text-accent-fg">
          OD
        </div>
      </div>
      <nav class="flex-1 overflow-y-auto py-1 scrollbar-thin">
        <For each={GROUPED}>
          {(g, gi) => (
            <div class="flex flex-col">
              <Show
                when={expanded()}
                fallback={
                  <Show when={gi() > 0}>
                    <div class="my-2 mx-3 h-px bg-[color-mix(in_oklab,rgb(var(--c-border))_60%,transparent)]" />
                  </Show>
                }
              >
                <div
                  class={cn(
                    'px-3 pb-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-text-subtle',
                    gi() === 0 ? 'pt-3' : 'pt-4',
                  )}
                >
                  {GROUP_LABELS[g.group]}
                </div>
              </Show>
              <ul class="flex flex-col gap-px px-2">
                <For each={g.routes}>
                  {(route) => {
                    const Icon = route.icon;
                    const active = () =>
                      location.pathname === route.path ||
                      (route.path !== '/' && location.pathname.startsWith(route.path));
                    return (
                      <li>
                        <A
                          href={route.path}
                          title={expanded() ? undefined : route.name}
                          onMouseEnter={() => ROUTE_PREFETCH[route.path]?.()}
                          onFocus={() => ROUTE_PREFETCH[route.path]?.()}
                          class={cn(
                            'group relative flex h-9 items-center gap-3 rounded-md pl-3 pr-2 text-[13px] text-text-muted transition-colors duration-150',
                            'hover:text-text',
                            active() && 'text-text',
                          )}
                        >
                          <span
                            class={cn(
                              'pointer-events-none absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r-full bg-accent transition-opacity duration-200',
                              active() ? 'opacity-100' : 'opacity-0',
                            )}
                          />
                          <Icon
                            size={15}
                            stroke-width={1.5}
                            class={cn('shrink-0', active() ? 'text-text' : 'text-text-subtle')}
                          />
                          <span
                            class={cn(
                              'truncate transition-opacity duration-150',
                              expanded() ? 'opacity-100' : 'opacity-0',
                            )}
                          >
                            {route.name}
                          </span>
                        </A>
                      </li>
                    );
                  }}
                </For>
              </ul>
            </div>
          )}
        </For>
      </nav>
      <Show
        when={expanded()}
        fallback={
          <div class="flex h-10 items-center justify-center">
            <button
              type="button"
              aria-label="Expand sidebar"
              title="Expand (⌘\\)"
              onClick={() => setPinned(true)}
              class="flex h-7 w-7 items-center justify-center rounded text-text-subtle transition-colors duration-150 hover:bg-surface-elevated hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        }
      >
        <div class="flex h-10 items-center justify-between gap-1 px-3">
          <button
            type="button"
            aria-pressed={hoverExpand()}
            aria-label={hoverExpand() ? 'Disable hover-expand' : 'Enable hover-expand'}
            title={
              hoverExpand()
                ? 'Hover-expand: ON (collapses on mouse-out unless pinned)'
                : 'Hover-expand: OFF (sidebar stays in current state until you toggle)'
            }
            onClick={() => setHoverExpand((v) => !v)}
            class={cn(
              'flex h-6 items-center gap-1.5 rounded px-1.5 text-[10px] uppercase tracking-[0.06em] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
              hoverExpand()
                ? 'bg-surface-elevated text-text'
                : 'text-text-subtle hover:bg-surface-elevated hover:text-text',
            )}
          >
            <MousePointer2 size={10} />
            hover
          </button>
          <div class="flex items-center gap-1">
            <button
              type="button"
              aria-label={pinned() ? 'Unpin sidebar' : 'Pin sidebar'}
              title={pinned() ? 'Unpin (⌘\\)' : 'Pin (⌘\\)'}
              onClick={() => setPinned((v) => !v)}
              class="flex h-6 w-6 items-center justify-center rounded text-text-subtle transition-colors duration-150 hover:bg-surface-elevated hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              {pinned() ? <PinOff size={12} /> : <Pin size={12} />}
            </button>
            <button
              type="button"
              aria-label="Collapse sidebar"
              title="Collapse (⌘\\)"
              onClick={() => {
                setPinned(false);
                setHover(false);
              }}
              class="flex h-6 w-6 items-center justify-center rounded text-text-subtle transition-colors duration-150 hover:bg-surface-elevated hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <ChevronLeft size={12} />
            </button>
          </div>
        </div>
      </Show>
    </aside>
  );
}

function WorkspaceCrumb(props: { path: string }): JSX.Element {
  const display = createMemo(() => truncateMiddle(props.path, 56));
  return (
    <span
      title={props.path}
      class="font-mono text-[11px] tracking-[-0.01em] text-text-subtle"
    >
      {display()}
    </span>
  );
}

function TopBar(props: { workspacePath?: string }): JSX.Element {
  const path = () => props.workspacePath ?? '~/workspace';
  return (
    <header
      class={cn(
        'sticky top-0 z-20 flex h-14 items-center gap-3 px-6',
        'bg-[color-mix(in_oklab,rgb(var(--c-bg))_75%,transparent)] backdrop-blur-xl',
        'hairline-b',
      )}
    >
      <WorkspaceCrumb path={path()} />
      <div class="flex-1" />
      <button
        type="button"
        onClick={() => {
          const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
          window.dispatchEvent(event);
        }}
        class="inline-flex items-center gap-2 rounded-md bg-surface px-2.5 py-1.5 text-xs text-text-muted transition-colors duration-150 hairline hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
      >
        <Search size={12} />
        <span>Jump to</span>
        <Kbd>⌘K</Kbd>
      </button>
      <ThemeToggle />
    </header>
  );
}

export function AppShell(props: { children?: JSX.Element }): JSX.Element {
  const [pinned, setPinned] = createSignal(readPinned());

  // Re-read on storage events from other tabs / Sidebar's effect
  onMount(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === PIN_KEY) setPinned(e.newValue === '1');
    };
    const t = setInterval(() => setPinned(readPinned()), 400);
    window.addEventListener('storage', onStorage);
    onCleanup(() => {
      window.removeEventListener('storage', onStorage);
      clearInterval(t);
    });
  });

  return (
    <div class="min-h-screen bg-bg text-text">
      <Sidebar />
      <div
        style={{
          'padding-left': `${pinned() ? SIDEBAR_EXPANDED : SIDEBAR_COLLAPSED}px`,
          transition: 'padding-left 200ms var(--ease-apple)',
        }}
      >
        <TopBar />
        <main class="mx-auto w-full max-w-[1400px] px-8 pb-16 pt-10">
          {props.children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
