# release-gates.md — 436-agent-ready-platform-complete

A release candidate is blocked unless all gates below pass.

## RG-1 Plugin/package generation
- OpenDream can generate installable thin packages for:
  - Codex
  - Claude Code
  - Cursor
  - GitHub Copilot
- generation outputs are reproducible for the same inputs
- generated packages contain no canonical policy duplication
- generated packages include a provenance report with source docs and schema versions

## RG-2 Path-scoped guidance
- root guidance remains concise
- path-scoped guidance exists for major subtrees where behavior materially differs
- precedence is documented and testable
- generated vendor-specific instruction files derive from canonical guidance rather than hand-maintained duplicates

## RG-3 Contract stability
- contract export exists and passes schema validation
- CLI examples are versioned and round-trip parse in tests
- `cli_output_version` changes require fixture updates and changelog entries

## RG-4 MCP inventory
- `docs/mcp/servers.md` is fully populated
- every exposed MCP/tool integration documents auth, trust boundary, failure modes, and revocation path
- conformance checks fail if adapter or plugin references undocumented MCP surfaces

## RG-5 Engine registry
- all unattended `skill_ref` executions resolve through declared engines
- unknown or undeclared engines are rejected
- built-in engines and plugin-backed engines expose machine-readable contracts and side-effect policy
- no arbitrary shell execution path exists for unattended jobs

## RG-6 Guidance drift
- repeated friction signals can produce deterministic reviewable proposals
- proposals do not mutate canonical docs automatically
- promotion/rejection flows leave structured audit artifacts

## RG-7 Isolated execution
- any automation with code mutation enabled requires isolated worktree mode
- run reports include worktree path, base ref, diff summary, and cleanup state
- direct mutation of the primary workspace from unattended code-writing automation is blocked by policy and tests

## RG-8 End-to-end conformance
- `make verify` passes
- all new schema fixtures pass
- package generators pass smoke tests
- at least one end-to-end automation proposal flow and one isolated code-mutation flow pass in temp repos
- no constitution violations remain
