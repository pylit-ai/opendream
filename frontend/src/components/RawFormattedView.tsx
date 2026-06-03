import { Show, createMemo, createSignal, type JSX } from 'solid-js';
import { Code, FileText } from 'lucide-solid';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { cn } from '~/lib/cn';

export type RawFormattedLanguage = 'markdown' | 'json' | 'text' | 'auto';

export interface RawFormattedViewProps {
  content: string | null | undefined;
  language?: RawFormattedLanguage;
  /** localStorage key for persisting view mode preference. */
  storageKey?: string;
  /** Default mode if no persisted preference. */
  defaultMode?: 'formatted' | 'raw';
  class?: string;
  /** Optional label shown in the header bar. */
  label?: string;
}

type Mode = 'formatted' | 'raw';

const VIEW_PREFIX = 'opendream:viewmode:';

function readMode(key: string | undefined, fallback: Mode): Mode {
  if (!key) return fallback;
  try {
    const v = localStorage.getItem(VIEW_PREFIX + key);
    return v === 'raw' || v === 'formatted' ? v : fallback;
  } catch {
    return fallback;
  }
}

function writeMode(key: string | undefined, mode: Mode): void {
  if (!key) return;
  try {
    localStorage.setItem(VIEW_PREFIX + key, mode);
  } catch {
    /* ignore */
  }
}

function detectLanguage(s: string): Exclude<RawFormattedLanguage, 'auto'> {
  const t = s.trim();
  if (!t) return 'text';
  if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))) {
    try {
      JSON.parse(t);
      return 'json';
    } catch {
      /* fall-through */
    }
  }
  // Markdown signals: heading, bold, list, code-fence
  if (/(^|\n)\s*#{1,6}\s/.test(t)) return 'markdown';
  if (/```/.test(t)) return 'markdown';
  if (/(^|\n)\s*[-*+]\s+/.test(t)) return 'markdown';
  if (/\*\*[^*]+\*\*/.test(t)) return 'markdown';
  return 'text';
}

function highlightJson(value: unknown): string {
  let pretty: string;
  try {
    pretty =
      typeof value === 'string' ? JSON.stringify(JSON.parse(value), null, 2) : JSON.stringify(value, null, 2);
  } catch {
    pretty = typeof value === 'string' ? value : String(value);
  }
  // Escape HTML first.
  const escaped = pretty
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // Tokenize: keys, strings, numbers, booleans, null.
  return escaped.replace(
    /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'text-warn'; // numbers
      if (/^"/.test(match)) {
        cls = /:\s*$/.test(match) ? 'text-accent' : 'text-success';
      } else if (/true|false/.test(match)) {
        cls = 'text-danger';
      } else if (match === 'null') {
        cls = 'text-text-subtle';
      }
      return `<span class="${cls}">${match}</span>`;
    },
  );
}

function renderMarkdown(src: string): string {
  const html = marked.parse(src, { async: false, breaks: true, gfm: true }) as string;
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

export function RawFormattedView(props: RawFormattedViewProps): JSX.Element {
  const initialMode: Mode = readMode(props.storageKey, props.defaultMode ?? 'formatted');
  const [mode, setMode] = createSignal<Mode>(initialMode);

  const text = (): string => {
    const c = props.content;
    if (c == null) return '';
    return typeof c === 'string' ? c : String(c);
  };

  const lang = createMemo<Exclude<RawFormattedLanguage, 'auto'>>(() => {
    const explicit = props.language ?? 'auto';
    if (explicit !== 'auto') return explicit;
    return detectLanguage(text());
  });

  const setModePersist = (m: Mode): void => {
    setMode(m);
    writeMode(props.storageKey, m);
  };

  return (
    <div
      class={cn(
        'flex flex-col rounded-md hairline bg-surface-elevated/40 overflow-hidden',
        props.class,
      )}
    >
      <header class="flex items-center justify-between gap-2 px-2.5 py-1.5 hairline-b">
        <span class="text-[10px] uppercase tracking-[0.08em] text-text-subtle">
          {props.label ?? lang()}
        </span>
        <div role="group" class="inline-flex items-center rounded-md bg-surface p-0.5 hairline">
          <button
            type="button"
            aria-label="Formatted view"
            aria-pressed={mode() === 'formatted'}
            onClick={() => setModePersist('formatted')}
            class={cn(
              'flex h-5 items-center gap-1 rounded px-1.5 text-[10.5px] text-text-subtle transition-colors hover:text-text',
              mode() === 'formatted' && 'bg-surface-elevated text-text',
            )}
          >
            <FileText size={11} />
            <span>Formatted</span>
          </button>
          <button
            type="button"
            aria-label="Raw view"
            aria-pressed={mode() === 'raw'}
            onClick={() => setModePersist('raw')}
            class={cn(
              'flex h-5 items-center gap-1 rounded px-1.5 text-[10.5px] text-text-subtle transition-colors hover:text-text',
              mode() === 'raw' && 'bg-surface-elevated text-text',
            )}
          >
            <Code size={11} />
            <span>Raw</span>
          </button>
        </div>
      </header>
      <div class="overflow-x-auto p-3">
        <Show
          when={mode() === 'formatted'}
          fallback={
            <pre class="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-text">
              {text()}
            </pre>
          }
        >
          <Show when={lang() === 'markdown'}>
            <div
              class="prose prose-sm max-w-none dark:prose-invert prose-pre:bg-surface prose-pre:hairline"
              // eslint-disable-next-line solid/no-innerhtml
              innerHTML={renderMarkdown(text())}
            />
          </Show>
          <Show when={lang() === 'json'}>
            <pre class="overflow-x-auto whitespace-pre font-mono text-[11.5px] leading-relaxed text-text">
              {/* eslint-disable-next-line solid/no-innerhtml */}
              <code class="language-json" innerHTML={highlightJson(text())} />
            </pre>
          </Show>
          <Show when={lang() === 'text'}>
            <pre class="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-text">
              {text()}
            </pre>
          </Show>
        </Show>
      </div>
    </div>
  );
}
