# Dream Narrative Templates

OpenDream dream narratives are deterministic in v1. They summarize the run record already persisted in dream audit JSON; no LLM call is made.

## Inputs

- `status`, `reason`, `mode`
- deterministic signal counts: `gathered_rows`, `appended_events`
- semantic funnel counts: `proposals_generated`, `proposals_approved`, `proposals_rejected`, `learned_context_created`

## Template Order

1. Skipped cycles explain the operator-facing reason first: no transcripts, insufficient signal, no backlog, minimum interval, or lock held.
2. Failed cycles point to the failure reason and audit artifacts.
3. Semantic/hybrid cycles summarize proposal generation, approval, rejection, and learned-context creation.
4. Deterministic cycles summarize transcript rows gathered, events staged, and maintenance.
5. Empty successful cycles state that no proposal or event changes were made.

Future LLM-backed summaries must preserve these fields as auditable source data and remain optional.
