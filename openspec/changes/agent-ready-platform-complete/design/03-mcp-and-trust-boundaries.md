# 03-mcp-and-trust-boundaries.md

## Goal
Replace the placeholder MCP inventory with a complete, enforced trust surface.

## Design
### Canonical inventory
`docs/mcp/servers.md` becomes a required machine-checkable manifest-backed doc.

### Required fields per server
- purpose
- transport
- auth model
- tools exposed
- resources exposed
- prompts exposed
- human approval required for
- failure modes
- owner
- revocation path
- allowed data classes
- package/plugin dependencies

### Enforcement
- adapter and package generators can only reference declared MCP surfaces
- conformance script fails when package manifests mention undocumented MCP servers
- docs and generated manifests must stay synchronized

## Stretch within this slice
- generate an optional JSON export of the MCP inventory for package generators and conformance tests
