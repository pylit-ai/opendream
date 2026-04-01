# 04-claude-adapter.md

## Goal
Support a no-extra-key semantic path using Claude’s own scheduled-task runtime.

## Model
Claude runs the semantic refresh prompt as a scheduled task or command/skill invocation.
Claude writes a structured semantic envelope back into the repo or invokes a bounded OpenDream CLI ingest command.

## Supported submodes
- `claude-desktop-task` (preferred when local files/tools are needed)
- `claude-cloud-task` (preferred when durability matters and fresh-clone semantics are acceptable)
- GitHub Actions fallback for repo-automation contexts

## Adapter responsibilities
- scaffold command/skill/prompt files
- scaffold task text for Desktop/Cloud scheduling
- define a structured output contract
- route outputs into delegated ingest

## Key rule
OpenDream docs must describe this as **Claude-owned execution with OpenDream-owned ingest**, not as OpenDream directly using Claude account auth.

## Optional note
Channels may be referenced as an adjunct for pushing external events into a running Claude session, but they are not required for the core release adapter.
