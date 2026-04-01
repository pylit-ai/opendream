# test-matrix.md — 438-semantic-auth-adapters-release-bundle

| Area | Scenario | Type | Expected |
|---|---|---|---|
| setup | detect Codex and recommend no-extra-key trusted local path | unit/integration | setup selects `codex-account` with trust warning notes |
| setup | detect Claude only and recommend scheduled-task path | unit/integration | setup selects `claude-scheduled-task` |
| setup | detect Cursor only and recommend automation path | unit/integration | setup selects `cursor-automation` |
| setup | detect nothing and no keys | unit | setup recommends deterministic-only or explicit provider setup |
| setup | Gemini present | unit | setup explicitly does not recommend OAuth reuse |
| codex | scaffold adapter | integration | files/manifests/wrapper docs generated |
| codex | status when auth cache missing | unit | degraded status with remediation |
| claude | scaffold desktop task path | integration | command/skill/task template generated |
| claude | scaffold cloud task path | integration | cloud-safe template generated with no local-file assumptions |
| cursor | scaffold automation path | integration | automation prompt + artifact return path generated |
| ingest | valid delegated envelope | unit/integration | ingest succeeds and archives envelope |
| ingest | invalid delegated envelope | unit | ingest fails with schema error |
| status | semantic status matrix | integration | active + candidate strategies visible |
| contract export | adapter inventory exported | integration | JSON includes strategies, auth sources, status fields |
| docs | forbidden magic wording | unit | wording checks fail when unsupported claims reappear |
| release | release-check full run | e2e | all new stages pass |
