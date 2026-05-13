# Release Evidence

Public-safe evidence for the latest OpenDream release and the final
project-lead review-response verification pass.

## Candidate

- Package: `opendream`
- Version: `0.3.8`
- Tag: `v0.3.8`
- Published release: <https://github.com/pylit-ai/opendream/releases/tag/v0.3.8>
- Review-response commit: `21ab1d4`
- Review-polish commit: `94e4b6e`
- Release commit: `b7b05d22b011c39e99536d28892d5501160d7001`
- Evidence generated: `2026-05-13T02:20:24Z`
- Python: `3.12.11`
- Platform: `macOS-26.4.1-arm64-arm-64bit`

## Local Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Public boundary | PASS | `scripts/check_public_boundary.sh --strict-local`, 8 seconds |
| Provenance risk | PASS | `python scripts/check_provenance_risk.py` |
| Full verification | PASS | `make verify` |
| Release check | PASS | `python scripts/release_check.py --timeout-seconds 300` |
| Release manifest | PASS | `.tmp/release-check/release_manifest.json`, 29 stages, 0 failures |
| Dream fidelity boundary JSON | PASS | Passing report has `violations: []`, `blocked_code_writes: []`, and allowed memory writes separated |
| Semantic benchmark empty tier | PASS | Empty MemoryAgentBench-style tier reports `skipped_no_fixture`; overall status is `passed_with_skips` |
| Clean build/install smoke | PASS | Release automation built and installed `opendream 0.3.8` locally before tagging |

## Remote Release Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Remote tag check | PASS | `refs/tags/v0.3.8` exists on `origin` |
| GitHub release, authenticated | PASS | Non-draft, non-prerelease `v0.3.8`, published `2026-05-13T02:14:56Z` |
| Required CI on release commit | PASS | CI run `25774060612`, conclusion `success`, head SHA `b7b05d22b011c39e99536d28892d5501160d7001` |
| PyPI trusted publishing | PASS | Publish run `25774060977`, conclusion `success`, head SHA `b7b05d22b011c39e99536d28892d5501160d7001` |
| PyPI package smoke | PASS | PyPI latest version is `0.3.8`; Python 3.12 clean install from `https://pypi.org/simple` reports `opendream 0.3.8` and `import opendream` succeeds |
| External GitHub visibility | PENDING | Requires the operator visibility flip for `pylit-ai/opendream`; re-check repo, release, CI badge, raw demo media, and Git install after the repo is public |

## Artifact Hashes

| Artifact | SHA-256 |
| --- | --- |
| `opendream-0.3.8-py3-none-any.whl` | `93092c08f5a76360d165fd6a7f45a7cc492587ed4baccaec735f7506db8d5689` |
| `opendream-0.3.8.tar.gz` | `54846babf2f943182f8284011d73cb3995f45387aab1b2a51561b931468a5b89` |

## Known Waivers

- Branch protection and ruleset API checks returned HTTP 403 while the GitHub
  repository is private on the current plan: "Upgrade to GitHub Pro or make
  this repository public to enable this feature." Configure branch protection
  or rulesets after repository visibility or plan supports that feature, then
  replace the `External GitHub visibility` row with the final verification
  result.
- This release is an alpha / technical preview. Public copy should describe
  OpenDream as local-first, auditable memory for coding agents, not as SOTA or
  AutoDream parity.
