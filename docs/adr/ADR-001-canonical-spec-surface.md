# ADR-001: Contract Surface and Framework Adapters

## Status
Accepted

## Context
This repository supports multiple AI coding tools and workflows. Without strict boundaries,
framework artifacts can become competing sources of requirements and increase governance drift.

## Decision
- Machine-readable contracts live in `opendream/schema/`.
- Implementation guidance lives in README, architecture docs, ADRs, and tests.
- Durable architecture decisions live in `docs/adr/`.
- Framework artifacts are optional adapters and must only translate canonical sources.
- Preferred location for framework adapter payloads is `.meta/spec-adapters/<framework>/...`.

## Consequences
- Contributors can choose workflow tooling without changing repository governance.
- Canonical requirements remain reviewable and enforceable in one place.
- CI can detect and reject normative requirement text in non-canonical locations.
