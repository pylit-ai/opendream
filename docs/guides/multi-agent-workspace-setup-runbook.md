# Multi-agent OpenDream workspace setup (runbook)

This document records the command sequence used to initialize OpenDream and activate supported bundled agents in a single repository workspace.

- **Example workspace (as run):** `/path/to/your/repo`
- **CLI version (as run):** `opendream <version>` (installed with `uv tool install`)
- **Date:** 2026-04-07

For product behavior and alternatives, see the repository [README](../../README.md) and [coding-agents.md](../coding-agents.md).

## Prerequisites

Install the CLI in an isolated environment (PEP 668–safe):

```bash
uv tool install opendream
# or: pipx install opendream
opendream --version
```

If flags like `activate`, `deactivate`, `semantic`, or `eval` are missing,
upgrade per the [README quick start](../../README.md#quick-start).

## Commands executed

Set the workspace to your repository root (must match the root you initialized):

```bash
export WS="/path/to/your/repo"
```

### 1. Initialize memory layout

```bash
opendream init --workspace "$WS"
```

Expected: JSON with `"status": "initialized"` and `memory_root` under `.opendream/memory` (canonical default).

### 2. (Optional) Dry-run activation per surface

```bash
opendream activation-plan --workspace "$WS" --targets claude-code
opendream activation-plan --workspace "$WS" --targets codex
opendream activation-plan --workspace "$WS" --targets cursor
opendream activation-plan --workspace "$WS" --targets gemini
```

### 3. Apply activation for supported agents

Run each target once (order does not need to match):

```bash
opendream activate --workspace "$WS" --targets claude-code
opendream activate --workspace "$WS" --targets codex
opendream activate --workspace "$WS" --targets cursor
opendream activate --workspace "$WS" --targets gemini
opendream activate --workspace "$WS" --targets github-copilot
opendream activate --workspace "$WS" --targets openclaw
```

### 4. Repair drift (idempotent)

```bash
opendream activate --workspace "$WS" --repair
```

On a clean tree this may report `"status": "noop"`.

### 5. Verify managed surfaces and capture

```bash
opendream doctor --workspace "$WS" --surface agents
opendream verify activation-capture --workspace "$WS" --targets all-supported
opendream status --workspace "$WS"
```

Expected: `doctor` reports `"status": "healthy"` for generated surfaces, `verify activation-capture` reports `"status": "passed"`, and `status` reports `"capture_verification": {"state": "passed", ...}`. Setup is not complete until capture verification passes.

## Surfaces created or updated (reference)

| Agent        | Adapter id (`--targets`) | Main managed surfaces |
|-------------|---------------------------|------------------------|
| Claude Code | `claude-code`             | `.claude/settings.json` (event-based `UserPromptSubmit` / `Stop` hooks), `.opendream/hooks/claude-pre-task.sh`, `.opendream/hooks/claude-post-task.sh` |
| Codex       | `codex`                   | `AGENTS.md` (managed OpenDream block), `.opendream/hooks/codex-*.sh`, `.opendream/bin/codex-task-wrapper.sh` |
| Cursor      | `cursor`                  | `.cursor/rules/opendream.mdc`, `.opendream/hooks/cursor-*.sh` |
| Gemini      | `gemini`                  | `GEMINI.md` (managed block), `.opendream/hooks/gemini-*.sh` |
| GitHub Copilot | `github-copilot`       | `.github/copilot-instructions.md` (managed block), `.opendream/hooks/github-copilot-*.sh` |
| OpenClaw    | `openclaw`                | `.openclaw/config.json`, `.openclaw/opendream-event-map.md`, `.opendream/hooks/openclaw-hooks.sh` |

**Instruction-only surfaces (Cursor rules, `GEMINI.md`, Copilot instructions):** the host may not run shell hooks automatically. The managed files tell the agent which `sh .opendream/hooks/...` commands to run; follow those instructions in-session. See [coding-agents.md](../coding-agents.md).

**Subdirectories:** if the agent runs with `cwd` below the repo root, set `OPENDREAM_WORKSPACE` to the workspace root so hooks target the correct store (same doc).

## Shorter alternative: all built-in targets

To activate **every** built-in adapter (includes targets beyond the four above, e.g. GitHub Copilot and OpenClaw when applicable):

```bash
opendream activate --workspace "$WS" --targets all-supported
opendream activate --workspace "$WS" --repair
opendream verify activation-capture --workspace "$WS" --targets all-supported
```

## One-liner quick path (detected agents only)

If you only want surfaces for agents OpenDream **detects** in the tree:

```bash
opendream init --workspace "$WS"
opendream activate --workspace "$WS" --repair
opendream verify activation-capture --workspace "$WS" --targets configured
opendream status --workspace "$WS"
```

For a tool that is not detected yet, use explicit `--targets <adapter-id>` as in section 3.

## Testing / confirmation

1. Re-run `opendream doctor --workspace "$WS" --surface agents` and confirm `"status": "healthy"`.
2. Run `opendream verify activation-capture --workspace "$WS" --targets configured` and confirm `"status": "passed"`.
3. In **Claude Code**, confirm hooks run (or inspect `.claude/settings.json`).
4. In **Codex**, use the wrapper / hook commands documented in the OpenDream section of `AGENTS.md`.
5. In **Cursor** / **Gemini** / **Copilot**, open the managed rule or instruction file and ensure pre/post hook commands are executed around substantive work.

Please run these checks in your environment and confirm there are no hook or permission errors in the agent logs.

---

**Web search:** For install quirks, new CLI flags, or PyPI versus git install tradeoffs, a dated search (for example `opendream pypi April 2026`) can surface recent release notes. Authoritative behavior remains this repository’s README and `opendream --help` for the version you have installed.
