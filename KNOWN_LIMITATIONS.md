# Known Limitations

OpenDream is alpha software. Launch claims are intentionally bounded to what
the public repository can verify.

## Scope Limits

| Area | Current limit | Evidence or mitigation |
| --- | --- | --- |
| Fixture-driven evals | Built-in benchmark and showcase results use packaged fixtures. They do not prove performance on every user repository. | `docs/benchmarks/methodology.md`, `scripts/release_check.py` |
| Semantic execution | Semantic mode can run deterministic, delegated, or direct-provider paths. Provider-backed paths require operator setup and may report `setup_required` or `degraded`. | `docs/benchmarks/semantic-mode.md`, `opendream semantic status` |
| MCP server | OpenDream does not ship a first-party MCP server in this release. It exposes CLI, local files, and observe UI surfaces. | README integration docs |
| Platform support | CI and package metadata target Python 3.11 through 3.14. Shell helpers assume POSIX-style environments. Windows usage should be treated as best-effort until verified. | `pyproject.toml`, `.github/workflows/ci.yml` |
| Network behavior | Runtime defaults are local-first and do not send telemetry. Provider/API-key paths are explicit setup paths, not hidden analytics. | `tests/test_no_network_defaults.py`, `SECURITY.md` |
| Public/private split | Private release evidence and operator notes live outside the public repo. Public artifacts must remain usable without that overlay. | `CLEAN_ROOM.md`, `scripts/check_public_boundary.sh` |

## Claim Rules

- Avoid unsupported "best", "first", "guaranteed", or "state-of-the-art"
  claims.
- State fixture scope whenever benchmark numbers are discussed.
- Treat degraded semantic state as a real state with `reason` and
  `next_action`, not as success.
