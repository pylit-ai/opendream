import { createEffect, on } from 'solid-js';
import { useSearchParams } from '@solidjs/router';

/**
 * Two-way binding between a `?id=<id>` URL search param and a slide-over
 * inspector signal. Mounting reads the param and pushes into setSelected;
 * setSelected pushes back into the URL so the URL is shareable / bookmarkable.
 *
 * Usage:
 *   const { selected, setSelected } = useDeepLink();
 *   ...
 *   <SlideOver open={selected() !== null} onOpenChange={(o) => !o && setSelected(null)} />
 */
export function useDeepLink(paramName: string = 'id'): {
  selected: () => string | null;
  setSelected: (id: string | null) => void;
  searchParams: ReturnType<typeof useSearchParams>[0];
} {
  const [searchParams, setSearchParams] = useSearchParams();

  const selected = (): string | null => {
    const v = searchParams[paramName];
    if (typeof v === 'string' && v) return v;
    return null;
  };

  const setSelected = (id: string | null): void => {
    setSearchParams({ [paramName]: id ?? undefined } as Record<string, string | undefined>, {
      replace: false,
    });
  };

  return { selected, setSelected, searchParams };
}

/**
 * Bidirectional binding between a single search param and a string signal
 * accessor/setter. When the URL param changes, push into the local state.
 * When the local state changes, push into the URL.
 */
export function bindSearchParam(
  searchParams: Record<string, string | string[] | undefined>,
  setSearchParams: (
    p: Record<string, string | undefined>,
    opts?: { replace?: boolean },
  ) => void,
  key: string,
  get: () => string,
  set: (v: string) => void,
): void {
  // URL → state
  createEffect(
    on(
      () => {
        const v = searchParams[key];
        return typeof v === 'string' ? v : '';
      },
      (v) => {
        if (v !== get()) set(v);
      },
    ),
  );
  // state → URL
  createEffect(
    on(get, (v) => {
      const cur = searchParams[key];
      const curStr = typeof cur === 'string' ? cur : '';
      if (v !== curStr) {
        setSearchParams({ [key]: v || undefined }, { replace: true });
      }
    }),
  );
}
