# Release Evidence

Public-safe evidence for the latest OpenDream release and the final
project-lead review-response verification pass.

## Candidate

- Package: `opendream`
- Version: `0.3.7`
- Tag: `v0.3.7`
- Published release: <https://github.com/pylit-ai/opendream/releases/tag/v0.3.7>
- Review-response commit: `21ab1d4`
- Release commit: `c82b959a722073d2efed73ebca68ded250782746`
- Evidence generated: `2026-05-12T23:36:25Z`
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
| Clean build/install smoke | PASS | Release automation built and installed `opendream 0.3.7` locally before tagging |

## Remote Release Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Remote tag check | PASS | `refs/tags/v0.3.7` exists on `origin` |
| GitHub release | PASS | Non-draft, non-prerelease `v0.3.7`, published `2026-05-12T23:36:08Z` |
| Required CI on release commit | PASS | CI run `25768566639`, conclusion `success`, head SHA `c82b959a722073d2efed73ebca68ded250782746` |
| PyPI trusted publishing | PASS | Publish run `25768567321`, conclusion `success`, head SHA `c82b959a722073d2efed73ebca68ded250782746` |
| PyPI package smoke | PASS | PyPI latest version is `0.3.7`; Python 3.12 clean install reports `opendream 0.3.7` and `import opendream` succeeds |

## Artifact Hashes

| Artifact | SHA-256 |
| --- | --- |
| `opendream-0.3.7-py3-none-any.whl` | `4c27124f401f86144fa167fcb068c79272b3f7e181d6142b1e6c6877fd084db8` |
| `opendream-0.3.7.tar.gz` | `7854538ece1813b778ac6153af0fbca01c75518fd1cec643f18fc256d4f7cf90` |

## Known Waivers

- Branch protection and ruleset API checks returned unavailable while the GitHub
  repository is private on the current plan. Configure branch protection or
  rulesets after repository visibility or plan supports that feature.
- This release is an alpha / technical preview. Public copy should describe
  OpenDream as local-first, auditable memory for coding agents, not as SOTA or
  AutoDream parity.
