# ADR-011: Third-party provenance and reuse policy

## Status
Accepted

## Context
The semantic sleep-time release draws on ideas and evaluation protocols from several third-party sources with varying license terms:
- **Sleep-time Compute** (Luo et al., 2025) — MIT license, code and concepts may be adapted with attribution.
- **MemoryAgentBench** (Tian et al., 2025) — no license published at time of evaluation; code cannot be vendored.
- **Meta-Harness** — no license published; code cannot be vendored.

Without explicit provenance tracking, the project risks incorporating unlicensed code or failing to provide required attribution.

## Decision
Establish explicit provenance tracking for all third-party code, prompts, and data:

1. **MIT-licensed sources** — may be adapted into the codebase with attribution in source files and in `THIRD_PARTY_NOTICES.md`.
2. **Unlicensed sources** — must not be vendored. Clean-room adapters may implement equivalent protocols based on published papers and documentation without copying code.
3. **THIRD_PARTY_NOTICES.md** — maintained at repository root, listing all third-party dependencies with license type, source URL, and usage scope.
4. **Clean-room adapter policy** — adapters for unlicensed benchmarks are written from specification only; contributors must not have viewed the original source code for the specific adapter they write.

## Consequences
- `THIRD_PARTY_NOTICES.md` is a required release artifact
- Clean-room adapters enable benchmark compatibility without legal exposure
- Contributors must declare provenance when introducing third-party-derived code
- Review checklist includes provenance verification for new dependencies
- Some benchmark features may lag behind upstream if clean-room reimplementation is complex

## Alternatives considered
- Vendor all third-party code and sort out licensing later (rejected: legal risk)
- Avoid all third-party benchmark protocols (rejected: limits evaluation quality and comparability)
- Wait for upstream licenses before any integration (rejected: blocks release timeline)

## References
- Sleep-time Compute repository (MIT license)
- MemoryAgentBench paper (Tian et al., 2025)
- ADR-010: Benchmark suite and harness optimization
