# Contributing

OpenDream accepts public, publishable changes only. Keep private operator notes,
local machine paths, secrets, account names, and generated local agent state out
of public commits.

## Development Setup

```bash
make setup
make verify
```

For install problems, include the exact install path (`pip`, `pipx`, `uvx`, or
source checkout), Python version, OS, and command output.

## Pull Requests

Include:

- problem statement and user-facing change
- files changed and public/private boundary impact
- verification commands and results
- docs updates for changed behavior
- release-risk notes if packaging, CI, security, or eval behavior changed

## Issues

Use the issue templates. Route reports by the failure surface:

- install or CLI behavior: bug report
- stale, harmful, or low-quality memory: memory quality report
- benchmark fixture or scorecard behavior: bug report with benchmark fixture noted
- agent activation/integration behavior: bug report with agent target noted
- security or privacy behavior: private security report
- trademark, logo, wordmark, license, or brand-boundary issues: public issue only
  when no security-sensitive details are involved

Include environment, install path, agent target, workspace OS, command output,
and reproduction steps when applicable.

## Public Boundary

Before opening a PR, run:

```bash
scripts/check_public_boundary.sh --strict-local
python scripts/check_provenance_risk.py
```
