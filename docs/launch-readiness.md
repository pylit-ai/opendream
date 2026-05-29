# OpenDream Release Readiness

This checklist is the release path for a one-install OpenDream user.

## Install

Primary tool install:

```bash
uv tool install opendream
# or
pipx install opendream
```

Source install for unreleased commits:

```bash
uv tool install --force "opendream @ git+https://github.com/pylit-ai/opendream.git"
```

Optional extras: none for the runtime package. Development tooling remains under `.[dev]` and the mirrored `uv sync --group dev` path.

## Demo

```bash
opendream demo --workspace .tmp/demo
opendream status --workspace .tmp/demo
opendream dream run --workspace .tmp/demo --compat-mode project-user
opendream eval dream-layout --workspace .tmp/demo --compat-mode project-user
```

`--compat-mode project-user` writes a project/user compatibility layout. It
does not imply copied internals or equivalence with any external system.

## Upgrade

```bash
uv tool upgrade opendream
opendream workspace upgrade --workspace "$PWD"
opendream doctor --workspace "$PWD" --surface agents
opendream verify activation-capture --workspace "$PWD" --targets configured
```

For a Git install:

```bash
uv tool install --force "opendream @ git+https://github.com/pylit-ai/opendream.git"
opendream workspace upgrade --workspace "$PWD"
```

## Release Gate

Run before tagging or publishing:

```bash
make verify
.venv/bin/python scripts/release_check.py
```

The release gate covers boundary checks, stale artifact checks, vendored asset
checks, provenance-risk checks, unit tests, eval smoke, package build,
clean-venv install, CLI help, demo, dream, service lifecycle, semantic release
proof, and advanced runtime eval.

## Evidence

- Clean-room manifest: [`CLEAN_ROOM.md`](../CLEAN_ROOM.md)
- Claims matrix: [`docs/claims.md`](./claims.md)
- Known limitations: [`KNOWN_LIMITATIONS.md`](../KNOWN_LIMITATIONS.md)
- Change-control note:
  [`docs/technical-notes/dreaming-memory-change-control.md`](./technical-notes/dreaming-memory-change-control.md)

## Security And Supply Chain

- Dependabot checks Python and GitHub Actions weekly.
- OpenSSF Scorecard runs on a non-blocking schedule and on manual dispatch.
- Security reporting and supported-version policy are in [`SECURITY.md`](../SECURITY.md).
- OpenDream sends no telemetry by default. Any provider/API-key execution path
  is explicit operator setup.

## Branch Protection And Release Environment

Before a release tag, an operator must verify:

| Setting | Required state |
| --- | --- |
| `main` branch protection | PR review and required CI checks enabled |
| Required checks | CI plus release-relevant local gates from this document |
| PyPI trusted publisher | GitHub Actions `publish-pypi.yml` bound to the `pypi` environment |
| Release environment | Manual approval or maintainer-only access |
| Tags | No local or remote collision for the candidate `vX.Y.Z` |

Record the exact verification date, commit SHA, release tag, and command output
in the release notes for the candidate version.
