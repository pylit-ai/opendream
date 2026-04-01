# 02-verify-before-assert.md

## Goal
Prevent memory from confidently storing concrete claims it has not earned.

## Claim classes
- **externally checkable**: counts, path names, current framework choices, identities, current repo/layout facts, exact totals, concrete status statements
- **derived stable abstractions**: project decisions, user preferences, anti-patterns, workflow hints
- **speculative/inferred**: plausible but weakly supported summaries or future-facing hypotheses

## Provenance tiers
- `source_backed`
- `runtime_verified`
- `inferred`
- `speculative`

## Promotion rules
- externally checkable claims require `source_backed` or `runtime_verified`
- `inferred` concrete claims cannot become active truth
- `speculative` claims remain non-durable or quarantined
- verified abstractions may still be promoted if the abstraction is not simply a disguised concrete claim

## Verification reads
When verification is needed:
- perform bounded targeted reads only
- record exactly what was checked
- record success/failure and confidence impact
