# 01-semantic-sleep-time-mode.md

## Runtime modes

### deterministic
Current DreamRunner path:
- orient
- gather recent signal
- consolidate
- prune / reindex

### semantic
Semantic DreamRunner path:
- orient
- gather recent signal
- infer likely future query families
- synthesize learned-context proposals
- verify
- promote / archive
- prune / reindex

### hybrid
Run deterministic and semantic subpaths together:
- deterministic writes maintain typed durable state
- semantic writes maintain learned-context state
- retrieval uses both under attribution and freshness rules

## Defaulting policy

Release behavior:
- if a semantic provider is configured and healthy, hybrid mode is the recommended/default path
- if no semantic provider is configured, deterministic mode remains available as an offline fallback
- docs and status surfaces must make mode explicit

## Trigger policy

Semantic runs are allowed through:
- explicit `dream run --mode semantic|hybrid`
- transcript backlog ticks
- queue-backed workers
- semantic automation refresh jobs
- benchmark / release harnesses

## Cost policy

Semantic mode must support:
- provider-specific max token budget
- per-run cost cap
- per-workspace daily sleep budget
- query-family max count
- proposal count caps
- early exit on low predicted value
