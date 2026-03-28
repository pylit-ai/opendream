# 430-sota-dream-runtime-bundle

## Why
The shipped OpenDream runtime already covers transcript-native dreaming, layered stores, retrieval, review tooling, observability, fidelity evals, and release gates. The remaining blocker from the March 28, 2026 runtime note is operational: dream consolidation decisions are not yet emitted as explicit plan or verifier artifacts, and the repo still lacks a first-party durable worker queue for unattended dream processing.

## Goal
Add explicit planner and verifier contracts plus a local queue-backed dream worker while reusing the repo’s existing retrieval, governance, and release surfaces.

## Non-goals
- hosted daemons
- default remote model integrations
- replacing the existing observability UI
- changing the durable memory file format

## Success criteria
- every consolidation run emits a validated plan and verifier report
- queued dream jobs survive restarts and drain safely
- adapter examples and release smoke expose the worker path
- no retrieval or fidelity regressions escape `make verify`
