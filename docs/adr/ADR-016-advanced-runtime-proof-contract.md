# ADR-016: Advanced runtime proof contract

## Status
Accepted

## Context
Release claims about memory-excellence need evidence across all supported execution modes, not just deterministic. Without cross-mode evidence, a release could claim superiority while only testing the fallback path.

## Decision
1. **An advanced-runtime report is generated during release-check** and validates against `advanced-runtime-report.schema.json`.
2. **The report combines:**
   - Memory-excellence scorecard results (stale claim rate, contradiction resolution, etc.)
   - Execution-mode matrix (which modes were tested)
   - Docs truthfulness (no forbidden wording, execution matrix present)
   - Release verdict: `pass`, `fail`, or `partial`
3. **The report is archived** alongside release artifacts for auditability.
4. **Release-check fails** if the advanced-runtime report verdict is `fail` or if docs/runtime mismatch.
5. **Supported comparison modes:** deterministic-only, direct-provider, codex-account, claude-scheduled-task, cursor-automation.

## Consequences
- Release claims are backed by generated evidence, not manual assertions.
- The excellence scorecard is proven across execution surfaces, not just one.
- Docs truthfulness is mechanically checked as part of the release gate.
