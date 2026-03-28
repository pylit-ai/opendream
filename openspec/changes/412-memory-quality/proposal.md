# Change: Upgrade retrieval and consolidation quality

## Why
Even with dream ingestion, the repo does not deserve a release label if retrieval remains shallow and consolidation still misses paraphrases, duplicates, and contradictions.

## What Changes
- add hybrid retrieval and structured explanations
- add candidate clustering, dedupe, and contradiction states
- add quarantine handling for low-confidence signal
- add deterministic memory-quality eval fixtures and CLI

## Impact
- Affected specs: `412-memory-quality`
- Affected code: `opendream/retriever.py`, `opendream/consolidator.py`, `tests/`, `README.md`
