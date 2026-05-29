# Contributing

OpenDream accepts release-ready changes only. Keep local operator notes,
machine paths, secrets, account names, and generated local runtime state out of
commits.

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
- files changed and release-hygiene impact
- verification commands and results
- docs updates for changed behavior
- release-risk notes if packaging, CI, security, or eval behavior changed

## Issues

Use the issue templates. Route reports by the failure surface:

- install or CLI behavior: bug report
- stale, harmful, or low-quality memory: memory quality report
- benchmark fixture or scorecard behavior: bug report with benchmark fixture noted
- agent activation/integration behavior: bug report with agent target noted
- security or privacy behavior: security report
- trademark, logo, wordmark, license, or brand-boundary issues: issue report only
  when no security-sensitive details are involved

Include environment, install path, agent target, workspace OS, command output,
and reproduction steps when applicable.

## Release Hygiene

Before opening a PR, run:

```bash
scripts/check_release_hygiene.sh --strict-local
python scripts/check_provenance_risk.py
```
