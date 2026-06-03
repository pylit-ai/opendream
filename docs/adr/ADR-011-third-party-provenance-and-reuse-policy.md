# ADR-011: Third-party provenance and reuse policy

## Status
Accepted

## Context
The semantic sleep-time release draws on ideas and evaluation protocols from several third-party sources with varying license terms:
- **Sleep-time Compute** (Luo et al., 2025) — concepts may inform design; no external code is required for OpenDream's implementation.
- **MemoryAgentBench** (Tian et al., 2025) — no license published at time of evaluation; code cannot be vendored.
- **Meta-Harness** — no license published; code cannot be vendored.

Without explicit provenance tracking, the project risks incorporating unlicensed code or failing to provide required attribution.

## Decision
Establish explicit provenance tracking for all third-party code, prompts, data,
and research inspiration:

1. **Bundled third-party code/assets** — must be listed in
   `THIRD_PARTY_NOTICES.md` with license text or a clear license pointer.
2. **Research inspiration** — belongs in `docs/provenance.md`, not
   `THIRD_PARTY_NOTICES.md`, unless OpenDream bundles code, data, or assets
   from that source.
3. **Unlicensed sources** — must not be vendored. Clean-room adapters may
   implement equivalent protocols based on published papers and documentation
   without copying code, prompts, fixtures, or datasets.
4. **Clean-room adapter policy** — adapters for unlicensed benchmarks are
   written from specification only; contributors must not copy source code for
   the specific adapter they write.

## Consequences
- `THIRD_PARTY_NOTICES.md` remains a required release artifact for bundled
  third-party code/assets
- `docs/provenance.md` carries concept and benchmark-provenance notes
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
