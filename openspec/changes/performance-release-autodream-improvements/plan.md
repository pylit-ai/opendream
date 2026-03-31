# Plan: performance-release-autodream-improvements

## Implementation order

1. **Models** (T9): Add workflow_steps field — foundation for later changes
2. **Extractor** (T1-T3, T10): Salience scoring + per-kind filtering + workflow parsing — write-path improvements
3. **Retriever** (T5-T7, T12-T13): Gating + staged retrieval + memory-hurt logging — read-path improvements
4. **Storage** (T12): Memory-hurt audit writing
5. **Evaluation** (T15-T17): Performance harness fixture + implementation + CLI
6. **Integration** (T3, T18): Wire filtering into maintain(), add eval to verify
7. **Tests** (T4, T8, T11, T14, T19): All test workstreams
8. **Release** (T20-T22): Full verify + release-check + scorecard

## Dependencies

- T1 depends on nothing (pure function addition)
- T3 depends on T1, T2 (filtering needs scoring + thresholds)
- T5-T7 depend on nothing (pure retriever changes)
- T9 depends on nothing (model addition)
- T10 depends on T9 (needs field to write to)
- T12-T13 depend on nothing (audit addition)
- T15-T17 depend on T1-T3, T5-T7, T12-T13 (harness measures new features)
- T18 depends on T15-T17 (needs eval command to exist)
- T20-T22 depend on all above
