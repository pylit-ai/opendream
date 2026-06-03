// Truncate-middle helper for opaque IDs. Keeps prefix + last 4 hex chars.
// e.g. mem_a3f4b7c8d2e1 → mem_a3f4…d2e1

export function shortId(id: string | null | undefined, keep = 4): string {
  if (!id) return '—';
  const m = id.match(/^([a-zA-Z]+_)([a-f0-9]+)$/);
  if (m) {
    const [, prefix, hex] = m;
    if ((hex ?? '').length > keep + 4) {
      return `${prefix}${hex!.slice(0, keep)}…${hex!.slice(-keep)}`;
    }
    return id;
  }
  if (id.length > keep * 2 + 1) {
    return `${id.slice(0, keep)}…${id.slice(-keep)}`;
  }
  return id;
}
