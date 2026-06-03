# Dream Change-Point Scoring

The Dreams page uses deterministic change-point scoring to separate meaningful dream cycles from repeated no-op cycles.

## What The Score Means

Each dream cycle receives `change_point` metadata:

- `material` — the cycle changed memory/runtime state: staged memory events, generated or approved proposals, created learned context, superseded learned context, or rejected proposals.
- `failure` — the cycle failed or skipped for a non-idle reason.
- `drift` — the cycle changed observable state such as transcript count, status, reason, model, phase sequence, or funnel counts.
- `duration_anomaly` — a phase ran at least 3x slower than a baseline from prior cycles.
- `noop` — no observable dream effect.

Rows with `material`, `failure`, `drift`, or `duration_anomaly` are highlighted. Adjacent `noop` rows with the same effect signature can be collapsed.

## Fields Used

The scorer uses only fields already projected by dream cycle observability:

- `mode`, `status`, `reason`, `model_id`
- `signal_row_count`
- `phases`, `phase_durations`
- `funnel.selected`, `funnel.generated`, `funnel.approved`, `funnel.created`
- `appended_events`, `learned_context_superseded`, `proposals_rejected`

The score is deterministic and local. It does not call an LLM and does not require external services.

`funnel.selected` means query families selected for evaluation. It is useful as a drift signal, but selection alone is not a material memory change.

## Non-Goals

This is heuristic scoring, not probabilistic change-point detection such as Bayesian Online Changepoint Detection or PELT segmentation. The score identifies operator-review candidates; it does not prove a causal regime change.

## Future Work

For thousands of cycles, add a server-side digest endpoint that returns pre-grouped no-op runs plus the ranked change-point list. That keeps the UI payload small while preserving expandable evidence for each group.
