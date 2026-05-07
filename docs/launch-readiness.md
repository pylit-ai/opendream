# OpenDream Launch Readiness

This checklist is the public release path for a one-install OpenDream user.

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

Optional extras: none for the public runtime. Development tooling remains under `.[dev]` and the mirrored `uv sync --group dev` path.

## Demo

```bash
opendream demo --workspace .tmp/demo
opendream status --workspace .tmp/demo
opendream dream run --workspace .tmp/demo --compat-mode autodream
opendream eval dream-fidelity --workspace .tmp/demo --compat-mode autodream
```

## Upgrade

```bash
uv tool upgrade opendream
opendream workspace upgrade --workspace "$PWD"
opendream doctor --workspace "$PWD" --surface agents
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

The release gate covers boundary checks, stale artifact checks, unit tests, eval smoke, package build, clean-venv install, CLI help, demo, dream, service lifecycle, and advanced runtime eval.
