# Spec adapters — agents

## Purpose

Framework-specific adapter payloads under `.meta/spec-adapters/` (Codex, Claude Code, OpenClaw, etc.). These are **non-canonical translations** of repo policy.

## Rules

- Do **not** introduce new policy here; point back to `AGENTS.md`, `README.md`, and `docs/`.
- Changes should remain **thin**: snippets, hooks, skills that reference canonical docs.
- When adding adapter files that mention MCP servers or external tools, ensure `docs/mcp/servers.md` lists those surfaces (or states they are operator-local only).

## Related

- Root `AGENTS.md` — canonical vs adapters
- `docs/architecture/overview.md` — architecture overview
