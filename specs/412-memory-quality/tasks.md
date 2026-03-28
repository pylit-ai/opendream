# tasks.md — 412-memory-quality

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `412-memory-quality` to `specs/registry.yaml`
- [x] T2: implement hybrid retrieval with lexical, embedding-like, type, recency, and scope contributions
- [x] T3: add candidate clustering, semantic dedupe, and contradiction handling
- [x] T4: add structured retrieval explanations and audit payloads
- [x] T5: add deterministic eval corpus plus `opendream eval memory-quality`
- [x] T6: add paraphrase, contradiction, quarantine, and noisy-corpus tests
- [x] T7: update README examples
- [x] T8: run `make verify`
- [x] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: eval fixture authoring
- [x] [P] TP2: README updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] eval command passes
- [x] tests pass
