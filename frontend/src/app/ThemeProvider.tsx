import {
  createContext,
  createEffect,
  createSignal,
  onCleanup,
  onMount,
  useContext,
  type JSX,
} from 'solid-js';

export type ThemeMode = 'light' | 'dark' | 'system';
type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'opendream:theme';

interface ThemeContextValue {
  mode: () => ThemeMode;
  resolved: () => ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>();

function readStoredMode(): ThemeMode {
  try {
    if (typeof window !== 'undefined') {
      const qs = new URLSearchParams(window.location.search);
      const override = qs.get('theme');
      if (override === 'light' || override === 'dark' || override === 'system') return override;
    }
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch {
    // ignore
  }
  return 'system';
}

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolve(mode: ThemeMode): ResolvedTheme {
  if (mode === 'system') return systemPrefersDark() ? 'dark' : 'light';
  return mode;
}

export function ThemeProvider(props: { children: JSX.Element }): JSX.Element {
  const [mode, setModeSignal] = createSignal<ThemeMode>(readStoredMode());
  const [resolved, setResolved] = createSignal<ResolvedTheme>(resolve(mode()));

  const apply = (next: ResolvedTheme) => {
    document.documentElement.setAttribute('data-theme', next);
    setResolved(next);
  };

  const setMode = (next: ThemeMode) => {
    setModeSignal(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
    apply(resolve(next));
  };

  createEffect(() => {
    apply(resolve(mode()));
  });

  onMount(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      if (mode() === 'system') apply(systemPrefersDark() ? 'dark' : 'light');
    };
    mql.addEventListener('change', onChange);
    onCleanup(() => mql.removeEventListener('change', onChange));
  });

  const value: ThemeContextValue = { mode, resolved, setMode };
  return <ThemeContext.Provider value={value}>{props.children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
