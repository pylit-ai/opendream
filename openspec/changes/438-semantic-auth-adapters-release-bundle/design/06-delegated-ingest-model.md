# 06-delegated-ingest-model.md

## Goal
Normalize vendor-run semantic outputs before they enter OpenDream.

## Envelope path
`.opendream/inbox/semantic/<adapter>/<timestamp>-<run-id>.json`

## Envelope contents
- adapter id
- run id
- execution owner
- repo / base ref / branch or worktree metadata
- source window summary
- anticipated query families
- proposed learned-context entries
- proposed event emissions
- verification notes from the vendor runtime if any
- model/runtime metadata
- timestamp

## Ingest rules
- validate against schema before any mutation
- archive invalid envelopes with failure reason
- do not directly modify durable memory
- convert accepted payload into:
  - learned-context proposals
  - event emissions
  - run artifacts

## Why this matters
Delegated execution is asynchronous and decoupled. Without a formal envelope, “semantic mode” degenerates into a folder full of vibes.
