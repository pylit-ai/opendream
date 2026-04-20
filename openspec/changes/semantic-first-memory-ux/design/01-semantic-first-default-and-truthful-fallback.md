# 01-semantic-first-default-and-truthful-fallback.md

## Goal

Make semantic-first the default product posture without allowing the runtime to imply semantic capability that does not exist.

## Required contract

- `opendream init --workspace ... --activate-configured` and `opendream activate --workspace ...` MUST run semantic readiness detection as part of the normal path.
- top-level `status` MUST report:
  - `product_posture`
  - `semantic_capability_state`
  - `active_execution_strategy`
  - `degraded_reason` when applicable
  - one recommended next action
- `semantic_capability_state` MUST distinguish:
  - `ready`
  - `degraded`
  - `disabled_by_choice`
- a workspace MUST NOT present itself as semantic-ready unless a supported semantic execution path and return path are both available.

## Truthful fallback rules

- semantic-first posture MAY degrade to deterministic capture, but the degraded state MUST remain visible in status, doctor, contract export, and UI.
- deterministic-only by choice MUST remain available and MUST be shown differently from degraded semantic.
- unsupported strategies MUST remain visible as unsupported rather than silently disappearing.

## Operator language

The normal-path language should answer:
1. what OpenDream is trying to do,
2. what it is actually doing right now,
3. what is blocking a stronger semantic path,
4. what single action would improve the state.

This keeps semantic-first honest while still making it the default recommendation.
