# Change: Match the observable AutoDream execution model

## Why
The implementation behaves more like a memory kernel than a reflective DreamRunner. The fidelity gap is operational: event-centric input, weak background semantics, missing transcript ingestion, and no explicit dream lifecycle.

## What Changes
- add transcript and log episode ingestion
- add a four-phase DreamRunner
- add date normalization and dream status state
- add compatibility views and custom memory directory support
- add reliable manual and scheduler-facing dream triggers

## Impact
- Affected specs: `411-autodream-fidelity`
- Affected code: `opendream_memory/`, `tests/`, `README.md`, `docs/architecture/overview.md`
