# Architecture

## Core pipeline
1. Extract and cluster candidates exactly as before.
2. Build a structured dream plan.
3. Run a verifier against the plan.
4. Apply only verifier-approved actions to durable memory.
5. Persist plan, verifier, mutation diff, queue state, and worker state inside the memory root.

## Runtime
- `dream enqueue` persists durable jobs.
- `dream worker` drains queued jobs and optionally falls back to transcript backlog polling.
- `dream daemon` is a CLI alias over the same worker loop.

## Trust boundary
- builtin planner and verifier stay deterministic
- optional subprocess adapters are operator-supplied and validated before use
