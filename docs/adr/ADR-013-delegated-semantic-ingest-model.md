# ADR-013: Delegated semantic ingest model

## Status
Accepted

## Context
When semantic work is executed by a vendor runtime (Claude scheduled task, Cursor automation), OpenDream does not directly control the model call. Results must flow back into OpenDream through a structured, validated pathway. Without a formal envelope contract, delegated results would be loose, unvalidated files that could silently corrupt memory or bypass verification.

## Decision
Vendor-delegated semantic runs return results via a **delegated semantic envelope**:

- Envelopes are written to `.opendream/inbox/semantic/<adapter>/<timestamp>-<run-id>.json`
- Each envelope is schema-validated (`delegated-semantic-envelope.schema.json`) before any mutation
- Invalid envelopes are archived with a failure reason, never silently dropped
- Accepted envelopes are converted into learned-context proposals and/or event emissions
- Envelopes do not directly mutate durable memory; they enter the same proposal-verify-promote pipeline as direct-provider results
- Provenance links back to the originating adapter and run metadata

The ingest command is `opendream semantic ingest --workspace <ws> [--path <envelope>|--scan-inbox]`.

## Consequences
- Delegated results are inspectable and auditable before they affect memory.
- Invalid envelopes fail loudly with clear diagnostics.
- The same verification pipeline applies regardless of execution owner.
- Operators can review pending envelopes before ingesting them.
- New delegated adapters only need to write conforming envelopes; no custom ingest code required.

## Alternatives considered
- **Direct memory mutation by vendor runtimes**: rejected because it bypasses verification and audit.
- **Unstructured file drops**: rejected because they cannot be schema-validated or linked to provenance.
- **API callback from vendor to OpenDream**: rejected because it requires a running OpenDream server, which is not required for local-first usage.

## References
- `opendream/schema/delegated-semantic-envelope.schema.json`
