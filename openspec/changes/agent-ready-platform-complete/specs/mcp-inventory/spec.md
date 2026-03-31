# mcp-inventory/spec.md

## ADDED Requirements

### Requirement: complete MCP inventory
OpenDream MUST maintain a complete canonical inventory of MCP servers, tools, resources, prompts, trust boundaries, and revocation paths used by the repo.

#### Scenario: inspect the inventory
- **WHEN** an operator or coding agent reads `docs/mcp/servers.md`
- **THEN** each MCP surface documents auth model, exposed tools/resources, approval boundaries, failure modes, and owner
- **AND** the document is suitable for both humans and conformance checks

### Requirement: adapter/package conformance
OpenDream MUST reject adapter or package outputs that reference undeclared MCP surfaces.

#### Scenario: generate a package with an undocumented MCP
- **WHEN** a package references an MCP server absent from the canonical inventory
- **THEN** validation fails
- **AND** the error identifies the missing inventory entry
