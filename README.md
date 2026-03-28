# OpenDream

OpenDream is a local-first memory subsystem for coding agents. It captures immutable evidence, derives typed memory candidates, consolidates durable memory with provenance, and exposes reproducible CLI workflows for bootstrap, dreaming, retrieval, evaluation, and release checks.

## Integration model (canonical surface)

OpenDream’s **core product** is a **local CLI-first memory engine** plus the thin runtime integration layer from spec **403**. It does **not** ship a long-running daemon or an in-repo model-driven “decide what to remember” service.

The **practical integration contract** is:

- **`emit-event`** — append schema-valid evidence to the store.
- **`maintain`** — cron-/idle-/session-end-friendly wrapper that runs extract plus consolidate when work qualifies, with structured **`status`** and **`reason`** when it skips (not a silent no-op).
- **`prepare-context`** — prompt-ready retrieval surface for the next task.

The **runtime** (hooks, scripts, IDE rules, or your own automation) decides **when** to call these commands. OpenDream validates, extracts, consolidates, retrieves, and writes audit artifacts **once invoked**.

**Corrections vs loose descriptions elsewhere:**

- Prefer **`maintain`** as the documented maintenance entrypoint (spec **403**). The CLI may expose additional commands; treat **`maintain`** as the integration anchor.
- **First-party product surface** = this **generic CLI**. Runtime-specific hook or script glue is **operator-owned** unless you add it yourself.
- **No first-party MCP server** ships in this repo; [`docs/mcp/servers.md`](./docs/mcp/servers.md) is a template for inventorying MCP, not an OpenDream server spec.

## What’s in this repo

- `opendream/` — runtime package for events, candidates, consolidation, retrieval, and storage
- `tests/` — fixture-driven integration and validation tests
- `specs/401-autodream-style-memory-subsystem/` — canonical implementation spec
- `openspec/changes/401-autodream-style-memory-subsystem/` — proposal bundle and design artifacts
- `docs/` — repo-wide architecture and governance docs

Governance reserves `.meta/spec-adapters/` as the **preferred location for optional, non-normative** framework examples (see [`AGENTS.md`](./AGENTS.md)). Those files are **not** part of the packaged product API; `scripts/check_adapters.py` only checks that example paths and documented CLI strings stay consistent.

## Quick start (contributors)

```bash
make sync
# or: make setup
make demo
make verify
make release-check
opendream --help
```

`make sync` uses **uv** and matches CI (`uv sync --group dev`). `make setup` uses **pip** in a fresh `python3 -m venv`. Use `.venv/bin/opendream` if you skip activating the venv.

## Operator path (install + smoke)

Prefer the **console entrypoint** after install (`pyproject.toml` defines `opendream`). The **PyPI distribution**, **Python package**, and **CLI** are all named **`opendream`** (`python3 -m opendream.cli` is the module fallback if the script is not on `PATH`).

### 1. Install the console entrypoint

**PyPI (recommended once published):** install into an isolated tool environment so you avoid Homebrew’s system Python (**PEP 668**).

```bash
uv tool install opendream
# or: pipx install opendream
# or: python3 -m venv .venv && .venv/bin/pip install opendream
opendream --help
```

**Bleeding edge from Git** (same isolation; no PyPI required):

