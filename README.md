# OpenDream

[![CI](https://github.com/pylit-ai/opendream/actions/workflows/ci.yml/badge.svg)](https://github.com/pylit-ai/opendream/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/opendream?label=PyPI)](https://pypi.org/project/opendream/)
[![Python versions](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-see%20LICENSE-lightgrey.svg)](./LICENSE)

**Local-first memory for coding agents** — activate OpenDream inside the repo you already use, let supported agent surfaces capture context locally, and keep the advanced runtime machinery available when you need it.

| If you want to… | Start here |
|-----------------|------------|
| Try it in a few commands | [Quick start](#quick-start) |
| Wire it into an agent runtime | [Integration at a glance](#integration-at-a-glance) |
| Browse memory in a browser | [Observability UI](#observability-ui) |
| Hack on the repo | [Contributing](#contributing) (expandable) |

---

## Quick start

```bash
uv tool install opendream   # or: pipx install opendream
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
opendream activate --workspace "$PWD" --repair
opendream deactivate --workspace "$PWD"
```

**PyPI can lag the README.** If `opendream init -h` does not list `--activate-configured`, or `opendream --help` has no `activate` / `deactivate` commands, upgrade from **Git** (below) or use a **local editable install** from this repository. `uv tool install opendream` only updates when a newer wheel is published.

Bleeding-edge from Git (overwrites the tool env): `uv tool install --force "opendream @ git+https://github.com/pylit-ai/opendream.git"`.

<details>
<summary><strong>Install options</strong> (venv, editable checkout, PEP 668)</summary>

**PyPI (recommended once published)** — use an isolated tool env to avoid system Python restrictions (PEP 668):

```bash
uv tool install opendream
# or: pipx install opendream
opendream --help
```

**From Git** (same idea; pin with `@main` / `@v0.1.0` where your installer allows):

```bash
uv tool install "opendream @ git+https://github.com/pylit-ai/opendream.git"
# or: pipx install git+https://github.com/pylit-ai/opendream.git
```

**Repo checkout** (contributors):

```bash
make setup
.venv/bin/opendream --help
```

Manual equivalent: `python3 -m venv .venv && .venv/bin/pip install -e .` from the repo root. Module fallback: `python3 -m opendream.cli --help`.

If `python3` is missing, install from [python.org](https://www.python.org/downloads/) or your OS package manager.

</details>

---

## Integration at a glance

OpenDream is an **activation-first CLI**. For normal use, the product contract is:

```bash
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
opendream activate --workspace "$PWD" --repair
opendream deactivate --workspace "$PWD"
```

The lower-level runtime remains available, but it is not the main mental model.

| Command | Role |
|---------|------|
| `emit-event` | Append schema-valid evidence to the store |
| `maintain` | Run extract + consolidate when work qualifies; returns structured **`status`** / **`reason`** when skipping (not a silent no-op) |
| `prepare-context` | Retrieval surface for the next task (prompt-ready output) |

Agent-oriented details (workspace vs cwd, `memory_layout`, `empty_reason` / `hints`, JSON version): [`docs/coding-agents.md`](./docs/coding-agents.md).

**Recommended activation workflow**

1. `opendream init --workspace "$PWD"` — create the memory layout.
2. `opendream activation-plan --workspace "$PWD" --targets configured` — dry-run: see which surfaces would change (no files written). Use `--targets all-supported` to preview every built-in agent target.
3. `opendream activate --workspace "$PWD" --targets configured` — apply only targets OpenDream detects (Claude/Codex/OpenClaw/Cursor/Gemini/Copilot markers in the tree). For a tool that was not detected yet, run e.g. `opendream activate --workspace "$PWD" --targets cursor` once to create `.cursor/rules/opendream.mdc` and hook scripts.
4. `opendream activate --workspace "$PWD" --repair` — restore drifted managed files and hook entries.
5. `opendream doctor --workspace "$PWD" --surface agents` — verify health before you commit.

Instruction-only targets (Cursor rules, `GEMINI.md`, `.github/copilot-instructions.md`) ship the same pre/post shell hooks as Codex; the agent must still run those commands when the host has no native OpenDream hooks.

Corrections worth knowing:

- Treat **`maintain`** as the documented maintenance entrypoint even if the CLI exposes more commands.
- **First-party surface** = this CLI. Hook/script glue is **operator-owned** unless you add it.
- **No first-party MCP server** in this repo; [`docs/mcp/servers.md`](./docs/mcp/servers.md) is a template for inventorying MCP, not a shipped server.

<details>
<summary><strong>Agent / spec cross-references</strong> (optional reading)</summary>

Human-facing behavior is described in this README and in [`AGENTS.md`](./AGENTS.md). Numbered trees under `specs/` and `openspec/changes/` (e.g. design bundles for the memory subsystem) are for **design traceability and tooling**, not required reading to use the CLI.

</details>

---

## Observability UI

Nothing starts a server unless you ask. The UI reads **one** workspace’s on-disk memory store (default relative path `.opendream/memory/` under the workspace).

```bash
opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000
```

Then open `http://127.0.0.1:8000/overview` on the same machine. `observe serve` blocks until Ctrl+C.

<details>
<summary><strong>What the observability app exposes</strong></summary>

Built from the same on-disk artifacts as the runtime (read model is derived; filesystem remains source of truth):

- Index at `.opendream/memory/state/observability_index.json` (under your configured memory root)
- Read APIs: overview, memories, runs, retrievals, sessions, context, graph, reviews, evals, exports
- Audited writes: annotations, review decisions, exports
- SSE at `/api/stream/status`
- Desktop-first routes: `/overview`, `/memories`, `/runs`, `/retrievals`, `/sessions`, `/reviews`, `/graph`, `/evals`, `/exports`

`prepare-context` persists context-assembly artifacts so the context viewer can show what the agent actually saw.

</details>

---

## Runtime integration (checklist)

Use OpenDream as an **activation-first runtime**:

- Run **`init --activate-configured`** for the standard path when the repo already has Claude Code, Codex, or OpenClaw config.
- Run **`status`** for the single high-signal answer covering activation, drift, queue state, and runtime health.
- Run **`activate --repair`** when `status` or `doctor` reports drift.
- Run **`deactivate`** if you want to remove OpenDream-managed repo-local surfaces while keeping your repo config intact.
- Use **`doctor --surface agents`**, **`service ...`**, **`dream ...`**, **`maintain`**, and **`prepare-context`** as advanced or explicit operator paths.

<details>
<summary><strong>Layered stores</strong> (project + optional global)</summary>

```bash
opendream init --workspace "$PWD"
opendream init --workspace ~/.opendream-global --store-kind global
```

Route preferences to global, then merge with project precedence via `prepare-context --include-global`:

```bash
opendream emit-event \
  --workspace "$PWD" --route global --global-workspace ~/.opendream-global \
  --scope global --kind preference_signal \
  --content "Prefer concise summaries across repos." \
  --message-ref manual-global-1 --tag key:summary-style

opendream prepare-context \
  --workspace "$PWD" --query "package manager and summary style" \
  --include-global --global-workspace ~/.opendream-global
```

</details>

<details>
<summary><strong>Advanced commands</strong></summary>

```bash
opendream status --workspace "$PWD"
opendream maintain --workspace "$PWD"
opendream activate --workspace "$PWD" --repair
opendream deactivate --workspace "$PWD"
opendream doctor --workspace "$PWD" --surface agents
```

Dream (explicit, bounded):

```bash
opendream dream run \
  --workspace "$PWD" \
  --episodes tests/fixtures/transcript_only_dream.jsonl \
  --compat-mode autodream

opendream dream status --workspace "$PWD" --compat-mode autodream
opendream dream tick --workspace "$PWD" --compat-mode autodream
opendream dream enqueue --workspace "$PWD" --episodes tests/fixtures/transcript_only_dream.jsonl
opendream dream worker --workspace "$PWD" --once
opendream dream daemon --workspace "$PWD" --interval-seconds 30 --max-polls 20
opendream install-service --workspace "$PWD" --interval-seconds 30
opendream service status --workspace "$PWD"
opendream service doctor --workspace "$PWD"
```

Use `dream worker --once` for a single queue drain inside hooks, scripts, or CI. Use `dream daemon` when a supervisor should keep polling over time. `install-service` renders launchd or systemd manifests, persists worker heartbeat state under the memory root, and exposes `service start|stop|restart|status|doctor` as a first-party lifecycle path. The default backend stays managed for portable verification; use `--backend native` when you want best-effort launchd or systemd activation.

For supported configured agents, the standard operator path is:

```bash
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
opendream activate --workspace "$PWD" --repair
opendream deactivate --workspace "$PWD"
```

Eval:

```bash
opendream eval dream-fidelity --workspace .tmp/dream-eval --compat-mode autodream
opendream eval memory-quality --workspace .tmp/eval
```

Both eval subcommands print JSON to stdout; if the report includes `"status": "failed"`, the process exits **non-zero** (typically `1`) so scripts and CI can fail the step without parsing the payload.

Cron example:

```bash
*/10 * * * * cd /path/to/repo && opendream maintain --workspace "$PWD" --include-global --global-workspace ~/.opendream-global
```

</details>

---

## Generated data

By default, durable memory artifacts live under **`.opendream/memory/`** (so a repo-root `memory/` folder stays free for other tools). If `memory/state/store.json` already exists from an older layout, that tree is used automatically until you migrate. Use `--memory-dir <relative-path>` to pin a custom location; planner plans, verifier reports, dream queue state, and worker audits live under the same memory root.

Activation and compressed-status metadata (for the standard `init --activate-configured` / `status` path) persist under **`.opendream/`** at the workspace root — notably `targets.json` and `activation-state.json`. Add `.opendream/` to `.gitignore` if you do not want those files committed.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [NORTHSTAR.md](./NORTHSTAR.md) | Product direction |
| [PRD.md](./PRD.md) | Requirements |
| [CONSTITUTION.md](./CONSTITUTION.md) | Governance |
| [AGENTS.md](./AGENTS.md) | AI assistant / agent conventions |

---

## Contributing

<details>
<summary><strong>Contributor workflow</strong></summary>

```bash
make sync    # or: make setup — uv vs pip venv
make demo
make verify
make release-check
opendream --help
```

`make sync` matches CI (`uv sync --group dev`). Use `.venv/bin/opendream` if you skip activating the venv.

</details>

<details>
<summary><strong>Step-by-step smoke test</strong> (init → emit → maintain → context)</summary>

```bash
opendream init --workspace .tmp/ws
```

Expect `.opendream/memory/` with `state/durable_records.json`, `state/index.json`, and `MEMORY.md` (paths relative to the active memory root).

```bash
opendream emit-event \
  --workspace .tmp/ws \
  --kind project_decision \
  --content "Use pnpm in this repo" \
  --message-ref manual-1 \
  --tag key:package-manager
```

Expect JSON `"status": "appended"` and new JSONL under `<memory-root>/state/events/`.

```bash
opendream maintain --workspace .tmp/ws
```

Expect JSON with `extract.processed_events > 0` when pending, `consolidate.status` completed or an explicit skip, and `<memory-root>/state/maintenance_state.json` updated when work runs.

```bash
opendream prepare-context \
  --workspace .tmp/ws \
  --query "package manager and workflow"
```

Expect `selected_memory_ids`, `why`, and `prompt_context`.

```bash
make verify
make release-check
```

**Verification limits:** The gate is real for CLI and packaging behavior but bounded. PASS means “meets this repo’s bar,” not universal safety.

</details>

<details>
<summary><strong>What’s in this repo</strong></summary>

| Path | Contents |
|------|----------|
| `opendream/` | Runtime: events, candidates, consolidation, retrieval, storage |
| `tests/` | Fixture-driven integration and validation |
| `specs/` | Canonical implementation spec tree |
| `openspec/changes/` | Proposal bundle and design artifacts |
| `docs/` | Architecture and governance |

Optional, **non-normative** framework examples may live under `.meta/spec-adapters/` (see [`AGENTS.md`](./AGENTS.md)). They are not part of the packaged product API; `scripts/check_adapters.py` keeps example paths and documented CLI strings consistent.

</details>

<details>
<summary><strong>Verification targets</strong></summary>

Authoritative when the scripted gate passes; report at `.tmp/verification/verification_report.json`.

| Target | What it runs |
|--------|----------------|
| `make lint` | Ruff (`scripts/lint.py`) |
| `make typecheck` | mypy on `opendream` and `scripts` |
| `make test` | Unit tests |
| `make verify` | Lint, typecheck, tests, `eval dream-fidelity` (fresh temp workspace), `scripts/check_adapters.py`, packaging smoke |
| `make release-check` | Release gate: artifacts, clean venv install, `dream run`, `eval dream-fidelity`, verification replay |

`make release-check` also writes `.tmp/release-check/release_manifest.json` and `release_summary.md`.

</details>

<details>
<summary><strong>Releasing (maintainers)</strong></summary>

Publishing follows the **tag push** pattern: [`.github/workflows/publish-pypi.yml`](./.github/workflows/publish-pypi.yml) runs `uv build` + `uv publish` with **PyPI Trusted Publishing (OIDC)**.

**GitHub vs PyPI binding**

- Each repo has its **own** GitHub Environment named `pypi` (the one on another org/repo does not apply here).
- On PyPI, the **opendream** project must list **repository `pylit-ai/opendream`** and workflow **`publish-pypi.yml`**. A trusted publisher row for a different repo will not publish this package.

**Checklist**

1. PyPI → **opendream** → **Publishing** → trusted publisher: owner `pylit-ai`, repository `pylit-ai/opendream`, workflow `publish-pypi.yml`, environment `pypi`.
2. GitHub → **Environments** → ensure **`pypi`** exists; add protection/reviewers if desired.
3. Bump `pyproject.toml` to a new version, then `git tag -a v0.1.0 -m "Release v0.1.0"` and `git push origin v0.1.0`, or use `make release-patch` / `release-minor` / `release-major`.

Local dry run: `uv build` → `dist/`. TestPyPI is not wired by default.

</details>

<details>
<summary><strong>Full CLI examples</strong> (copy-paste reference)</summary>

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

Module fallback:

```bash
python3 -m opendream.cli --help
```

</details>
