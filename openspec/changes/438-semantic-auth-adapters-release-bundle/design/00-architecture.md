# 00-architecture.md

## Architecture decision
Add an explicit **semantic execution layer** above the current semantic dreamer.

OpenDream must distinguish:

1. **Direct-provider execution**
   - OpenDream owns the model call
   - auth source is explicit provider credentials
   - best for CI, portable automation, and fully OpenDream-owned flows

2. **Vendor-delegated execution**
   - vendor runtime owns the model call
   - OpenDream owns memory, ingest, verification, and observability
   - best when the user already pays for a vendor plan and wants minimal extra setup

3. **Deterministic fallback**
   - no model call
   - no setup ambiguity
   - always available

## Principle
OpenDream must never describe a delegated run as if OpenDream itself made a direct provider call.

## Canonical execution contract
Every semantic run must produce one of:
- local semantic run report
- delegated semantic envelope
- deterministic fallback report

All three become inspectable runtime artifacts.
