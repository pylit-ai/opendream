# OpenClaw adapter pack

Canonical behavior lives in `specs/404-framework-adapter-pack/`, `specs/405-layered-memory-stores/`,
`specs/418-transcript-native-dream-engine/`, `specs/420-truthful-verification-and-release/`,
`specs/430-sota-dream-runtime-bundle/`, and `README.md`.
This folder only maps that CLI into OpenClaw prompts and hook examples.

1. Prefer `opendream init --workspace "$PWD" --activate-configured` for the standard path.
2. Use `opendream status --workspace "$PWD"` for the compressed health view, then `opendream activate --workspace "$PWD" --repair` if drift appears.
3. Use `event-map.md` and the prompt snippets only as non-normative examples.
4. Set `OPENDREAM_WORKSPACE` and optional `OPENDREAM_GLOBAL_WORKSPACE`.
5. Use `opendream deactivate --workspace "$PWD"` to remove managed repo-local surfaces.

Pre-plan hook:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh pre-plan "current task"`

Post-task hook plus a one-shot dream worker poll:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh post-task "task summary"`
