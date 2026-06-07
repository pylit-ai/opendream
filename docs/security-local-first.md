# Local-First Security Model

OpenDream stores runtime memory in the selected workspace by default. It does not require a hosted account, hidden cloud memory layer, or background home-directory crawl.

The current runtime has no OpenDream Cloud upload path. Future cloud features
would be separately configured and opt-in.

## Defaults

- Workspace memory remains local unless the operator configures an external path.
- Provider-backed semantic execution is an explicit setup path.
- Machine-wide workspace discovery is opt-in through configured scan roots.
- Source links, selected context, exclusions, and review decisions remain inspectable.
- OpenDream does not ship a first-party MCP server.

## Trust Boundaries

Treat these as separate boundaries:

- **Personal:** context intended for one operator.
- **Project:** context tied to one workspace.
- **Team:** context approved for a shared workflow.
- **Path:** context relevant only to part of a repository.
- **Agent:** integration-specific instructions or generated files.
- **Provider:** data sent to an explicitly configured external model or service.

OpenDream can generate integration files and hooks, but the host controls whether and when they execute. Review generated files before enabling them in sensitive repositories.

## Operator Checks

```bash
opendream status --workspace .
opendream doctor --workspace . --surface memory
opendream doctor --workspace . --surface agents
opendream contract export --workspace . --format json
```

See [Agent Integrations](./agent-integrations.md), [Provenance](./provenance.md), and [Known Limitations](./known-limitations.md) for implementation details.
