# 10-license-provenance-and-cleanroom.md

## Reuse policy

### Sleep-time Compute
- the attached archive includes an MIT license
- selective code or prompt reuse is allowed if:
  - provenance is recorded
  - MIT notice is preserved
  - copied files are isolated and documented
  - copied material is not confused with OpenDream-authored canonical behavior

### MemoryAgentBench
- no redistributable license grant is obvious in the attached archive root
- treat as reference only unless upstream license is confirmed and recorded
- prefer clean-room adapters and paper-driven evaluation criteria

### Meta-Harness
- no redistributable license grant is obvious in the attached archive root
- treat as reference only unless upstream license is confirmed and recorded
- use concept extraction, not vendoring, by default

## Required files
- `THIRD_PARTY_NOTICES.md`
- provenance manifest in release evidence
- copied-source inventory with path, upstream source, commit/date, license, and rationale

## Forbidden shortcuts
- copying prompt text into production without attribution
- vendoring benchmark or optimizer code without explicit redistribution rights
- claiming clean-room status if copied material is present but undocumented
