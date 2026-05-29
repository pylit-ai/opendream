# Clean-Room Provenance

OpenDream is maintained as a clean-room implementation. This file is the
provenance manifest for code, docs, benchmarks, and vendored assets.

## Provenance Classes

| Class | Policy | Current sources |
| --- | --- | --- |
| Code reuse | Code in this repository is written for OpenDream and licensed under Apache-2.0 unless a file says otherwise. | `opendream/**`, `scripts/**`, `tests/**` |
| Concept inspiration | Published papers, blog posts, and project documentation may inform requirements and evaluation dimensions. They do not authorize copying code, prompts, unpublished docs, or fixtures. | Sleep-time compute, Observational Memory, MemoryAgentBench, Meta-Harness |
| Benchmark-dimension inspiration | Benchmark dimensions are reimplemented against OpenDream APIs and fixtures. | `docs/benchmarks/**`, `opendream/benchmark_adapters.py` |
| Vendored JS | Vendored browser assets are MIT-licensed packages with pinned versions and checksums. | `opendream/static/vendor/**`, `THIRD_PARTY_NOTICES.md` |
| Excluded sources | Workspace notes, generated local runtime state, account-specific docs, and unpublished vendor internals are not sources for OpenDream code. | Excluded by `scripts/check_release_hygiene.sh` |

## Explicit Non-Use Statement

OpenDream does not use unpublished vendor code, prompts, fixtures, datasets,
unpublished docs, or generated local runtime artifacts. Compatibility names describe
documented behavior or legacy CLI flags, not copied internals.

## Release Gate

The release gate must fail if this manifest is missing. It must also run the
release hygiene, vendored-asset, and provenance-risk scanners before artifacts
are treated as release candidates:

```bash
scripts/check_release_hygiene.sh --strict-local
python scripts/check_vendor_assets.py
python scripts/check_provenance_risk.py
```

## Review Notes

- Add new third-party packages to `THIRD_PARTY_NOTICES.md`.
- Add new vendored browser files to `opendream/static/vendor/README.md` with
  on-disk sha256 values.
- Keep legal judgment outside automation. The scanner is a hygiene gate, not a
  legal opinion.
