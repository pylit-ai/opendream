# Verification Steps

## 1. Schema validation
Validate all runtime JSON against declared schemas.

Expected:
- 100% valid objects
- no undocumented fields

## 2. Golden deterministic run
Use a fixed fixture with:
- 3 sessions
- 20 events
- 5 preferences
- 3 project decisions
- 2 contradictions
- 1 repeated workflow

Run extractor + consolidator twice.

Expected:
- deterministic durable state
- deterministic startup index
- no duplicate durable writes on second run

## 3. Bootstrap verification
Use a messy historical corpus.

Expected:
- category inventory produced
- raw evidence preserved
- apply step bounded and auditable
- low-confidence items not promoted directly

## 4. Conflict verification
Inject mixed-provenance contradictions.

Expected:
- stronger supported record active
- weaker ambiguous record contested or superseded
- contested excluded from startup index

## 5. Retrieval trace verification
Run representative coding prompts.

Expected:
- every selected memory has a retrieval reason and score
- irrelevant recall remains under threshold

## 6. Concurrency verification
Simulate overlapping remember requests plus background consolidate.

Expected:
- exactly one active lock holder
- no malformed files
- no lost remember requests

## 7. No-code-write verification
Diff repo before and after consolidation.

Expected:
- only memory store paths changed

## 8. Decay verification
Seed stale low-confidence pending items.

Expected:
- quarantined or absent from startup index
- durable high-value items preserved

## 9. Outcome verification
Benchmark recurring coding tasks with:
- no memory
- append-only memory
- full system

Expected:
- full system outperforms append-only on repeated tasks

## 10. License-clean verification
Review:
- dependency tree
- vendored files
- prompt files
- comments/docstrings for copied material

Expected:
- no required code reuse from reviewed repos
- no copied prompt text required for runtime behavior
