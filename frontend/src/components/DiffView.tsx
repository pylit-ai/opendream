import { For, Show, createMemo, type JSX } from 'solid-js';
import { diffLines, parsePatch, applyPatch } from 'diff';
import { cn } from '~/lib/cn';

export interface DiffViewProps {
  before?: string | object | null;
  after?: string | object | null;
  /** Pre-formatted unified patch text (overrides before/after). */
  patch?: string | null;
  language?: 'json' | 'text';
  class?: string;
  emptyLabel?: string;
}

interface Row {
  kind: 'add' | 'del' | 'ctx' | 'hunk';
  text: string;
  beforeLine?: number;
  afterLine?: number;
}

function stringify(value: unknown, language: 'json' | 'text'): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (language === 'json') {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function rowsFromPair(before: string, after: string): Row[] {
  const parts = diffLines(before, after);
  const out: Row[] = [];
  let bLine = 1;
  let aLine = 1;
  for (const part of parts) {
    const lines = part.value.replace(/\n$/, '').split('\n');
    if (part.value === '') continue;
    if (part.added) {
      for (const t of lines) {
        out.push({ kind: 'add', text: t, afterLine: aLine++ });
      }
    } else if (part.removed) {
      for (const t of lines) {
        out.push({ kind: 'del', text: t, beforeLine: bLine++ });
      }
    } else {
      for (const t of lines) {
        out.push({ kind: 'ctx', text: t, beforeLine: bLine++, afterLine: aLine++ });
      }
    }
  }
  return out;
}

function rowsFromPatch(patch: string): Row[] {
  const out: Row[] = [];
  // Try structured parse for line numbers, fall back to raw scan.
  try {
    const parsed = parsePatch(patch);
    for (const file of parsed) {
      for (const hunk of file.hunks ?? []) {
        out.push({
          kind: 'hunk',
          text: `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`,
        });
        let bLine = hunk.oldStart;
        let aLine = hunk.newStart;
        for (const line of hunk.lines) {
          const tag = line[0];
          const text = line.slice(1);
          if (tag === '+') out.push({ kind: 'add', text, afterLine: aLine++ });
          else if (tag === '-') out.push({ kind: 'del', text, beforeLine: bLine++ });
          else if (tag === ' ' || tag === undefined)
            out.push({ kind: 'ctx', text, beforeLine: bLine++, afterLine: aLine++ });
        }
      }
    }
  } catch {
    for (const raw of patch.split('\n')) {
      if (raw.startsWith('@@')) out.push({ kind: 'hunk', text: raw });
      else if (raw.startsWith('+') && !raw.startsWith('+++'))
        out.push({ kind: 'add', text: raw.slice(1) });
      else if (raw.startsWith('-') && !raw.startsWith('---'))
        out.push({ kind: 'del', text: raw.slice(1) });
      else if (raw.startsWith('---') || raw.startsWith('+++')) continue;
      else out.push({ kind: 'ctx', text: raw });
    }
  }
  return out;
}

export function DiffView(props: DiffViewProps): JSX.Element {
  const rows = createMemo<Row[]>(() => {
    if (props.patch && props.patch.trim().length > 0) {
      return rowsFromPatch(props.patch);
    }
    const lang = props.language ?? 'text';
    const b = stringify(props.before, lang);
    const a = stringify(props.after, lang);
    if (!b && !a) return [];
    return rowsFromPair(b, a);
  });

  const empty = () => rows().length === 0;
  // Detect "all context" — patch with no add/del means nothing actually changed.
  const noChanges = () =>
    rows().length > 0 && rows().every((r) => r.kind === 'ctx' || r.kind === 'hunk');

  return (
    <div
      class={cn(
        'overflow-x-auto rounded-md hairline bg-surface-elevated font-mono tabular-nums',
        props.class,
      )}
      style={{ 'font-size': '12px', 'line-height': '1.55' }}
    >
      <Show
        when={!empty() && !noChanges()}
        fallback={
          <div class="px-3 py-2 text-[12px] text-text-subtle">
            {props.emptyLabel ?? (empty() ? 'No diff available' : 'No changes')}
          </div>
        }
      >
        <table class="w-full border-collapse">
          <tbody>
            <For each={rows()}>
              {(row) => {
                if (row.kind === 'hunk') {
                  return (
                    <tr>
                      <td
                        colspan={3}
                        class="bg-[color-mix(in_oklab,rgb(var(--c-text-muted))_8%,transparent)] px-3 py-0.5 text-[11px] text-text-subtle"
                      >
                        {row.text}
                      </td>
                    </tr>
                  );
                }
                const sign =
                  row.kind === 'add' ? '+' : row.kind === 'del' ? '−' : ' ';
                const bg =
                  row.kind === 'add'
                    ? 'bg-[color-mix(in_oklab,rgb(var(--c-success))_12%,transparent)]'
                    : row.kind === 'del'
                      ? 'bg-[color-mix(in_oklab,rgb(var(--c-danger))_12%,transparent)]'
                      : '';
                const accent =
                  row.kind === 'add'
                    ? 'border-l-2 border-success/60 text-success'
                    : row.kind === 'del'
                      ? 'border-l-2 border-danger/60 text-danger'
                      : 'border-l-2 border-transparent text-text';
                return (
                  <tr class={bg}>
                    <td
                      class="select-none px-1.5 text-right text-[10.5px] text-text-subtle"
                      style={{ 'min-width': '34px', width: '34px' }}
                    >
                      {row.beforeLine ?? ''}
                    </td>
                    <td
                      class="select-none px-1.5 text-right text-[10.5px] text-text-subtle"
                      style={{ 'min-width': '34px', width: '34px' }}
                    >
                      {row.afterLine ?? ''}
                    </td>
                    <td class={cn('max-w-0 whitespace-pre-wrap break-words pl-2 pr-3', accent)}>
                      <span class="select-none pr-2 text-text-subtle">{sign}</span>
                      {row.text}
                    </td>
                  </tr>
                );
              }}
            </For>
          </tbody>
        </table>
      </Show>
    </div>
  );
}

// Re-export for callers who need a quick patch-application sanity check.
export { applyPatch };
