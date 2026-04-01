# test-matrix.md — 440-memory-platform-superiority-release-bundle

| Area | Scenario | Type | Expected |
|---|---|---|---|
| setup | Codex detected on trusted local machine | unit/integration | recommends `codex-account` |
| setup | Claude only, no provider keys | unit/integration | recommends `claude-scheduled-task` |
| setup | Cursor only, no provider keys | unit/integration | recommends `cursor-automation` |
| setup | provider keys configured | unit/integration | can recommend `direct-provider` per preference |
| setup | Gemini detected | unit | negative recommendation only |
| codex | scaffold trusted local adapter | integration | wrapper/config/docs generated |
| codex | public/untrusted runner | unit | codex-account not recommended |
| claude | scaffold desktop scheduled task | integration | task/command/prompt files generated |
| claude | scaffold cloud scheduled task | integration | cloud-safe template generated |
| cursor | scaffold automation | integration | automation prompt + artifact path generated |
| ingest | valid delegated envelope | integration | proposal/event artifacts emitted |
| ingest | invalid delegated envelope | unit | archived with failure report |
| feature mining | scaffold feature-radar delegated path | integration | runnable example generated |
| feature mining | scaffold semantic-refresh delegated path | integration | runnable example generated |
| status | semantic status matrix | integration | active/candidate strategies visible |
| contract export | adapter inventory exported | integration | JSON includes strategy and owner fields |
| docs | forbidden wording present | unit | wording gate fails |
| superiority | generate runtime-superiority report | integration | report produced and schema-valid |
| release | full verify + release-check | e2e | all gates pass |
