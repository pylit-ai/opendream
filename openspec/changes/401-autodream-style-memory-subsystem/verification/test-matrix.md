# Test Matrix

| Area | Test | Type | Blocking |
|---|---|---|---|
| Schema | JSON validation | automated | yes |
| Consolidation | deterministic golden run | automated | yes |
| Bootstrap | staged migration correctness | automated + human | yes |
| Index | startup budget | automated | yes |
| Conflict handling | contested/superseded behavior | automated | yes |
| Retrieval | top-k precision | automated + human | yes |
| Concurrency | lock/corruption safety | automated | yes |
| Safety | no code writes | automated | yes |
| Decay | stale-item quarantine | automated | no |
| Outcome | repeated-task benchmark | automated + human | no |
| Licensing | clean-room scan | automated + manual | yes |
