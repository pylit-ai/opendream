# spec.md — 431-cli-ux-polish

## Title
Polish CLI onboarding, exit semantics, and human-facing guidance

## Why
Recent UX trials showed the OpenDream CLI is strong for automation but still has avoidable friction:
- bare `opendream` only emits argparse's default "required: command" error
- eval subcommands can report `"status": "failed"` while still exiting `0`
- dream commands with no episodes or transcripts can look more successful than they are
- `worker` and `daemon` are both present but their intended use is not obvious from help text

## In scope
- non-zero CLI exits for failed eval subcommands
- clearer no-argument and missing-subcommand hints
- explicit `no-episodes` behavior for dream run and enqueue when neither explicit nor discovered inputs exist
- help text clarifying `dream worker` vs `dream daemon`

## Out of scope
- redesigning the JSON output format
- replacing argparse
- interactive prompts or TUI behavior

## User-visible behavior
- failed evals exit non-zero
- no-arg invocation suggests `init`, `demo`, and `-h`
- `dream run` and `dream enqueue` clearly report `no-episodes` when nothing is available to process
- help output states when to use `worker` vs `daemon`

## Acceptance criteria
- [x] AC-1: `eval memory-quality` and `eval dream-fidelity` exit `1` when their JSON status is `failed`
- [x] AC-2: bare `opendream` error output includes a concrete next-step hint
- [x] AC-3: `dream run` and `dream enqueue` return explicit `no-episodes` results when no episode files are provided or discovered
- [x] AC-4: top-level and dream help text distinguish `dream worker` from `dream daemon`

## Required verifiers
- unit tests: yes, CLI return-code and parser-message checks
- integration tests: yes, `tests.test_memory_cli`
- manual verification: yes, `opendream`, `opendream dream worker -h`, and `opendream eval memory-quality`
