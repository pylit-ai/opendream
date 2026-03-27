# License Hygiene Policy

## Decision
The AutoDream-style memory subsystem SHALL be implemented clean-room.

## Allowed inputs
The following may be used as:
- non-normative design inspiration
- sanity-check references
- prior-art review material

They SHALL NOT be required dependencies for implementation correctness.

## Reuse policy
- third-party code reuse: disabled
- third-party prompt reuse: disabled
- third-party template reuse: disabled

## Why
The reviewed repos do not provide enough uniquely valuable implementation substance to justify code inheritance.

The one repo with a clear MIT license is useful mostly for:
- backups
- dry-run
- reports
- path safety
- packaging/tests

These are trivial to reimplement independently.

The repos do not provide sufficiently strong or trustworthy implementations for:
- typed durable memory
- provenance
- contradiction handling
- supersession
- candidate/apply separation
- retrieval
- concurrency safety
- bootstrap migration

## Practical rule
If a feature can be described in plain English from first principles, implement it from the spec.
Do not port code.

## Optional acknowledgement
If desired, a non-normative docs note may mention that public OSS prior art was reviewed during design exploration.
No attribution is required for functionality implemented independently without copied expression.
