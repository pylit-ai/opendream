# plan.md — 405-layered-memory-stores

## Summary
Extend the runtime from single-store operation to explicit store kinds and store groups. Keep the storage format unchanged, but add a small composition layer, precedence-aware retrieval, explicit event-routing policy, and store manifests.

## Architecture impact
- touched components:
  - `opendream_memory.storage`
  - `opendream_memory.integration`
  - `opendream_memory.cli`
  - tests and fixtures
  - `README.md`
  - `docs/adr/ADR-002-layered-memory-store-precedence.md`
- unchanged components:
  - core event, candidate, and durable schemas
  - basic filesystem store layout inside each workspace

## Data model / contract changes
- add `store_kind` metadata in `memory/state/store.json`
- add optional store-group manifest support
- no breaking schema change to `memory-event` or `memory-topic`
- composed retrieval includes source store metadata per selected memory

## Interfaces
- new and extended CLI flags:
  - `--store-kind {project,global}`
  - `--route {project,global}`
  - `--global-workspace <path>`
  - `--stores-manifest <path>`
- `prepare-context` composes store groups
- `maintain` iterates over store groups deterministically

## Precedence policy
Default precedence:
1. project
2. workspace
3. agent
4. global

Rules:
- project-local memory suppresses lower-precedence global duplicates on the same durable key
- global preferences may inform project work unless project memory already owns that key
- contested records remain excluded by default regardless of store
- global stores never silently write into project stores and vice versa

## Routing policy
Default emit behavior:
- project-scoped events go to the project store
- global preference events may go to the global store only when the operator explicitly requests it
- sensitive events must not be routed to the global store

## Observability
- retrieval output includes `store_id` and `store_kind`
- prompt context groups selected memory by source store
- maintenance summaries are store-specific and aggregate-capable

## Rollout
1. add spec and registry entry
2. implement store metadata and store-group composition
3. extend CLI and integration surfaces
4. add multi-store tests and docs
5. rerun `make verify`

## Rollback
1. remove store-group features
2. keep project-local store behavior unchanged

## Verification plan
- run: `make test`
- run: `make verify`
- manual checks:
  - initialize a project store and a global store
  - write preferences to the global store
  - write repo decisions to the project store
  - confirm precedence in composed `prepare-context`

## ADR needed?
- yes
- completed as `docs/adr/ADR-002-layered-memory-store-precedence.md`
