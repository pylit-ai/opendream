# ADR-017: Machine-local workspace catalog and dashboard

## Status
Accepted

## Context
OpenDream is activation-first and workspace-scoped. Durable memory,
activation metadata, targets, queue state, and service artifacts all live
under the individual workspace's `.opendream/` tree. That is the correct
local-first default: a workspace is the source of truth for itself.

As operators use OpenDream across many repos, there is no first-party place
to answer basic multi-repo questions:

- which workspaces on this machine are initialized?
- which are activated right now?
- which have services installed?
- which are stale or broken?

The only honest answer today is "grep the filesystem for `.opendream/`
directories." That contradicts the North Star goal of being a default
local-first memory substrate across many repos and runtimes, and it
leaves an ergonomic gap around multi-workspace operator control.

The Constitution also requires operator control, structured observability,
local-first inspectability, no hidden remote state, and no silent
fallbacks. Any central index must strengthen those properties rather than
erode them.

## Decision
Add a **machine-local, derived** workspace catalog stored in
`~/.opendream/`:

- `~/.opendream/catalog.json` — list of known workspace entries
- `~/.opendream/roots.json` — explicit scan roots
- (optional) `~/.opendream/catalog-cache.json` — cached probe summaries

The catalog is **never canonical**. Per-workspace `.opendream/` metadata
is always the source of truth. The catalog can be rebuilt from workspace
state by running `opendream workspace scan`.

Updates happen:

1. Event-driven, when `init`, `activate`, or `install-service` succeed.
2. Explicitly, when the operator runs `opendream workspace scan
   --root <path>` or `--all-roots`.

Scans must be explicit and opt-in. There is no default whole-home crawl,
no background discovery, and no remote sync. The CLI command family
(`workspace list/inspect/scan/roots/forget/doctor`) and a `/workspaces`
dashboard route in the local web UI consume the same catalog.

Catalog update failures must be surfaced explicitly, never hidden, and
must not corrupt the primary command's return value.

## Consequences
### Easier
- `opendream workspace list` answers "which workspaces do I have?" in
  one command.
- The web UI has a central dashboard at `/workspaces` that routes into
  per-workspace views.
- Scripts can consume `workspace list --format json` and the scan report
  schema.

### Harder / intentional constraints
- We must document clearly that the catalog is a convenience index, not
  canonical state, to prevent operators from trusting it as authoritative.
- We must resist the temptation to add background scans, hidden writes,
  or remote sync. Every discovery step is operator-initiated.
- Catalog probes are read-only and bounded in what they record; secrets
  and raw memory content must never be promoted into catalog entries.

## Alternatives considered
- **Promote the catalog to canonical state.** Rejected: it would violate
  the workspace-scoped invariant and create drift any time a workspace
  is moved, deleted, or repaired outside OpenDream.
- **Rely on ad hoc filesystem search only.** Rejected: the North Star
  explicitly targets a multi-repo substrate and operators deserve
  first-party ergonomics.
- **Background scans of `$HOME` by default.** Rejected: violates the
  Constitution's operator-control and no-silent-fallback rules and
  would feel intrusive.

## References
- `openspec/changes/441-workspace-catalog-dashboard-bundle/`
- `NORTHSTAR.md`
- `CONSTITUTION.md`
- `opendream/workspace_catalog.py`
- `docs/architecture/overview.md`
