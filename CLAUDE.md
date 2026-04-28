@AGENTS.md
@docs/governance/DOCS_SYSTEM.md

# OpenDream for Claude Code

Use `AGENTS.md` as the canonical routing file and `docs/governance/DOCS_SYSTEM.md` for documentation precedence.

Public release note: this repository intentionally omits generated Claude-specific packs, commands, and local backup files. Treat `.meta/spec-adapters/claude-code/` as optional examples, not policy.

<!-- metactl:begin claude-md -->
# Repository Builder

[metactl Instruction Index]|target:claude-code|policy:brownfield-safe-builder|mode:reference_index
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.
|budget:warn=8192B|max=32768B
|packs:none
<!-- metactl:end claude-md -->
