# Release gates

## Primary UX
- [ ] `opendream --help` promotes init, activate, status, repair, and deactivate
- [ ] README teaches the compressed path first

## Runtime
- [ ] status aggregates activation and runtime health
- [ ] common-path activation works without daemon mental overhead

## Repair and removal
- [ ] `activate --repair` restores drift
- [ ] `deactivate` removes managed surfaces without clobbering unrelated content

## E2E
- [ ] supported target fixtures pass from the compressed standard path
