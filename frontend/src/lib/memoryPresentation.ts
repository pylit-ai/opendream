import type { ChipVariant } from '~/components/Chip';

const PREFIX_BY_TYPE: Record<string, string> = {
  semantic_fact: 'Fact',
  project_decision: 'Decision',
  environment_requirement: 'Requirement',
  pending_item: 'Pending',
};

const PREFIXES = Object.values(PREFIX_BY_TYPE);

export interface MemoryTypePresentation {
  label: string;
  variant: ChipVariant;
}

function titleCase(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function memoryTypePresentation(type: string | undefined): MemoryTypePresentation {
  const raw = (type ?? '').trim();
  const key = raw.toLowerCase();
  if (key === 'semantic_fact') return { label: 'Fact', variant: 'accent' };
  if (key === 'project_decision') return { label: 'Decision', variant: 'ok' };
  if (key === 'environment_requirement') return { label: 'Requirement', variant: 'warn' };
  if (key === 'pending_item') return { label: 'Pending', variant: 'warn' };
  if (key.includes('decision')) return { label: titleCase(raw), variant: 'ok' };
  if (key.includes('fact')) return { label: titleCase(raw), variant: 'accent' };
  if (key.includes('requirement')) return { label: titleCase(raw), variant: 'warn' };
  return { label: raw ? titleCase(raw) : 'Unknown', variant: 'neutral' };
}

export function stripMemoryPrefix(value: string | undefined, type?: string): string | undefined {
  if (value == null) return undefined;
  const text = value.trim();
  if (!text) return text;

  const orderedPrefixes = [
    ...(type ? [PREFIX_BY_TYPE[type.toLowerCase()]].filter(Boolean) : []),
    ...PREFIXES,
  ];
  for (const prefix of orderedPrefixes) {
    const re = new RegExp(`^${prefix}:\\s*`, 'i');
    if (re.test(text)) return text.replace(re, '').trim();
  }
  return text;
}

export function memoryPreview(
  title: string | undefined,
  summary: string | undefined,
  type?: string,
): string | undefined {
  const cleanTitle = stripMemoryPrefix(title, type);
  const cleanSummary = stripMemoryPrefix(summary, type);
  return cleanTitle || cleanSummary;
}
