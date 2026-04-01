# 02-learned-context-layer.md

## New record type: learned_context

Each record stores:
- `record_id`
- `workspace_id`
- `source_event_ids`
- `source_episode_ids`
- `source_trace_ids`
- `query_family_tags`
- `summary`
- `details`
- `assumptions`
- `provider_id`
- `model_id`
- `prompt_version`
- `created_at`
- `fresh_until`
- `confidence`
- `verifier_status`
- `conflict_state`
- `superseded_by`
- `harm_signals`
- `promotion_target` (none / learned_context / durable_record)

## Storage layout

Recommended:
- `memory/state/learned_context_records.json`
- `memory/audit/semantic_dream/*.json`
- `memory/audit/semantic_verifier/*.json`
- `memory/topics/learned-context/*.md` (generated view only)

## Why separate from durable records

Learned context:
- may compress multiple facts
- may anticipate future tasks
- may contain useful but non-canonical abstractions
- may go stale faster than durable facts
- needs independent freshness and harm policy

Promoting everything directly into typed durable memory would be the exact sort of overconfidence machine people later call “stateful intelligence” with a straight face.
