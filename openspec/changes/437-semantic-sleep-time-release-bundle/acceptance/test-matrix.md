# test-matrix.md — 437-semantic-sleep-time-release-bundle

| Area | Scenario | Type | Expected |
|---|---|---|---|
| semantic mode | semantic run on transcript-only episodes | integration | learned-context proposals emitted |
| semantic mode | hybrid run on transcript-only episodes | integration | durable + learned-context outputs coexist |
| learned context | conflicting learned-context vs durable fact | integration | verifier blocks or downgrades conflict |
| anticipation | query-family inference on repeated repo tasks | integration | tagged query families appear in run report |
| promotion | proposal rejected by deterministic verifier | integration | no promotion occurs |
| promotion | proposal accepted by verifiers | integration | learned-context promotion artifact exists |
| retrieval fusion | prepare-context with learned context enabled | integration | attributed sections emitted |
| retrieval fusion | stale learned context present | integration | gating suppresses or de-prioritizes it |
| provider config | missing provider credentials | unit/integration | semantic mode fails explicitly or falls back per policy |
| automation | semantic refresh automation job | integration | strategist/refresh records updated |
| benchmark internal | deterministic vs semantic vs hybrid internal suite | e2e | comparative scorecard emitted |
| benchmark MAB | AR adapter run | integration | score archived |
| benchmark MAB | TTL adapter run | integration | score archived |
| benchmark MAB | LRU adapter run | integration | score archived |
| benchmark MAB | CR adapter run | integration | score archived |
| coding-task eval | repeated repo task with semantic mode | e2e | utility metrics emitted |
| memory-hurt | stale learned context induces harm | integration | harm attribution captured |
| harness bootstrap | bootstrap pre-prompt snapshot enabled | integration | initial prompt includes environment snapshot |
| harness optimizer | smoke optimization on toy harness set | integration | report produced, no unsafe mutations |
| package/docs | contract export lists semantic surfaces | unit/integration | schema-valid export |
| release | full verify + release-check | e2e | all gates pass |
