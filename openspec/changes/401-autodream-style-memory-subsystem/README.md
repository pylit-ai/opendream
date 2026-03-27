# AutoDream-Style Memory Subsystem

This OpenSpec bundle defines a clean-room implementation of a background memory subsystem for coding agents.

It is inspired by:
- public Claude Code memory behavior,
- public Claude Code changelog and background-agent capabilities,
- publicly discussed AutoDream-style consolidation patterns,
- and general OSS / research prior art on long-term agent memory.

This bundle does not require code reuse from any third-party repository.

## Design stance
- clean-room implementation
- local-first by default
- compact startup index + lazy topic loading
- append-only evidence capture
- asynchronous consolidation
- typed durable memory
- provenance-preserving mutation
- single-writer safety
- fully auditable writes

## Modes
1. bootstrap mode
   - first-time migration / indexing of messy historical memory
2. scheduled mode
   - bounded recurring consolidation of new candidates only

## Non-goals
- exact behavioral cloning of Anthropic internal heuristics
- reusing third-party prompt text or code
- broad repo mutation during memory maintenance
