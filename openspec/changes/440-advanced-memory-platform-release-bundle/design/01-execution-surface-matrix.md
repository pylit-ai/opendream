# 01-execution-surface-matrix.md

## Strategies
- `deterministic`
- `direct-provider`
- `codex-account`
- `claude-scheduled-task`
- `cursor-automation`

## Ownership model
- direct-provider => OpenDream owns the model call
- codex-account => Codex runtime owns the model call, OpenDream owns orchestration + ingest
- claude-scheduled-task => Claude runtime owns the model call, OpenDream owns orchestration + ingest
- cursor-automation => Cursor runtime owns the model call, OpenDream owns orchestration + ingest

## Recommendation order for `--prefer no-extra-key`
1. Codex account-backed trusted local/private execution
2. Claude scheduled-task delegated execution
3. Cursor account-backed automation execution
4. direct-provider if explicitly configured
5. deterministic-only fallback

## Key rule
OpenDream must never describe delegated execution as if OpenDream itself borrowed the vendor session.
