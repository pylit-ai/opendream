# Agent Memory Approaches

OpenDream is an open, local-first memory layer for AI agents. It is designed to carry useful context between sessions while keeping sources, boundaries, and memory changes visible.

| Capability | Static memory files | Generic RAG / vector DB | Hosted memory APIs | Managed product memory | OpenDream |
|------------|---------------------|-------------------------|--------------------|------------------------|-----------|
| Improves context across sessions | Manual | Depends | Yes | Yes | Yes |
| Local-first by default | Yes | Depends | No | No | Yes |
| Portable across agent runtimes | Manual copy | Custom integration | API-dependent | Usually product-bound | Yes |
| User-defined boundaries and scopes | Folder conventions | Metadata filters | API-dependent | Product-defined | Yes |
| Shows why context was recalled | No | Sometimes | Sometimes | Limited | Yes |
| Shows stale or conflicting memory | No | Limited | Limited | Limited | Yes |
| Multiple agents can contribute | Manual | Yes | Yes | Product-dependent | Yes |
| Reviewable memory updates | Manual diffs | Custom | Limited | Limited | Yes |
| Works without vendor memory lock-in | Yes | Yes | No | No | Yes |
| Public real-world benchmarks | No | Varies | Varies | Usually private | Not yet |

These are capability-level distinctions, not universal performance claims. A custom RAG system can implement many of the same controls, and hosted products vary.

OpenDream is alpha. Current evidence is strongest for local operation, context preparation, auditability, and Codex-tested workflows. Broader agent integrations and external benchmarks remain active validation areas.

## Different Jobs

- Static memory files save instructions or notes, but usually rely on manual upkeep and broad prompt inclusion.
- RAG retrieves indexed knowledge. OpenDream focuses on agent memory lifecycle: what should be saved, superseded, excluded, reviewed, and recalled.
- Hosted memory APIs provide managed storage and retrieval, with portability and policy determined by the service.
- Managed product memory is integrated into one product and may hide storage, ranking, or cleanup details.
- OpenDream keeps structured, source-linked records and prepares compact task context at retrieval time. Markdown files are optional agent-facing views, not the canonical store.

See [Dreaming Memory Change Control](./technical-notes/dreaming-memory-change-control.md) for the lifecycle and [Known Limitations](./known-limitations.md) for current boundaries.
