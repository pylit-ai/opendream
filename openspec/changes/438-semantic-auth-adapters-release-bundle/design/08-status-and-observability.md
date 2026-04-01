# 08-status-and-observability.md

## Goal
Make semantic mode debuggable by normal operators.

## Status fields
- configured mode
- requested preference
- active execution strategy
- auth source
- candidate strategies
- degraded reasons
- last semantic owner
- last run status
- last delegated ingest status
- next scheduled action
- remediation hints

## UI/read-model
Surface:
- active semantic strategy card
- adapter health table
- delegated envelopes pending/ingested/failed
- trust-boundary notes
- links to generated setup artifacts

## Why
If the docs are finally honest but the UI still says “semantic: enabled”, operators will still infer magic.
