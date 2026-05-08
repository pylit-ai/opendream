# Semantic Dream Trace Runbook

Use this when a semantic dream ran but the operator needs to know whether it consumed signal, generated proposals, passed verification, or materialized learned context.

## Pipeline

1. Signal: semantic dreams read transcript episodes or explicit project events.
2. Planning: recent signal is matched against query families.
3. Synthesis: matched rows become learned-context proposals. If family matching is too weak, a bounded `recent-project-activity` fallback can propose from the most recent rows.
4. Verification: proposals run through deterministic and semantic verifier checks.
5. Materialization: approved or review-required proposals become active learned-context records.
6. Retention: stale learned context can be archived by calendar grace and optional context-activity grace.

## Trace Fields

The backend stores `semantic_trace` in the semantic dream audit summary. `/api/dream/cycles` exposes a compact `trace_summary` without raw source content.

- `signal.source`: `transcript_episodes`, `explicit_events`, or null.
- `signal.latest_timestamp`: newest consumed signal timestamp.
- `signal.rows_scanned` and `signal.rows_gathered`: input volume.
- `planner.families_considered`, `planner.families_selected`, `planner.selected_family_ids`: family planning result.
- `synthesis.family_results`: matched-row counts, proposal IDs, and drop reasons.
- `synthesis.fallback_reason`: why fallback proposal synthesis ran.
- `verification.verdict_counts`: verifier outcomes.
- `materialization.promoted_record_ids`: learned-context records created.
- `materialization.no_materialization_reason`: exact phase and reason when zero records are created.

## Checks

```bash
opendream dream run --mode semantic --workspace /path/to/workspace
opendream observe serve --host 127.0.0.1 --port 8766 --workspace /path/to/workspace
```

```bash
python - <<'PY'
from pathlib import Path
from opendream.storage import MemoryStore

store = MemoryStore(Path("/path/to/workspace"))
print(store.load_dream_state().get("last_run_summary", {}).get("semantic_trace"))
print(store.load_learned_context_records()[-3:])
PY
```

API checks while observe is serving:

```bash
python - <<'PY'
import json
import urllib.request

base = "http://127.0.0.1:8766"
cycles = json.load(urllib.request.urlopen(base + "/api/dream/cycles?limit=5"))
print(json.dumps(cycles["items"][0].get("trace_summary"), indent=2))
detail = json.load(urllib.request.urlopen(base + "/api/dream/cycles/" + cycles["items"][0]["run_id"]))
print(json.dumps(detail["summary"].get("semantic_trace"), indent=2))
PY
```

## Healthy Run

- `trace_summary.input_consumed` is true.
- `rows_scanned` is greater than zero.
- `families_selected` is greater than zero.
- `proposals_generated` is greater than zero.
- `verifier_verdicts.approve` or `verifier_verdicts.review_required` is greater than zero.
- `learned_context_created` is greater than zero.
- Dreams detail shows the same chain in the Dream trace panel.

## No-Op Runs

- `gather_recent_signal:no-signal-rows`: no transcript or explicit-event signal was available.
- `synthesize:no-row-family-token-overlap`: selected families did not match rows strongly enough.
- `synthesize:no-family-proposal`: family matching produced no proposal and fallback was unavailable.
- `synthesize:equivalent-active-learned-context`: duplicate guard suppressed a repeated equivalent cycle.
- `verify:all-proposals-rejected`: proposals existed, but verifier rejected all of them.

## Verifiers

```bash
cd /path/to/opendream
PYTHONPATH=. uv run python -m unittest tests.test_semantic_adapters tests.test_observability -v
cd frontend && pnpm build
PYTHONPATH=. uv run python scripts/verify.py
```
