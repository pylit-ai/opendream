# 06-delegated-envelope-and-ingest.md

## Goal
Normalize delegated semantic output across vendors.

## Envelope path
`.opendream/inbox/semantic/<adapter>/<ts>-<run-id>.json`

## Envelope contents
- adapter id
- execution owner
- source workspace/ref metadata
- anticipated query families
- proposed learned-context entries
- proposed emitted events
- runtime metadata
- schedule metadata
- timestamps

## Ingest behavior
- schema validate first
- archive invalid payloads
- convert accepted payloads into learned-context proposals and/or event emissions
- never bypass verification/promotion policy
- record provenance back to adapter and run id
