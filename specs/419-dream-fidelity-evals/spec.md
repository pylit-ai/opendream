# spec.md — 419-dream-fidelity-evals

## Title
Add machine-readable dream fidelity evals for transcript-native behavior

## Why
`412-memory-quality` proves retrieval and contradiction handling, but it does not directly prove the transcript-native dreamer behaves as intended. OpenDream needs a dedicated fidelity eval that exercises transcript-only dreaming, checks bounded-search reporting, verifies dream status visibility, and proves retrieval works from dream-produced durable memory.

## In scope
- packaged transcript fixture for dream-fidelity evaluation
- `opendream eval dream-fidelity`
- machine-readable checks for transcript-only emergence, phase fidelity, date normalization, compat views, and bounded-search reporting
- retrieval validation against dream-produced durable memory
- clean-venv smoke coverage for the dream-fidelity eval

## Out of scope
- hosted eval dashboards
- large-scale benchmarking across arbitrary transcript corpora
- replacement of `eval memory-quality`

## User-visible behavior
- operators can run `opendream eval dream-fidelity --workspace <path>` and get a deterministic JSON report
- the report states exactly which fidelity checks passed or failed
- installed-package smoke tests exercise the same eval, not just the demo path

## Acceptance criteria
- [x] AC-1: `opendream eval dream-fidelity --workspace <path>` emits machine-readable per-check results
- [x] AC-2: the eval passes on the packaged transcript-only fixture and proves transcript-only durable emergence
- [x] AC-3: the eval proves date normalization, four-phase summaries, and compatibility-view generation
- [x] AC-4: the eval fails if bounded-search reporting is absent or claims full-corpus replay
- [x] AC-5: the eval proves retrieval can select dream-produced package-manager and workflow memories
- [x] AC-6: clean-venv release smoke runs the dream-fidelity eval successfully from the installed package

## Edge cases
- eval workspace initialized with a non-default memory directory
- installed package using packaged fixtures rather than repo-relative test data
- transcript-derived titles that do not match a single hard-coded label string

## Required verifiers
- unit tests: no
- integration tests: yes, CLI coverage for `eval dream-fidelity` and clean-venv install smoke
- evals / scenario checks: yes, the `dream-fidelity` eval itself
- manual verification: yes, run `opendream eval dream-fidelity --workspace <tmp>`

## Risks
- eval coverage can create false confidence if it drifts from the runtime summary contract
- a single packaged transcript fixture can become too narrow if future runtime behavior broadens materially

## Links
- `../418-transcript-native-dream-engine/spec.md`
- `../412-memory-quality/spec.md`
- `../../README.md`
