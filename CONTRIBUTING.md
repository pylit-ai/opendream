# Contributing

OpenDream accepts public, publishable changes only. Keep private operator notes,
local machine paths, secrets, account names, and generated local agent state out
of public commits.

## Development Setup

```bash
make setup
make verify
```

## Pull Requests

Include:

- problem statement and user-facing change
- files changed and public/private boundary impact
- verification commands and results
- docs updates for changed behavior
- release-risk notes if packaging, CI, security, or eval behavior changed

## Issues

Use the issue templates. Include environment, install path, agent target,
workspace OS, command output, and reproduction steps when applicable.

## Public Boundary

Before opening a PR, run:

```bash
scripts/check_public_boundary.sh --strict-local
python scripts/check_provenance_risk.py
```
