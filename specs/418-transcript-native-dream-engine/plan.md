# plan.md — 418-transcript-native-dream-engine

## Summary
Promote the DreamRunner from a useful feature to the canonical runtime path. Reuse the existing local-first memory engine, but make transcript backlog polling, explicit dream status, and bounded transcript-search reporting first-class and inspectable.

## Architecture impact
- touched components:
  - `opendream.dream`
  - `opendream.episodes`
  - `opendream.storage`
  - `opendream.cli`
  - `tests/test_memory_cli.py`
  - `README.md`
- unchanged components:
  - core durable-record schema
  - observability API and web app surfaces outside dream-state enrichment

## Data model / contract changes
- extend `dream_state.json` with last run summary, reason, duration, and last episode timestamp
- add default transcript directory support under `memory/state/transcripts/`
- enrich dream audit summaries with bounded-search metadata and searched file lists

## Interfaces
- input: `opendream dream run|status|tick`
- output: durable memory, compat views, dream audit summaries, and explicit scheduler-safe skip reasons

## Observability
- dream summaries expose phases, duration, trigger class, and searched transcript files
- dream status exposes backlog-adjacent metadata without reading raw JSON state files

## Security / safety review
- auth changes: none
- secret handling: transcript-derived memory still flows through the same extraction and consolidation filters
- irreversible actions: none

## Rollout
1. add transcript backlog helpers and richer dream status state
2. expose `dream status` and `dream tick`
3. record bounded-search metadata in dream summaries
4. update docs and targeted integration tests

## Rollback
1. remove nested dream status or tick aliases
2. revert to the previous dream-state payload if the richer summary contract becomes unstable

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `make verify`
- manual checks:
  - run `opendream dream run --workspace <path> --episodes <jsonl>`
  - run `opendream dream status --workspace <path>`
  - run `opendream dream tick --workspace <path>` with transcript files in `memory/state/transcripts/`

## ADR needed?
- no
