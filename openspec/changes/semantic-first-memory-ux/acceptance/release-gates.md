# release-gates.md

- `status`, `workspace doctor`, `/overview`, and `/settings` agree on semantic readiness vs degraded vs deterministic-by-choice state
- a workspace with semantic posture but no runnable semantic path is never labeled semantic-ready
- the homogeneous-memory fixture is surfaced as degraded or warning-bearing, not healthy
- `prepare-context` exposes profile and pruning metadata and keeps startup output pointer-like
- release-check includes a pruning-advantage assertion against an unpruned baseline
- docs and UI wording do not imply that writing `mode=semantic` alone activates semantic capability
