# spec.md — 411-autodream-fidelity

## Title
Match the observable AutoDream execution model with transcript-guided dreaming

## Why
OpenDream currently behaves like an event-driven memory kernel, not a reflective DreamRunner. This change adds transcript and log ingestion, a four-phase dream lifecycle, explicit dream status, and path-safe compatibility behavior so the implementation matches the public AutoDream shape more closely.

## In scope
- DreamRunner with `orient`, `gather_recent_signal`, `consolidate`, and `prune_and_reindex`
- transcript and log episode ingestion alongside existing events
- relative-date normalization to absolute timestamps
- dream status persistence and manual trigger surface
- scheduler config for dream thresholds
- configurable memory directory support that dream and normal writes both honor
- compatibility views for `MEMORY.md`, `project.md`, and `user.md`

## Out of scope
- hosted background daemons
- remote transcript services
- full-text replay of arbitrary corpora on every run

## User-visible behavior
- Operators can run `opendream-memory dream run` against transcript-only inputs and get durable memory.
- `status` exposes dream state and last dream run information.
- `MEMORY.md` stays lean while detail expands into topic files and optional compat views.

## Acceptance criteria
- [ ] AC-1: a transcript-only fixture with no structured event emission still produces durable memory after a dream run
- [ ] AC-2: relative transcript dates are normalized to absolute dates in stored durable memory
- [ ] AC-3: `MEMORY.md` stays within the configured index budget while topic/detail files grow
- [ ] AC-4: dream status transitions between `never_ran`, `idle`, and `dreaming` with `last_ran_at`
- [ ] AC-5: a configured custom memory directory is honored by normal writes and dream writes
- [ ] AC-6: simultaneous dream runs do not corrupt state

## Edge cases
- transcript sources outside the workspace
- custom memory directories
- repeated dream runs with no new episode signal
- stale locks from interrupted dream runs

## Required verifiers
- unit tests: yes, date normalization and dream state handling
- integration tests: yes, transcript-only dream flow and custom-path flow
- evals / scenario checks: no
- manual verification: yes, run `opendream-memory dream run` on fixture transcripts

## Risks
- dream scanning can become expensive if narrowing is not bounded
- compatibility views can drift if not generated from the same canonical durable records

## Links
- `../../README.md`
- `../../specs/406-scheduler-and-status-surface/spec.md`
