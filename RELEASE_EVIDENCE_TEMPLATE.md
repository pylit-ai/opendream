# Release Evidence Template

This template is public-safe. Fill private URLs, account checks, and Linear
writeback details in the private overlay.

## Candidate

- Version:
- Public branch:
- Public commit:
- Generated at:
- Operator:

## Required Gates

| Gate | Command or artifact | Status | Notes |
| --- | --- | --- | --- |
| Boundary | `scripts/check_public_boundary.sh --strict-local` |  |  |
| Verification | `make verify` |  |  |
| Release check | `python scripts/release_check.py --timeout-seconds 300` |  |  |
| Manifest JSON | `.tmp/release-check/release_manifest.json` |  |  |
| Summary | `.tmp/release-check/release_summary.md` |  |  |
| Clean install | release-check clean venv stages |  |  |
| Artifact hashes | release manifest `artifact_hashes` |  |  |
| Remote CI | private operator evidence |  |  |
| Publish dry-run | private operator evidence |  |  |

## Unresolved Risks

| Risk | Owner | Decision |
| --- | --- | --- |

## Go/No-Go

- Recommendation:
- Required manual action before tag:
- Required post-publish smoke:
