const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const NUMBER_FMT = new Intl.NumberFormat('en-US');

function toDate(input: string | number | Date): Date | null {
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input;
  if (input == null || input === '') return null;
  const d = new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function formatTime12(d: Date): string {
  let hours = d.getHours();
  const mins = d.getMinutes();
  const ampm = hours >= 12 ? 'pm' : 'am';
  hours = hours % 12 || 12;
  return `${hours}:${pad2(mins)}${ampm}`;
}

export function formatDate(input: string | number | Date): string {
  const d = toDate(input);
  if (!d) return '';
  const now = new Date();
  const sameYear = d.getFullYear() === now.getFullYear();
  const month = MONTHS[d.getMonth()] ?? '';
  const day = d.getDate();
  const time = formatTime12(d);
  if (sameYear) return `${month} ${day} ${time}`;
  return `${month} ${day}, ${d.getFullYear()}`;
}

export function formatDateLong(input: string | number | Date): string {
  const d = toDate(input);
  if (!d) return '';
  return d.toISOString().replace('T', ' ').replace('Z', ' UTC');
}

/**
 * Locale-aware integer formatting (1234 -> "1,234").
 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return NUMBER_FMT.format(value);
}

/**
 * Humane duration: 450ms, 3.2s, 1m 12s, 1h 04m.
 * Accepts milliseconds.
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return s < 10 ? `${s.toFixed(1)}s` : `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const remS = Math.round(s - m * 60);
  if (m < 60) return `${m}m ${pad2(remS)}s`;
  const h = Math.floor(m / 60);
  const remM = m - h * 60;
  return `${h}h ${pad2(remM)}m`;
}

/**
 * Truncate a long path keeping head and tail: ~/src/foo/bar/baz -> ~/src/…/baz.
 */
export function truncateMiddle(value: string, max = 48): string {
  if (!value || value.length <= max) return value;
  const segs = value.split('/');
  if (segs.length <= 3) {
    const keep = Math.max(8, Math.floor((max - 1) / 2));
    return `${value.slice(0, keep)}…${value.slice(-keep)}`;
  }
  const head = segs.slice(0, 2).join('/');
  const tail = segs.slice(-2).join('/');
  const candidate = `${head}/…/${tail}`;
  if (candidate.length <= max) return candidate;
  return `…/${tail}`;
}
