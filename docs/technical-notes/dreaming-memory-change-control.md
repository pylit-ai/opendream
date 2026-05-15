# Dreaming Memory Change Control

OpenDream treats "dreaming" as a controlled local transformation: raw events
are narrowed into candidates, reviewed against existing records, and then
materialized as durable memory only when validation passes.

## Control Flow

| Step | Input | Control | Evidence |
| --- | --- | --- | --- |
| Event capture | Local transcript, hook, or CLI event | Workspace-scoped append only | event record with source path and timestamp |
| Extraction | Candidate facts and procedures | Schema validation and provenance fields | `memory-candidate.schema.json` |
| Consolidation | Existing durable records plus candidates | Contradiction, supersession, and duplicate checks | consolidation audit diff |
| Retrieval | Query plus active memory | Selected and excluded memory lists | retrieval audit |
| Review | Release or operator check | Benchmark, showcase, and provenance gates | release manifest |

## Trust Boundaries

| Boundary | Public behavior |
| --- | --- |
| Local storage | Memory is stored under the selected workspace unless the operator chooses another memory dir. |
| Provider execution | Provider-backed semantic execution is explicit setup. Default release checks do not require API keys. |
| Release notes | Account-specific evidence, unpublished URLs, and issue-tracker writeback stay outside public artifacts. |
| Vendored assets | Offline graph assets are pinned public packages with checksums and license notices. |

## Release Review

Release review should answer four questions:

1. Does every generated or transformed memory record point back to local source evidence?
2. Do retrieval reports show both selected and excluded memory when relevant?
3. Do benchmarks state fixture scope and degraded semantic state truthfully?
4. Do release artifacts include boundary, provenance, packaging, and no-network checks?

The release gate records those answers in `.tmp/release-check/release_manifest.json`
and the release notes for the candidate version.
