# test-matrix.md — 441-workspace-catalog-dashboard-bundle

| Area | Scenario | Type | Expected |
|---|---|---|---|
| catalog | add workspace on init/activate | integration | workspace appears in machine-local catalog |
| catalog | install-service on existing workspace | integration | catalog entry updates with service metadata |
| catalog | workspace path missing | unit/integration | entry marked missing/stale, not deleted silently |
| roots | add root | unit/integration | root persisted |
| roots | remove root | unit/integration | root removed without corrupting catalog |
| scan | scan configured root with multiple repos | integration | only `.opendream/` repos imported |
| scan | scan with no configured roots | unit | explicit error or empty report with remediation |
| cli | workspace list | integration | table/json output correct |
| cli | workspace inspect | integration | detailed status returned |
| cli | workspace forget | integration | entry removed from catalog, workspace untouched |
| ui | /workspaces dashboard route | integration | cards render |
| ui | dashboard card links to workspace detail | integration | navigation works |
| ui | broken workspace state | integration | card shows missing/broken diagnostic |
| docs | wording check | unit | docs do not imply hidden global canonical state |
| release | full verify | e2e | all catalog/dashboard gates pass |
