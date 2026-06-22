# Contributor Reference

This guide holds contributor smoke tests, automation examples, verification targets, release notes, and full CLI examples that used to live in the README.

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
<summary><strong>Automation (managed projections)</strong> — register, run, schedule via tick</summary>

Automations are **projection jobs**: they read **durable** memories, write **typed records** under `<memory-root>/automation/`, and can appear in `prepare-context` under **Active Automation Projections** — they do **not** replace canonical durable memory.

**Playbook:** To wire skills, cron, and staleness the same way across projects (feature mining, bug radar, research deltas), follow [`docs/automation/dream-task-playbook.md`](automation/dream-task-playbook.md). Commit job specs under `docs/automation/job-specs/` or your own path and register from there.

**1. Prerequisite:** initialized store plus durable memories (same as the smoke test: `init`, ingest events, `maintain`).

**2. Job spec:** JSON validated against [`opendream/schema/automation-job.schema.json`](../opendream/schema/automation-job.schema.json). You may omit `version`, `enabled`, and timestamps; `automation register` normalizes defaults (`version`: 1, `enabled`: true, `created_at` / `updated_at`).

Example file `automation-release-watch.json` (adjust selectors to match your corpus):

```json
{
  "job_id": "release-watch",
  "title": "Release watch",
  "description": "Track release-affecting workflow signals.",
  "skill_ref": "builtin://projection-engine",
  "trigger": {"type": "interval", "interval_seconds": 3600},
  "input_selectors": {
    "memory_types_any": ["project_decision", "environment_requirement", "procedural_workflow", "user_preference"],
    "text_terms_any": ["redis", "migration"],
    "statuses_any": ["active"],
    "limit": 25
  },
  "output": {"record_type": "feature", "max_records": 10},
  "merge_policy": {"dedupe_by": "title"},
  "decay_policy": {"stale_after_runs": 3},
  "review_policy": {"require_manual_review": true, "auto_surface_limit": 3},
  "security_policy": {"allow_sensitive": false}
}
```

**3. Commands**

```bash
opendream automation register --workspace "$PWD" --spec ./automation-release-watch.json
opendream status --workspace "$PWD"
opendream automation run --workspace "$PWD" --job release-watch
opendream automation status --workspace "$PWD" --job release-watch
opendream automation review --workspace "$PWD" --job release-watch
opendream prepare-context --workspace "$PWD" --query "your task"
```

- **`opendream tick --workspace "$PWD"`** runs maintenance **and** any **due** automation jobs (interval elapsed since `last_run_at`). Use this from cron or a service alongside `maintain`.
- **`opendream automation tick`** runs **only** due automation jobs (no extract/consolidate pass).
- Use **`--now`** only for deterministic tests or scripted repros; normal operator flows should omit it.

**4. On-disk layout (under active memory root)**

| Path | Role |
|------|------|
| `automation/jobs/<job_id>.json` | Registered, schema-valid job |
| `automation/records/<record_type>/<job_id>.json` | Projection records |
| `automation/audit/` | Run reports and diffs |

**5. Tests in repo:** `tests.test_memory_cli.MemoryCliIntegrationTests.test_automation_register_run_status_and_context` and `test_automation_staleness_and_top_level_tick`. Consumer repos should run the same smoke path locally; extend CI with project-owned schema checks if the canonical backlog lives in git (see **Verification** in [`docs/automation/dream-task-playbook.md`](automation/dream-task-playbook.md)).

</details>

<details>
<summary><strong>What’s in this repo</strong></summary>

| Path | Contents |
|------|----------|
| `opendream/` | Runtime: events, candidates, consolidation, retrieval, storage |
| `tests/` | Fixture-driven integration and validation |
| `opendream/schema/` | Machine-readable runtime contracts |
| `docs/` | Architecture, governance, and user-facing guides |

Optional, **non-normative** framework examples may live under `.meta/spec-adapters/` (see [`AGENTS.md`](../AGENTS.md)). They are not part of the packaged API; `scripts/check_adapters.py` keeps example paths and documented CLI strings consistent.

</details>

<details>
<summary><strong>Verification targets</strong></summary>

Authoritative when the scripted gate passes; report at `.tmp/verification/verification_report.json`.

| Target | What it runs |
|--------|----------------|
| `make lint` | Ruff (`scripts/lint.py`) |
| `make typecheck` | mypy on `opendream` and `scripts` |
| `make test` | Unit tests |
| `make verify` | Lint, typecheck, tests, generated-state guard, `eval dream-layout` (fresh temp workspace), `scripts/check_adapters.py`, packaging smoke |
| `make release-check` | Release gate: generated-state guard, artifacts, clean venv install, `dream run`, `eval dream-layout`, verification replay |

`make release-check` also writes `.tmp/release-check/release_manifest.json` and `release_summary.md`.

</details>

<details>
<summary><strong>Releasing (maintainers)</strong></summary>

Publishing follows the **tag push** pattern: [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml) runs `uv build` + `uv publish` with **PyPI Trusted Publishing (OIDC)**.

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
opendream eval dream-layout --workspace .tmp/dream-eval --compat-mode project-user
opendream eval memory-quality --workspace .tmp/eval
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow"
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow" --include-global --global-workspace ~/.opendream-global
opendream automation register --workspace .tmp/workspace --spec ./path/to/job.json
opendream automation run --workspace .tmp/workspace --job my-job-id
opendream automation tick --workspace .tmp/workspace
opendream automation status --workspace .tmp/workspace
opendream status --workspace .tmp/workspace
opendream observe index --workspace .tmp/workspace
opendream observe serve --workspace .tmp/workspace --port 8000
```

Module fallback:

```bash
python3 -m opendream.cli --help
```

</details>
