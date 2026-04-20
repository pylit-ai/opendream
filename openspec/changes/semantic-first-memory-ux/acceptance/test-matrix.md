# test-matrix.md

| Case | Scenario | Type | Expected result |
|---|---|---|---|
| X1 | fresh workspace with supported semantic path | integration | status and UI show `ready`; setup guidance points to active owner |
| X2 | fresh workspace with no provider or adapter | integration | status and UI show `degraded` with reason and next action |
| X3 | deterministic-only by explicit choice | integration | status and UI show `disabled_by_choice`, not degraded |
| X4 | homogeneous-memory fixture dominated by `semantic_fact` | integration | doctor warns on type diversity, learned-context inactivity, and pruning quality |
| X5 | startup context assembly | unit/integration | pointer-like output with pruning metadata and bounded token estimate |
| X6 | semantic task profile with strong query match | unit/integration | bounded learned-context inclusion with explicit suppression reasons |
| X7 | unpruned baseline vs semantic-ready progressive mode | benchmark | semantic-ready shows pruning savings without repeated-task regression |
| X8 | docs/UI wording audit | release | no surface implies semantic capability from config alone |
