# test-matrix.md — 436-agent-ready-platform-complete

| Area | Scenario | Type | Expected |
|---|---|---|---|
| package generation | codex package scaffold from canonical inputs | integration | plugin validates and includes manifest/skills/MCP config |
| package generation | claude plugin scaffold from canonical inputs | integration | plugin validates and includes skills/hooks/marketplace metadata |
| package generation | cursor plugin scaffold from canonical inputs | integration | plugin validates and includes rules/skills/hooks manifest |
| package generation | copilot instruction pack generation | integration | repo-wide and path-scoped instructions generated from canonical guidance |
| guidance | nested guidance precedence | unit/integration | more specific guidance wins without duplicate policy |
| contracts | contract export schema | unit | JSON validates against contract schema |
| contracts | example fixtures round-trip | integration | parsers accept exported fixtures |
| MCP inventory | undocumented MCP in adapter | integration | conformance check fails |
| engine registry | unknown engine id | unit | registration rejected |
| engine registry | plugin-backed engine manifest valid | integration | engine installs/loads and runs deterministically |
| automation | built-in projection engine | integration | writes projection records only |
| automation | guidance-drift engine | integration | emits reviewable proposal records |
| isolation | code-mutating job without isolated mode | integration | blocked |
| isolation | code-mutating job with isolated worktree | e2e | run succeeds, report includes worktree metadata |
| release | full verify | e2e | passes |
| docs | generated vendor docs point to canonical sources | integration | no normative duplication |
