# MCP servers

## Purpose

Inventory MCP (Model Context Protocol) servers, transports, tools, resources, prompts, and trust boundaries relevant to **this repository and its operator environments**.

The OpenDream **Python runtime is stdlib-only** and does not embed an MCP server. MCP integrations appear when operators attach editor- or workspace-local MCP clients (for example Cursor, Claude Desktop, or custom gateways).

## Trust model

- **Canonical docs** (`AGENTS.md`, `CONSTITUTION.md`, `docs/`) define policy. MCP tools are **capabilities**, not policy sources.
- Treat every MCP server as **operator-local configuration** unless the repo explicitly documents a first-party bundled server (none today).
- **Revocation**: disable or remove the server entry in the operator’s MCP config; rotate tokens if the server had OAuth/API access.
- **Human approval**: use server or client “approval required” settings for destructive tools (filesystem writes outside the workspace, network, shell).

## Required fields (per server)

Use this checklist when adding or reviewing a server entry below:

| Field | Meaning |
| --- | --- |
| purpose | Why the server exists for this repo/workflow |
| transport | stdio / http / ws |
| auth model | none / local-only / API key / OAuth (describe storage) |
| tools exposed | Callable surfaces agents can invoke |
| resources exposed | Optional URI patterns |
| prompts exposed | Optional prompt templates |
| human approval required for | High-risk actions |
| failure modes | Timeouts, auth expiry, partial results |
| owner | Team or role accountable |
| revocation path | How to disable and rotate secrets |
| allowed data classes | e.g. repo paths only, no production DB |

---

## In-repo runtime (default)

### opendream-cli-local

- purpose: OpenDream memory and activation commands run via **`python -m opendream.cli`** in the workspace; not an MCP server.
- transport: n/a (subprocess / CLI)
- auth model: n/a (local process)
- tools exposed: n/a
- resources exposed: n/a
- prompts exposed: n/a
- human approval required for: destructive flags on CLI (documented per command)
- failure modes: lock contention, invalid workspace path
- owner: platform
- revocation path: n/a
- allowed data classes: workspace-local files under configured memory roots

---

## Optional operator-local MCP (examples)

Configurations vary by machine. The following **patterns** are common when using AI IDEs with this repo; they are **not** pinned dependencies of OpenDream.

### cursor-workspace-mcp (example)

- purpose: Editor-provided tools (browser, fetch, repo MCP file system) configured in Cursor for the developer’s machine.
- transport: varies by bundled server
- auth model: operator credentials; often local-only
- tools exposed: per Cursor MCP configuration (see local `mcps/` descriptors if present)
- resources exposed: per server
- prompts exposed: per server
- human approval required for: network fetch, shell, file writes outside allow-listed paths
- failure modes: server not running, schema mismatch after client upgrade
- owner: operator
- revocation path: Cursor settings → disable MCP server or project
- allowed data classes: operator-defined; prefer least privilege

### claude-desktop-mcp (example)

- purpose: Optional third-party MCP servers registered in Claude Desktop.
- transport: stdio (typical)
- auth model: per-server OAuth or API keys in OS keychain
- tools exposed: per installed plugin
- human approval required for: tools that perform writes or external calls
- revocation path: remove connector in Claude Desktop; rotate OAuth app if compromised
- owner: operator

---

## Conformance (planned)

Future package generators and adapters should only reference MCP servers documented here (or explicitly marked operator-local). Undeclared references should fail verification (`436-agent-ready-platform-complete` tasks T14–T15).

## Change control

When adding a **repo-recommended** MCP integration (not just personal IDE config), update this file in the same change as adapter or docs that mention the server, and add a verification step in `make verify` or release checks.