**[uv](https://docs.astral.sh/uv/guides/tools/):**

```bash
uv tool install "opendream @ git+https://github.com/pylit-ai/opendream.git"
opendream --help
```

**[pipx](https://pipx.pypa.io/):**

```bash
pipx install git+https://github.com/pylit-ai/opendream.git
opendream --help
```

To pin a branch or tag, use a PEP 508 URL suffix (e.g. `@main` or `@v0.1.0`) where your installer allows it.

**Local checkout (contributors or editable hack):** from the OpenDream root, use the repo venv (avoids `externally-managed-environment` on system `python3`):

```bash
make setup
.venv/bin/opendream --help
```

**Manual venv** (same as `make setup`, any checkout path):

```bash
cd /path/to/opendream
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/opendream --help
```

After `source .venv/bin/activate`, you can run `opendream` without the prefix.

If `python3` is missing, install Python from [python.org](https://www.python.org/downloads/) or your OS package manager. On macOS, `python` is often absent while `python3` is present.

### 2. Initialize a workspace

```bash
opendream init --workspace .tmp/ws
```

Expected: `memory/` under the workspace, including `memory/state/durable_records.json`, `memory/state/index.json`, and `memory/MEMORY.md`.

### 3. Emit one event manually

```bash
opendream emit-event \
  --workspace .tmp/ws \
  --kind project_decision \
  --content "Use pnpm in this repo" \
  --message-ref manual-1 \
  --tag key:package-manager
```

Expected: JSON with `"status": "appended"`, and new JSONL under `memory/state/events/`.

### 4. Run maintenance

```bash
opendream maintain --workspace .tmp/ws
```

Expected: JSON output with `extract.processed_events > 0` when events were pending, `consolidate.status` of `completed` or an explicit skip reason, and `memory/state/maintenance_state.json` updated when work runs. After consolidation, topic files and the startup index appear when promotion rules allow.

### 5. Prepare prompt context

```bash
opendream prepare-context \
  --workspace .tmp/ws \
  --query "package manager and workflow"
```

Expected: `selected_memory_ids`, `why`, and `prompt_context` (startup index section plus selected durable memory).

### 6. Run the repo verifiers

```bash
make verify
make release-check
```

`make verify` runs `scripts/verify.py` (Ruff lint, mypy on `opendream` and `scripts`, unit tests, `eval dream-fidelity`, adapter example integrity, packaging smoke). `make release-check` adds the full release gate (wheel/sdist, clean venv install, `dream run`, `eval dream-fidelity`, and `tests.test_release_artifact`).

**Verification limits:** This gate is **real** for CLI behavior and packaging, but it is still a **bounded** suite. It does not prove absence of every defect class you might care about in production. Treat failures as authoritative; treat PASS as “meets this repo’s bar,” not universal safety.

### Observability UI (run it yourself)

Nothing starts a browser or background server for you: **you** run the CLI on your machine. The UI reads **one** workspace’s `memory/` tree (the path you pass to `--workspace`), not every repo at once.

After install:

```bash
opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000
```

`observe serve` **blocks the terminal** until you stop it (Ctrl+C). On the same machine, open **http://127.0.0.1:8000/overview** (adjust `--port` / `--host` if needed).

More detail: [Observability web app](#observability-web-app).

## CLI

**Primary invocation** (after `pip install -e .` or `make setup`):

```bash
opendream init --workspace .tmp/workspace
opendream init --workspace ~/.opendream-global --store-kind global
opendream demo --workspace .tmp/demo
opendream bootstrap-index --workspace .tmp/workspace --events tests/fixtures/bootstrap_events.jsonl
opendream consolidate --workspace .tmp/workspace
opendream retrieve --workspace .tmp/workspace --query "package manager and workflow"
opendream emit-event --workspace .tmp/workspace --kind project_decision --content "Use pnpm in this repo" --message-ref manual-1 --tag key:package-manager
opendream maintain --workspace .tmp/workspace
opendream dream run --workspace .tmp/workspace --episodes tests/fixtures/transcript_only_dream.jsonl
opendream dream status --workspace .tmp/workspace
opendream dream tick --workspace .tmp/workspace --episodes tests/fixtures/transcript_only_dream.jsonl
opendream eval dream-fidelity --workspace .tmp/dream-eval --compat-mode autodream
opendream eval memory-quality --workspace .tmp/eval
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow"
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow" --include-global --global-workspace ~/.opendream-global
opendream status --workspace .tmp/workspace
opendream observe index --workspace .tmp/workspace
opendream observe serve --workspace .tmp/workspace --port 8000
```

**Module fallback** (editable checkout without console script on `PATH`):

```bash
python3 -m opendream.cli --help
python3 -m opendream.cli init --workspace .tmp/workspace
# …same subcommands as opendream …
```

## Verification

OpenDream is only "verified" when the scripted gate passes. The gate emits `.tmp/verification/verification_report.json` with per-stage PASS or FAIL evidence.

- `make lint` — Ruff (`scripts/lint.py`)
- `make typecheck` — mypy on `opendream` and `scripts` (`scripts/typecheck.py`)
- `make test` — unit tests
- `make verify` — `scripts/verify.py` (lint, typecheck, tests, `eval dream-fidelity`, `scripts/check_adapters.py`, packaging smoke)
- `make release-check` — authoritative release gate: artifacts, clean venv install, `dream run`, `eval dream-fidelity`, verification replay

`make release-check` emits:

- `.tmp/release-check/release_manifest.json`
- `.tmp/release-check/release_summary.md`

## Releasing (maintainers)

Publishing matches the **agentic-devkit** pattern: **tag push** runs [`.github/workflows/publish-pypi.yml`](./.github/workflows/publish-pypi.yml) (`uv build` + `uv publish`) using **PyPI Trusted Publishing (OIDC)**—no API token stored in GitHub secrets.

1. **PyPI:** Add a **trusted publisher** for `opendream`: either under an existing project’s settings, or as a **pending publisher** on your PyPI account (the project can be created on first successful OIDC publish—see [PyPI: creating a project through OIDC](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)). Use GitHub → `pylit-ai/opendream` → workflow `publish-pypi.yml` (and **environment** `pypi` if you use a GitHub Environment below).
2. **GitHub:** Create an **environment** named `pypi` (optional but recommended) with any protection rules you want; the publish workflow targets `environment: pypi`.
3. **Cut a release:** with a clean tree, run `make release-patch` (or `release-minor` / `release-major`), or bump with `make bump-patch` and push tag `vX.Y.Z` yourself. The tag must match `v[0-9]+.[0-9]+.[0-9]+`.

Local dry run: `uv build` (artifacts under `dist/`). **TestPyPI** is not wired by default; add a second job or workflow if you need it.

## Docs

- [NORTHSTAR.md](./NORTHSTAR.md)
- [PRD.md](./PRD.md)
- [CONSTITUTION.md](./CONSTITUTION.md)
- [AGENTS.md](./AGENTS.md)

## Generated data

Memory artifacts are written under a workspace-local `memory/` directory by default. Use `--memory-dir <relative-path>` when a repo needs a non-default location, and the same path is honored by direct writes, dreaming, retrieval context, and status commands.

## Runtime integration

For real agent use, treat OpenDream as a **CLI sidecar**:

- emit memory-worthy events with **`emit-event`**
- run **`maintain`** on a schedule or after sessions so extract + consolidate can run (structured skip reasons when there is nothing to do)
- run **`dream run`** against transcript or log episodes when you want reflective consolidation
- use **`dream status`** or **`dream tick`** when you want scheduler-safe DreamRunner state and backlog polling
- use **`prepare-context`** to inject selected memory into the next planning prompt
- call **`status`** when you want lock and pending-work visibility before prompting

## Layered stores

Initialize a repo-local project store and an optional user-global store:

```bash
opendream init --workspace "$PWD"
opendream init --workspace ~/.opendream-global --store-kind global
```

Route user preferences into the global store:

```bash
opendream emit-event \
  --workspace "$PWD" \
  --route global \
  --global-workspace ~/.opendream-global \
  --scope global \
  --kind preference_signal \
  --content "Prefer concise summaries across repos." \
  --message-ref manual-global-1 \
  --tag key:summary-style
```

Compose project and global context with project precedence:

```bash
opendream prepare-context \
  --workspace "$PWD" \
  --query "package manager and summary style" \
  --include-global \
  --global-workspace ~/.opendream-global
```

## Scheduler surface

**`maintain`** is the documented wrapper for repeated extract + consolidate. **`status`** exposes pending work, last run, lock state, and dream state.

```bash
opendream status --workspace "$PWD"
opendream maintain --workspace "$PWD"
```

Dream runs are explicit and bounded:

```bash
opendream dream run \
  --workspace "$PWD" \
  --episodes tests/fixtures/transcript_only_dream.jsonl \
  --compat-mode autodream

opendream dream status --workspace "$PWD" --compat-mode autodream
opendream dream tick --workspace "$PWD" --compat-mode autodream
```

Memory quality and dream fidelity can be benchmarked locally:

```bash
opendream eval dream-fidelity --workspace .tmp/dream-eval --compat-mode autodream
opendream eval memory-quality --workspace .tmp/eval
```

Cron example:

```bash
*/10 * * * * cd /path/to/repo && opendream maintain --workspace "$PWD" --include-global --global-workspace ~/.opendream-global
```

## Observability web app

OpenDream ships a local-first observability stack built from the same filesystem artifacts as the runtime. The read model is derived, provenance-preserving, and never becomes the source of truth.

**You start it locally** (see [Operator path → Observability UI](#observability-ui-run-it-yourself)). There is no hosted instance bundled with the repo.

```bash
opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000
# Then open http://127.0.0.1:8000/overview (same machine as the server).
```

The server exposes:

- a read model at `memory/state/observability_index.json`
- read APIs for overview, memories, runs, retrievals, sessions, context, graph, reviews, evals, and exports
- audited write APIs for annotations, review decisions, and exports
- SSE updates at `/api/stream/status`
- a no-build desktop-first UI at routes like `/overview`, `/memories`, `/runs`, `/retrievals`, `/sessions`, `/reviews`, `/graph`, `/evals`, and `/exports`

`prepare-context` persists context-assembly artifacts so the context viewer can reconstruct what the agent actually saw.

## Optional non-normative examples

Framework-oriented **example** snippets and scripts may live under `.meta/spec-adapters/` per [`AGENTS.md`](./AGENTS.md). They translate the **same CLI** into hook or prompt patterns; they are **not** a separate supported API. `scripts/check_adapters.py` ensures those examples stay present and reference real `opendream` subcommands.
