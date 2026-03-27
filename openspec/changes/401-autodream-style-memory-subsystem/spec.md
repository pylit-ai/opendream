# OpenSpec: AutoDream-Style Memory Subsystem for Coding Agents

## Status
Proposed

## Owner
Memory Platform / Agent Runtime

## Summary
Build a framework-agnostic memory subsystem for coding agents that:
1. captures durable signals as immutable events,
2. extracts typed candidate memories conservatively,
3. consolidates them in a background worker,
4. maintains a compact startup memory index plus topic files,
5. handles contradiction, supersession, decay, and quarantine explicitly,
6. retrieves only the minimum relevant durable memory for future tasks,
7. exposes full observability and diff-based audit trails.

## Why this exists
Transcript replay does not scale.
Append-only note dumping does not scale.
Naive summarization degrades over time.

Long-lived coding agents need:
- continuity across sessions,
- bounded startup context,
- durable user/project preferences,
- persistent environment/tooling constraints,
- reusable procedural workflows,
- and explicit handling for stale or contradictory memory.

## Goals
- keep startup memory compact and deterministic
- support async background consolidation
- separate semantic, procedural, and preference memory
- preserve provenance on all durable mutations
- allow manual inspection and editing of memory
- remain implementation-agnostic across OpenClaw/Codex-style runtimes

## Non-goals
- exact reverse-engineered parity with any closed implementation
- storing all transcript content durably
- automatic code rewriting during consolidation
- hidden or unaudited memory mutation
- mandatory DB backend in v1

## Normative implementation stance
This system MUST be implemented clean-room.
It MUST NOT depend on copied code, prompts, or templates from external repos unless that reuse is separately reviewed and approved.

## Two operating modes

### Mode A: Bootstrap
Bootstrap is the first-time migration path for messy historical memory.

Purpose:
- inventory existing raw memory corpus
- identify candidate categories
- create initial typed durable memory
- generate the first compact startup index
- avoid large destructive rewrites to raw source material

Bootstrap is slow, bounded, review-friendly, and explicitly staged.

### Mode B: Scheduled Consolidation
Scheduled mode is the recurring maintenance path.

Purpose:
- process only new candidate evidence
- update durable memory incrementally
- reindex compact startup memory
- decay, quarantine, and supersede stale items
- stay non-blocking relative to foreground agent work

## Architecture

### A. Event Capture
Write append-only events to WAL.
Capture:
- explicit remember requests
- user corrections
- project decisions
- environment requirements
- debugging outcomes
- workflow steps
- anti-patterns
- pending items
- contradiction signals
- task outcomes

Events are evidence, not durable memory.

### B. Candidate Extraction
A lightweight post-turn extractor proposes typed memory candidates.
Extractor does not mutate durable memory.
Weak evidence should be dropped or quarantined rather than promoted.

### C. Bootstrap Indexer
A bootstrap-only component scans historical memory and transcript evidence in bounded batches.
It proposes topic-grouped candidate sets before any durable apply step.

### D. Consolidator
Background worker that:
- merges compatible candidates,
- updates or creates durable records,
- marks contested or superseded records,
- applies decay/quarantine,
- regenerates startup index,
- emits diffs and run summaries.

### E. Retriever
At session start:
- loads compact startup index only

At task time:
- retrieves minimal durable records by scope, type, lexical match, embedding score, recency, and access utility

### F. Observability
Every durable write must emit:
- diff artifact
- operation trace
- source event references
- run summary

Every retrieval should optionally emit:
- selected memory ids
- retrieval reasons
- scores

## Storage model

### Filesystem mode (default)
memory/
  MEMORY.md
  topics/
    *.md
  state/
    events/
      *.jsonl
    candidates/
      *.jsonl
  audit/
    consolidation/
      *.jsonl
    retrieval/
      *.jsonl
  locks/
    consolidator.lock

### Optional DB-backed mode
Canonical storage in SQLite or Postgres, with generated markdown exports:
- `MEMORY.md`
- topic markdown files
- audit logs

## Memory classes
1. semantic_fact
2. procedural_workflow
3. user_preference
4. project_decision
5. environment_requirement
6. anti_pattern
7. pending_item
8. contested_fact
9. superseded_record

## Hard requirements
- R1: durable memory mutations must preserve provenance
- R2: startup index must remain compact
- R3: topic details must be lazily loadable
- R4: consolidation must be single-writer
- R5: contradictions must not be silently overwritten
- R6: extractor and consolidator must be separate stages
- R7: bootstrap and scheduled modes must be separate
- R8: procedural workflows must be stored separately from semantic facts
- R9: consolidator may write only inside memory store paths
- R10: every durable mutation must produce an audit diff
- R11: contested records must be excluded from startup index by default
- R12: stale low-confidence memory must decay or quarantine
- R13: user-editable markdown representation must exist
- R14: no external repo code is required to implement the system

## Retrieval policy
At startup:
- load `MEMORY.md` only

At task time:
- retrieve by:
  - scope match
  - type boost
  - lexical relevance
  - embedding relevance (optional)
  - recency
  - salience
  - successful prior retrieval count

For coding tasks, boost:
- project_decision
- environment_requirement
- procedural_workflow
- anti_pattern
- relevant user_preference
- recent pending_item

## Contradiction policy
When evidence conflicts:
1. prefer stronger provenance over recency alone
2. if unresolved, mark contested
3. if later evidence clearly replaces prior durable memory, mark superseded
4. preserve explicit linkages:
   - `conflicts_with`
   - `supersedes`
5. exclude contested items from startup index

## Decay policy
- pending_item decays fast
- low-confidence one-off facts decay fast
- user_preference decays slowly unless contradicted
- project_decision persists until superseded
- procedural_workflow is promoted when repeatedly successful

## Security policy
- consolidator has read-only access to repo/code
- consolidator write access is restricted to memory store
- secrets are never promoted unless explicitly allowlisted
- no cross-machine sync by default
- no unaudited remote persistence by default

## Success criteria
- startup memory stays bounded
- retrieval quality improves over append-only baseline
- repeated-task success improves with procedural memory
- no silent overwrite under concurrent conditions
- every durable mutation is explainable from source evidence
