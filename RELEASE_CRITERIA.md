# OpenDream Release Criteria

These criteria define code-readiness for a public release candidate. They are
evidence gates, not marketing claims.

| Gate | Required evidence |
| --- | --- |
| Boundary | `scripts/check_public_boundary.sh --strict-local` passes and no public artifact contains private overlay paths, generated local agent state, secrets, or internal URLs. |
| Clean room | `CLEAN_ROOM.md`, `THIRD_PARTY_NOTICES.md`, vendored checksums, and provenance-risk scan pass. |
| Install | Local sdist/wheel build and clean virtualenv install pass from the public tree. |
| CLI smoke | `opendream --version`, `opendream --help`, demo, dream, service, and eval smoke stages pass in `scripts/release_check.py`. |
| Docs | README quickstart, showcase docs, known limitations, claims matrix, and security policy are present and public-safe. |
| Evals | Fixture-driven performance, dream-fidelity, advanced-runtime, and semantic benchmark release proof pass or record exact degraded state. |
| Packaging | Package-boundary and public-artifact checks pass; generated artifacts have hashes. |
| CI/security | CI workflow, publish workflow, dependency update policy, and Scorecard/rationale exist. |
| Final decision | Private release evidence records unresolved risks, waivers, Linear issue updates, and go/no-go recommendation. |

Every P0/P1 launch ticket must map to at least one row above in the private
completion ledger.
