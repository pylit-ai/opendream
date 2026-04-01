# release-gates.md — 440-memory-platform-superiority-release-bundle

A release candidate is blocked unless all gates below pass.

## RG-1 Memory-excellence dependency
- the memory-excellence bundle is present and passing
- verified writes, grep-first probing, generated-only views, relation-aware retrieval, reconciliation, procedural-memory upgrades, and the memory-excellence scorecard are active release requirements

## RG-2 Setup unambiguity
- `opendream semantic setup --prefer no-extra-key` exists
- it returns a machine-readable report
- it recommends one supported strategy and explains why others were not chosen
- setup outputs are truthful about who owns semantic execution

## RG-3 Execution ownership visibility
- `semantic status`, `dream status`, contract export, and read-model surfaces show:
  - active execution strategy
  - auth source
  - last semantic owner
  - fallback path
  - candidate strategies
- docs use the same terminology

## RG-4 Codex trusted local/private execution
- Codex account-backed adapter exists and can be scaffolded
- trust-boundary warnings are explicit
- no public/untrusted automation context is silently steered into account-backed mode
- smoke scaffolds and fixture tests pass

## RG-5 Claude scheduled-task execution
- Claude adapter exists with Desktop and Cloud scheduling scaffolds
- feature-mining / radar / semantic-refresh scaffolds exist
- delegated envelopes from Claude validate and ingest correctly
- docs do not claim direct OpenDream-owned Claude auth reuse

## RG-6 Cursor automation execution
- Cursor adapter exists with account-backed automation scaffolds
- artifact return path / inbox conventions are generated
- delegated envelopes from Cursor validate and ingest correctly
- docs distinguish account-backed automation from API-key programmatic mode

## RG-7 Unsupported-path policy
- setup wizard does not recommend unsupported Gemini OAuth reuse
- docs mark unsupported paths explicitly
- tests cover negative recommendations

## RG-8 Feature-mining compatibility
- feature-radar / bug-radar / fix-radar / semantic-refresh can be scaffolded for supported execution modes
- deterministic projection and delegated semantic refresh cooperate without treating projections as canonical truth
- playbooks and examples are runnable

## RG-9 Docs and release-note truthfulness
- README / FAQ / coding-agents docs / automation playbook / benchmark docs / CHANGELOG are reconciled
- docs no longer imply unsupported hidden auth, generic OAuth borrowing, or ambiguous semantic ownership
- docs position OpenDream as a verified, bounded, relation-aware memory control plane

## RG-10 Runtime-superiority proof
- release evidence includes a runtime-superiority report that combines:
  - memory-excellence scorecard
  - execution-mode matrix
  - repeated coding-task deltas
  - delegated-ingest correctness
  - feature-mining/radar correctness
- release fails if any supported execution mode violates the configured excellence budgets

## RG-11 Verification
- `make verify` and `make release-check` include:
  - adapter schema tests
  - setup-wizard tests
  - delegated-ingest tests
  - docs wording checks
  - runtime-superiority report generation
