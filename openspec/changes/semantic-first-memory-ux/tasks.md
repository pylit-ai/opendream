# tasks.md — 443-semantic-first-memory-ux

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until CLI, API, UI, docs, and release evidence tell the same story.

## WS1 — Registration and product contract
- [x] T1: add `443-semantic-first-memory-ux` to `specs/registry.yaml` with explicit dependencies on `440` and `442`
- [x] T2: update proposal/design/plan artifacts so semantic pruning and progressive disclosure are part of the product contract, not an implementation footnote

## WS2 — Readiness and quality contracts
- [x] T3: extend status/overview/contract-export read models with semantic posture, capability state, degraded reason, and next action
- [x] T4: add machine-readable memory-quality and context-pruning report shapes or extend existing contracts accordingly
- [x] T5: add fixtures and schema validation coverage for the new contract fields

## WS3 — Progressive context assembly
- [x] T6: implement startup/task context profiles in `prepare-context`
- [x] T7: emit selection, suppression, and pruning metadata in JSON outputs
- [x] T8: enforce pointer-like startup output and bounded learned-context inclusion
- [x] T9 [P]: add fixture coverage for startup, semantic task, and deep task profiles

## WS4 — Memory-quality diagnostics
- [x] T10: implement memory-quality heuristics for homogeneous type mix, ephemera ratio, semantic-unavailable state, and missing learned-context activity
- [x] T11: expose those diagnostics in `status` summary and detailed doctor output
- [x] T12: add a homogeneous-memory regression fixture modeled on the "semantic requested, but no semantic path actually runs" failure mode
- [x] T13: add tests for deterministic-by-choice vs semantic-degraded labeling

## WS5 — Observe UI
- [x] T14: replace the raw header-first dream-mode affordance with a semantic readiness card and progressive-disclosure advanced controls
- [x] T15: add overview panels for readiness, quality warnings, pruning evidence, and last semantic run
- [x] T16: turn `/settings` into the semantic setup/control center while preserving expandable raw JSON
- [x] T17 [P]: add UI contract tests or snapshot coverage for degraded and ready states

## WS6 — Docs and operator guidance
- [x] T18: update README, FAQ, and automation/playbook docs to explain semantic-first posture and explicit degraded fallback
- [x] T19: document progressive context disclosure, pruning evidence, and memory-quality doctor behavior
- [x] T20: add wording checks so docs and UI copy do not imply semantic readiness when only degraded deterministic capture is active

## WS7 — Evals and release proof
- [x] T21: add benchmark fixtures comparing unpruned baseline, semantic-first degraded, and semantic-ready progressive behavior
- [x] T22: add release-check assertions for pruning advantage and truthful degraded labeling
- [x] T23: add repeated-task evidence so semantic-ready mode proves at least one concrete benefit beyond context-size reduction alone

## Parallelizable
- [x] [P] TP1: contract work and UI wire-up can proceed in parallel once readiness field names stabilize
- [x] [P] TP2: docs and wording checks can begin once operator language is settled
- [x] [P] TP3: benchmark fixture authoring can proceed in parallel with doctor heuristics

## Required verification commands
- [x] V1: targeted unit tests for readiness derivation, memory-quality heuristics, and context-profile selection
- [x] V2: targeted integration tests for `status`, `workspace doctor`, `prepare-context`, `/api/overview`, and `/settings`
- [x] V3: benchmark fixture tests for homogeneous-memory and semantic-ready pruning behavior
- [x] V4: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V5: `./.venv/bin/python -m mypy opendream scripts`
- [x] V6: `make verify`
- [x] V7: `make release-check`

## Completion checklist
- [x] semantic-first is the default posture without dishonest readiness claims
- [x] degraded deterministic fallback is explicit and actionable
- [x] progressive disclosure is observable in context assembly, not just described in docs
- [x] pruning advantage is measurable and release-gated
- [x] CLI and web UI expose the same readiness and memory-quality truth
