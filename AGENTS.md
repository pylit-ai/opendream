# AGENTS.md

Contributor guidance for OpenDream.

## Release Hygiene

- Keep this file and path-scoped AGENTS files release-safe.
- Do not add local machine paths, secrets, provider/account details, internal URLs, or generated local tool state here.
- Tool-specific generated surfaces belong in ignored local directories.

## Path-Scoped Guidance

- `opendream/AGENTS.md`
- `.meta/spec-adapters/AGENTS.md`
- `tests/AGENTS.md`

<!-- BEGIN OPENDREAM MANAGED BLOCK: codex -->

## OpenDream Activation

Before substantial work from the workspace root, set `OPENDREAM_QUERY` to the actual task text, then run if the hook exists:
`[ -f .opendream/hooks/codex-pre-task.sh ] && sh .opendream/hooks/codex-pre-task.sh "${OPENDREAM_QUERY:-}" || true`

If `selected_memory_ids` is non-empty, record how context was used with `opendream record-context-use` or include a terse final line such as `OpenDream context used: <ids>` / `OpenDream context ignored: <reason>`.

Before the final response from the workspace root, run if the hook exists:
`[ -f .opendream/hooks/codex-post-task.sh ] && sh .opendream/hooks/codex-post-task.sh "${OPENDREAM_SUMMARY:-Task completed.}" || true`

`opendream doctor --workspace "$PWD" --surface agents` checks managed files only.
`opendream verify activation-capture --workspace "$PWD" --targets codex` proves diagnostic memory capture.
If hooks are absent, continue and repair with `opendream activate --workspace "$PWD" --repair`, then run capture verification.

For scripted Codex entrypoints, prefer:
`sh .opendream/bin/codex-task-wrapper.sh --summary "${OPENDREAM_SUMMARY:-Task completed.}" -- <agent command>`

<!-- END OPENDREAM MANAGED BLOCK: codex -->
