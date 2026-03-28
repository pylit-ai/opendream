# spec.md — 418-transcript-native-dream-engine

## Title
Make the transcript-native DreamRunner the canonical memory-maintenance path

## Why
The thin integration layer in `403-runtime-integration-layer` and the first DreamRunner pass in `411-autodream-fidelity` proved the runtime could ingest transcripts, but they did not fully establish the public runtime contract. OpenDream now needs one canonical spec that says the main act is transcript-native dreaming with explicit phases, bounded transcript search reporting, scheduler-safe status or tick surfaces, and memory-only writes.

## In scope
- transcript-first DreamRunner execution from explicit episode paths or the workspace transcript directory
- explicit four-phase lifecycle: `orient`, `gather_recent_signal`, `consolidate`, `prune_and_reindex`
- `dream run`, `dream status`, and `dream tick`
- relative-date normalization during transcript ingestion
- bounded transcript-tail search reporting with inspected files and `full_corpus_replay: false`
- richer dream status state including `last_run_summary`, `last_run_reason`, `last_run_duration_ms`, and `last_episode_timestamp`
- compatibility views for `MEMORY.md`, `project.md`, and `user.md`
- lock-safe, memory-only writes under the configured memory directory

## Out of scope
- hosted daemons or remote transcript services
- product-code mutation by the DreamRunner
- whole-corpus replay on every run
- exact reproduction of private Anthropic heuristics

## User-visible behavior
- `opendream-memory dream run` can create durable memory from transcript-only inputs.
- `opendream-memory dream status` exposes `never_ran`, `dreaming`, and `idle` plus the last run summary.
- `opendream-memory dream tick` can poll a transcript backlog safely and skip with explicit reasons when nothing new should run.
- `MEMORY.md` stays lean while topic files and compat views hold the detail.

## Acceptance criteria
- [x] AC-1: a transcript-only fixture with no structured `emit-event` usage still produces durable memory after `opendream-memory dream run`
- [x] AC-2: dream runs emit the explicit four-phase lifecycle in their machine-readable summary
- [x] AC-3: transcript relative dates are normalized to absolute dates in durable memory
- [x] AC-4: `dream status` exposes `last_run_summary`, `last_run_reason`, `last_run_duration_ms`, and `last_episode_timestamp`
- [x] AC-5: `dream tick` runs from transcript backlog and skips cleanly on `min-interval` or `no-backlog`
- [x] AC-6: dream summaries report searched transcript files and set `full_corpus_replay` to `false`
- [x] AC-7: custom memory directories are honored by dream writes and compat views
- [x] AC-8: concurrent dream runs do not corrupt state and writes remain confined to the memory subtree

## Edge cases
- transcript fixtures arriving via the default `memory/state/transcripts/` directory
- repeated dream ticks with no new transcript evidence
- stale dream locks from interrupted runs
- compat-mode runs in a non-default memory directory

## Required verifiers
- unit tests: yes, date normalization and dream-state persistence
- integration tests: yes, transcript-only dream flow, `dream status`, `dream tick`, custom-path flow, and lock behavior
- evals / scenario checks: yes, `opendream-memory eval dream-fidelity`
- manual verification: yes, run `dream run`, `dream status`, and `dream tick` against transcript fixtures

## Risks
- bounded tail search can still miss relevant older transcript rows if operators never rerun with broader inputs
- a richer dream status surface can drift if summaries are not written from the same runtime result

## Links
- `../403-runtime-integration-layer/spec.md`
- `../411-autodream-fidelity/spec.md`
- `../../README.md`
