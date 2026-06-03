// Module-level fetch cache with TTL. Survives route navigation.
// Used to avoid refetching list/detail data the user just viewed.

interface Entry<T> {
  v: T;
  e: number;
}

const cache = new Map<string, Entry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();

// Stale-while-revalidate window. After TTL expires, the cached value remains
// returnable for STALE_WINDOW_MS while a background refetch refreshes it.
const STALE_WINDOW_MS = 5 * 60_000;

export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs = 30_000,
): Promise<T> {
  const now = Date.now();
  const hit = cache.get(key) as Entry<T> | undefined;
  if (hit) {
    if (hit.e > now) return hit.v;
    // Within stale window: return stale, refresh in background.
    if (hit.e + STALE_WINDOW_MS > now) {
      if (!inflight.has(key)) {
        const refresh = (async () => {
          try {
            const v = await fetcher();
            cache.set(key, { v, e: Date.now() + ttlMs });
            return v;
          } finally {
            inflight.delete(key);
          }
        })();
        inflight.set(key, refresh);
        refresh.catch(() => undefined);
      }
      return hit.v;
    }
  }
  const pending = inflight.get(key) as Promise<T> | undefined;
  if (pending) return pending;
  const p = (async () => {
    try {
      const v = await fetcher();
      cache.set(key, { v, e: Date.now() + ttlMs });
      return v;
    } finally {
      inflight.delete(key);
    }
  })();
  inflight.set(key, p);
  return p;
}

export function invalidate(prefix: string): void {
  for (const k of Array.from(cache.keys())) {
    if (k.startsWith(prefix)) cache.delete(k);
  }
}

export function prefetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs = 30_000,
): void {
  // Fire and forget; ignore errors so hover doesn't surface noise.
  cachedFetch(key, fetcher, ttlMs).catch(() => undefined);
}

export function peek<T>(key: string): T | undefined {
  const hit = cache.get(key) as Entry<T> | undefined;
  if (!hit) return undefined;
  if (hit.e <= Date.now()) return undefined;
  return hit.v;
}
