export interface GlossaryEntry {
  key: string;
  label: string;
  help: string;
}

export const RUN_KIND_GLOSSARY: GlossaryEntry[] = [
  {
    key: 'consolidation',
    label: 'Consolidation',
    help: 'Background memory maintenance: turns raw events and candidates into durable memory. It is normal for this to outnumber dream cycles.',
  },
  {
    key: 'dream',
    label: 'Dream',
    help: 'A transcript/native dream cycle. It reads episodes or transcripts and may append new memory events.',
  },
  {
    key: 'semantic_dream',
    label: 'Semantic dream',
    help: 'A learned-context dream cycle that synthesizes or updates semantic context.',
  },
  {
    key: 'automation',
    label: 'Automation projection',
    help: 'A scheduled or manual projection job. It reads durable memory and writes typed automation records; it does not replace canonical memory.',
  },
  {
    key: 'run',
    label: 'Run',
    help: 'Generic runtime audit entry when a more specific kind is not available.',
  },
];

export const MEMORY_STATUS_GLOSSARY: GlossaryEntry[] = [
  {
    key: 'active',
    label: 'Active',
    help: 'Trusted durable memory. Retrieval can use it normally.',
  },
  {
    key: 'contested',
    label: 'Contested',
    help: 'Conflicting evidence exists. Keep visible for review instead of silently trusting either side.',
  },
  {
    key: 'superseded',
    label: 'Superseded',
    help: 'Replaced by a newer or stronger memory, but retained for history.',
  },
  {
    key: 'learned',
    label: 'Learned',
    help: 'Per-context learned item the runtime is still trying out.',
  },
  {
    key: 'pruned',
    label: 'Pruned',
    help: 'Removed during a prune cycle. Usually reversible from audit history.',
  },
  {
    key: 'rejected',
    label: 'Rejected',
    help: 'Operator-suppressed. It should not surface in retrievals.',
  },
  {
    key: 'archived',
    label: 'Archived',
    help: 'Inactive but retained for audit and forensics.',
  },
  {
    key: 'stale',
    label: 'Stale',
    help: 'No longer backed by current evidence or marked old by review.',
  },
];

export const REVIEW_QUEUE_GLOSSARY: GlossaryEntry[] = [
  {
    key: 'contested_memory',
    label: 'Contested memory',
    help: 'A memory conflicts with another memory and needs a human or auto-review decision.',
  },
  {
    key: 'low_confidence_memory',
    label: 'Low confidence memory',
    help: 'A durable memory is below the confidence threshold and may need suppression or notes.',
  },
  {
    key: 'large_diff',
    label: 'Large diff',
    help: 'A run produced an inspectable change set or warning. Review the diff before trusting the change.',
  },
  {
    key: 'failed_run',
    label: 'Failed run',
    help: 'A runtime job emitted warnings or failure evidence and should be checked.',
  },
  {
    key: 'suspicious_retrieval',
    label: 'Suspicious retrieval',
    help: 'Retrieval omitted near-threshold memories. It is a review prompt, not proof the retrieval is wrong.',
  },
];

export const MEMORY_TYPE_GLOSSARY: GlossaryEntry[] = [
  {
    key: 'project_decision',
    label: 'Project decision',
    help: 'A durable decision about how this project should be built or operated.',
  },
  {
    key: 'environment_requirement',
    label: 'Environment requirement',
    help: 'A prerequisite such as a tool, service, version, or local setup requirement.',
  },
  {
    key: 'workflow',
    label: 'Workflow',
    help: 'A repeatable procedure or ordered set of steps.',
  },
  {
    key: 'user_preference',
    label: 'User preference',
    help: 'A remembered user style, convention, or operating preference.',
  },
  {
    key: 'anti_pattern',
    label: 'Anti-pattern',
    help: 'Something the agent should avoid because prior evidence says it caused problems.',
  },
  {
    key: 'semantic_fact',
    label: 'Semantic fact',
    help: 'A general learned fact or summary that does not fit a stricter memory type.',
  },
];

export const MEMORY_TAG_GLOSSARY: GlossaryEntry[] = [
  {
    key: 'key:<topic>',
    label: 'key:<topic>',
    help: 'Clusters evidence around the same topic, such as key:package-manager.',
  },
  {
    key: 'workflow:<name>',
    label: 'workflow:<name>',
    help: 'Marks an event or memory as part of a named workflow.',
  },
  {
    key: 'conflict:<topic>',
    label: 'conflict:<topic>',
    help: 'Marks contradiction evidence for the same topic.',
  },
  {
    key: 'severity:<level>',
    label: 'severity:<level>',
    help: 'Marks risk level, such as severity:high.',
  },
  {
    key: 'anti-pattern:true',
    label: 'anti-pattern:true',
    help: 'Marks behavior or guidance that should be avoided.',
  },
  {
    key: 'success:true',
    label: 'success:true',
    help: 'Marks evidence that a workflow or task succeeded.',
  },
];

function helpFrom(entries: GlossaryEntry[], key: string | undefined, fallback: string): string {
  const normalized = String(key ?? '').trim().toLowerCase();
  return entries.find((entry) => entry.key === normalized)?.help ?? fallback;
}

function labelFrom(entries: GlossaryEntry[], key: string | undefined): string {
  const normalized = String(key ?? '').trim().toLowerCase();
  return entries.find((entry) => entry.key === normalized)?.label ?? (normalized ? normalized.replace(/_/g, ' ') : 'Unknown');
}

export function helpForRunKind(kind: string | undefined): string {
  return helpFrom(RUN_KIND_GLOSSARY, kind, RUN_KIND_GLOSSARY.find((entry) => entry.key === 'run')!.help);
}

export function helpForMemoryStatus(status: string | undefined): string {
  return helpFrom(MEMORY_STATUS_GLOSSARY, status, 'Status not recognized by this build.');
}

export function helpForReviewQueueType(type: string | undefined): string {
  return helpFrom(REVIEW_QUEUE_GLOSSARY, type, 'Review queue type not recognized by this build.');
}

export function labelForReviewQueueType(type: string | undefined): string {
  return labelFrom(REVIEW_QUEUE_GLOSSARY, type);
}

export function helpForMemoryType(type: string | undefined): string {
  return helpFrom(MEMORY_TYPE_GLOSSARY, type, 'Memory type not recognized by this build.');
}
