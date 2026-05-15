# Clean-Room Provenance

OpenDream is maintained as a public, publishable implementation. This file is
the public provenance manifest for code, docs, benchmarks, and vendored assets.

## Provenance Classes

| Class | Policy | Current sources |
| --- | --- | --- |
| Code reuse | Public code in this repository is written for OpenDream and licensed under Apache-2.0 unless a file says otherwise. | `opendream/**`, `scripts/**`, `tests/**` |
| Concept inspiration | Public papers, blog posts, and project documentation may inform requirements and evaluation dimensions. They do not authorize copying code, prompts, non-public docs, or fixtures. | Sleep-time compute, Observational Memory, MemoryAgentBench, Meta-Harness |
| Benchmark-dimension inspiration | Benchmark dimensions are reimplemented against OpenDream APIs and fixtures. | `docs/benchmarks/**`, `opendream/benchmark_adapters.py` |
| Vendored JS | Vendored browser assets are public MIT-licensed packages with pinned versions and checksums. | `opendream/static/vendor/**`, `THIRD_PARTY_NOTICES.md` |
| No-reuse sources | Non-public workspace notes, generated local agent state, account-specific docs, and unpublished vendor internals are not sources for public code. | Excluded by `scripts/check_public_boundary.sh` |

## Explicit Non-Use Statement

OpenDream does not use non-public vendor code, prompts, fixtures, datasets,
internal docs, or generated local agent artifacts. Compatibility names describe
public behavior or legacy CLI flags, not copied internals.

## Release Gate

The release gate must fail if this manifest is missing. It must also run the
public boundary, vendored-asset, and provenance-risk scanners before artifacts
are treated as release candidates:

```bash
scripts/check_public_boundary.sh --strict-local
python scripts/check_vendor_assets.py
python scripts/check_provenance_risk.py
```

## Review Notes

- Add new third-party packages to `THIRD_PARTY_NOTICES.md`.
- Add new vendored browser files to `opendream/static/vendor/README.md` with
  on-disk sha256 values.
- Keep legal judgment outside automation. The scanner is a hygiene gate, not a
  legal opinion.
