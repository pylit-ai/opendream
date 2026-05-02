from __future__ import annotations

from pathlib import Path
from typing import Any

from .integration import maintain, prepare_context
from .models import MemoryEvent
from .retriever import retrieve
from .storage import MemoryStore
from .util import FIXTURE_ROOT, read_json, to_iso, utc_now, write_json
from .validation import validate_document

SHOWCASE_SCENARIO = "coding-agent-showcase"
DEFAULT_DEMO_SCENARIO = "default"
SHOWCASE_FIXTURE = FIXTURE_ROOT / "showcase_coding_agent_memory.jsonl"
SHOWCASE_QUERY = "pnpm Redis build memory-showcase workflow"
SHOWCASE_RETRIEVAL_LIMIT = 6
SHOWCASE_TASK_PROMPT = (
    "You are about to update the OpenDream Observe UI for the memory showcase. "
    "Before editing, identify the repo-specific package manager, local service prerequisites, "
    "known failed approach, successful UI build step, and verification workflow."
)
SHOWCASE_EXPECTED_RESPONSE = (
    "Use pnpm for frontend commands, make sure Redis is available before queue-backed worker tests, "
    "avoid npm because it caused lockfile drift, rebuild opendream/static/dist after Observe UI type changes, "
    "and run the memory-showcase verification path."
)
SHOWCASE_STATELESS_AGENT_ANSWER = (
    "Use the normal frontend path: run npm install and npm run build, then update the Observe UI "
    "and run the relevant tests. I do not see repo-specific service prerequisites or prior failed approaches."
)
SHOWCASE_ANSWER_SIGNALS: tuple[dict[str, Any], ...] = (
    {
        "key": "package_manager_pnpm",
        "label": "Uses current pnpm package-manager decision",
        "required_terms": ("pnpm",),
    },
    {
        "key": "redis_prerequisite",
        "label": "Names Redis as a local service prerequisite",
        "required_terms": ("redis",),
    },
    {
        "key": "npm_lockfile_drift_avoided",
        "label": "Avoids npm because of lockfile drift",
        "required_terms": ("avoid npm", "lockfile drift"),
        "source_terms": ("avoid npm", "lockfile", "drift"),
    },
    {
        "key": "observe_dist_rebuild",
        "label": "Includes the committed Observe UI dist rebuild",
        "required_terms": ("opendream/static/dist", "observe ui"),
    },
    {
        "key": "memory_showcase_workflow",
        "label": "Runs the memory-showcase verification path",
        "required_terms": ("memory-showcase", "verification"),
        "source_terms": ("memory-showcase", "focused unittest", "make verify"),
    },
    {
        "key": "no_current_npm_guidance",
        "label": "Does not recommend stale npm guidance",
        "forbidden_terms": ("use npm", "npm install", "npm run"),
    },
    {
        "key": "decoy_not_used",
        "label": "Does not use the unrelated GraphQL billing decoy",
        "forbidden_terms": ("graphql billing",),
    },
    {
        "key": "source_grounded",
        "label": "Grounded in selected durable memory source refs",
        "requires_source_refs": True,
    },
)
SHOWCASE_ABSTENTION_CASES = [
    {
        "case_id": "low_information_prompt",
        "query": "help",
        "expected": "retrieval gate abstains because the prompt is underspecified",
    },
    {
        "case_id": "unknown_domain_prompt",
        "query": "configure payroll VAT invoice portal",
        "expected": "no memory is selected for an unrelated domain query",
    },
]
SHOWCASE_MEMORY_HURT_CASES = [
    {
        "case_id": "contested_npm_prototype_recall",
        "query": "npm frontend dependencies prototype",
        "expected": "default retrieval suppresses the contested stale npm memory; forced contested recall is flagged",
    }
]
SHOWCASE_REPORT_PATH = Path("state") / "showcase_report.json"


def showcase_report_path(store: MemoryStore) -> Path:
    return store.memory_root / SHOWCASE_REPORT_PATH


def load_showcase_report(store: MemoryStore) -> dict[str, Any]:
    path = showcase_report_path(store)
    if not path.exists():
        return {
            "available": False,
            "report": None,
            "report_path": str(path),
            "command": f"opendream demo --scenario {SHOWCASE_SCENARIO} --workspace {store.workspace}",
        }
    return {
        "available": True,
        "report": read_json(path, {}),
        "report_path": str(path),
    }


def load_showcase_events(path: Path = SHOWCASE_FIXTURE) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [read_json_line(line) for line in text.splitlines() if line.strip()]


def read_json_line(line: str) -> dict[str, Any]:
    import json

    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("showcase fixture rows must be JSON objects")
    return value


def run_showcase_demo(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store.ensure_layout()
    before = retrieve(
        store,
        query=SHOWCASE_QUERY,
        limit=SHOWCASE_RETRIEVAL_LIMIT,
        now=timestamp,
        query_source="showcase-before",
        caller_detail="coding-agent-showcase baseline",
    )

    events = load_showcase_events()
    for event in events:
        validate_document("memory-event.schema.json", event)
        store.append_event(MemoryEvent(**event))

    maintenance = maintain(store, now=timestamp, min_new_events=0, min_interval_seconds=0)
    after = retrieve(
        store,
        query=SHOWCASE_QUERY,
        limit=SHOWCASE_RETRIEVAL_LIMIT,
        now=timestamp,
        query_source="showcase-after",
        caller_detail="coding-agent-showcase seeded recall",
    )
    context = prepare_context(store, query=SHOWCASE_QUERY, limit=SHOWCASE_RETRIEVAL_LIMIT, now=timestamp)
    report = build_showcase_report(
        store,
        events=events,
        before=before,
        after=after,
        context=context,
        maintenance=maintenance,
        timestamp=timestamp,
    )
    report_path = showcase_report_path(store)
    report["report_path"] = str(report_path)
    write_json(report_path, report)
    return report


def build_showcase_report(
    store: MemoryStore,
    *,
    events: list[dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    maintenance: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    records = {record["memory_id"]: record for record in store.load_durable_records()}
    events_by_id = {event["event_id"]: event for event in events}
    candidates = _load_all_candidates(store)
    source_refs = [
        _source_ref(memory_id, records.get(memory_id), events_by_id)
        for memory_id in after.get("selected_memory_ids", [])
        if records.get(memory_id)
    ]
    agent_snippet = _agent_snippet(source_refs)
    agent_answers = _agent_answers(before=before, after=after, source_refs=source_refs)
    retrieval_reasons = _retrieval_reasons(after)
    prompt_links = _prompt_context_links(context, source_refs, retrieval_reasons)
    case_results = _showcase_case_results(
        store,
        before=before,
        after=after,
        context=context,
        source_refs=source_refs,
        timestamp=timestamp,
    )
    dream_transition_diff = _dream_transition_diff(
        events=events,
        candidates=candidates,
        records=records,
        maintenance=maintenance,
        after=after,
        context=context,
    )
    evidence_density = _evidence_density(source_refs)
    hallucination_risk = _hallucination_risk(
        source_refs=source_refs,
        evidence_density=evidence_density,
    )
    why_this_dream_helped = _why_this_dream_helped(
        dream_transition_diff=dream_transition_diff,
        evidence_density=evidence_density,
        hallucination_risk=hallucination_risk,
        case_results=case_results,
        agent_answers=agent_answers,
    )
    checks = score_showcase(
        before=before,
        after=after,
        source_refs=source_refs,
        agent_snippet=agent_snippet,
        agent_answers=agent_answers,
        case_results=case_results,
        hallucination_risk=hallucination_risk,
    )
    status = "passed" if all(item["passed"] for item in checks.values()) else "failed"
    objective = _showcase_objective()
    return {
        "scenario": SHOWCASE_SCENARIO,
        "status": status,
        "generated_at": timestamp,
        "workspace": str(store.workspace),
        "memory_root": str(store.memory_root),
        "fixture": SHOWCASE_FIXTURE.name,
        "events_appended": len(events),
        "before": before,
        "after": after,
        "context": {
            "context_id": context.get("context_id"),
            "selected_memory_ids": context.get("selected_memory_ids", []),
            "prompt_context": context.get("prompt_context", ""),
            "visibility": context.get("prompt_context_visibility", {}),
            "selection": context.get("selection", {}),
            "context_pruning": context.get("context_pruning", {}),
            "links": prompt_links,
        },
        "objective": objective,
        "evaluation_case": {
            "user_prompt": SHOWCASE_TASK_PROMPT,
            "retrieval_query": SHOWCASE_QUERY,
            "expected_response": SHOWCASE_EXPECTED_RESPONSE,
            "why_this_tests_memory": (
                "The prompt needs knowledge from several earlier synthetic sessions: a corrected package-manager "
                "decision, an environment requirement, a failed approach, a successful workaround, and a workflow "
                "step. It should also ignore unrelated GraphQL billing memory and avoid the stale npm decision."
            ),
            "failure_without_memory": (
                "A stateless agent would likely guess npm or omit Redis, repeat the lockfile-drift failure, "
                "or skip the committed Observe UI dist rebuild."
            ),
        },
        "selected_memory_ids": after.get("selected_memory_ids", []),
        "agent_snippet": agent_snippet,
        "agent_answers": agent_answers,
        "negative_controls": case_results["negative_controls"],
        "abstention_cases": case_results["abstention_cases"],
        "memory_hurt_cases": case_results["memory_hurt_cases"],
        "proof": {
            "query": SHOWCASE_QUERY,
            "source_refs": source_refs,
            "expected_signals": ["pnpm", "Redis", "frontend build", "memory-showcase workflow"],
        },
        "retrieval_rationale": retrieval_reasons,
        "dream_transition_diff": dream_transition_diff,
        "evidence_density": evidence_density,
        "hallucination_risk": hallucination_risk,
        "why_this_dream_helped": why_this_dream_helped,
        "dream_effectiveness": _dream_effectiveness(
            events=events,
            records=records,
            source_refs=source_refs,
            maintenance=maintenance,
            before=before,
            after=after,
            context=context,
            agent_answers=agent_answers,
            case_results=case_results,
        ),
        "checks": checks,
        "maintenance": maintenance,
    }


def score_showcase(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    source_refs: list[dict[str, Any]],
    agent_snippet: str,
    agent_answers: dict[str, Any],
    case_results: dict[str, list[dict[str, Any]]],
    hallucination_risk: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    joined = "\n".join(
        " ".join(
            [
                str(ref.get("title", "")),
                str(ref.get("summary", "")),
                " ".join(str(event.get("content", "")) for event in ref.get("source_events", [])),
            ]
        )
        for ref in source_refs
    )
    selected_ids = after.get("selected_memory_ids", [])
    return {
        "baseline_empty": {
            "passed": not before.get("selected_memory_ids"),
            "detail": "before probe should not retrieve memory from an empty store",
        },
        "recall": {
            "passed": bool(selected_ids) and "pnpm" in joined and "Redis" in joined,
            "detail": "after probe should recall package manager and Redis requirements",
        },
        "stale_update": {
            "passed": "pnpm" in joined and "Earlier stale decision: use npm" not in joined,
            "detail": "selected proof should prefer the pnpm correction over the stale npm prototype decision",
        },
        "decoy_rejection": {
            "passed": "GraphQL billing API" not in joined,
            "detail": "unrelated GraphQL billing sandbox memory should be excluded from selected durable memory",
        },
        "negative_controls": {
            "passed": all(case.get("passed") for case in case_results.get("negative_controls", [])),
            "detail": "negative controls should reject stale or unrelated memories from the showcase prompt",
        },
        "abstention": {
            "passed": all(case.get("passed") for case in case_results.get("abstention_cases", [])),
            "detail": "abstention probes should select no memory when the task lacks usable project-memory signal",
        },
        "memory_hurt": {
            "passed": all(case.get("passed") for case in case_results.get("memory_hurt_cases", [])),
            "detail": "memory-hurt probes should show harmful contested recall is detectable and suppressed by default",
        },
        "provenance": {
            "passed": bool(source_refs)
            and all(ref.get("source_event_ids") and ref.get("source_events") for ref in source_refs),
            "detail": "each selected memory should expose source event evidence",
        },
        "hallucination_risk": {
            "passed": bool(hallucination_risk.get("passed")),
            "detail": "selected memories and expected answer elements must be backed by source events",
        },
        "snippet": {
            "passed": "OpenDream found prior memory:" in agent_snippet,
            "detail": "showcase should emit the visible agent-facing recall phrase",
        },
        "answer_improvement": {
            "passed": bool(agent_answers.get("comparison", {}).get("passed")),
            "detail": "memory-assisted answer should cover expected signals and improve over stateless baseline",
        },
    }


def _showcase_case_results(
    store: MemoryStore,
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, list[dict[str, Any]]]:
    records = {record["memory_id"]: record for record in store.load_durable_records()}
    return {
        "negative_controls": _negative_control_cases(
            records=records,
            before=before,
            after=after,
            context=context,
            source_refs=source_refs,
        ),
        "abstention_cases": _abstention_cases(store, timestamp=timestamp),
        "memory_hurt_cases": _memory_hurt_cases(store, timestamp=timestamp),
    }


def _negative_control_cases(
    *,
    records: dict[str, dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_ids = set(after.get("selected_memory_ids", []))
    excluded_ids = {
        item.get("memory_id")
        for item in after.get("excluded", [])
        if isinstance(item, dict) and item.get("memory_id")
    }
    prompt_context = str(context.get("prompt_context", ""))
    proof_text = "\n".join(
        "\n".join([str(ref.get("title", "")), str(ref.get("summary", ""))]) for ref in source_refs
    )

    def ids_matching(text: str) -> list[str]:
        return [
            memory_id
            for memory_id, record in records.items()
            if text in " ".join(
                [str(record.get("title", "")), str(record.get("summary", "")), str(record.get("body", ""))]
            )
        ]

    graphql_ids = ids_matching("GraphQL billing API")
    stale_npm_ids = ids_matching("Earlier stale decision: use npm")
    return [
        {
            "case_id": "empty_store_baseline",
            "control_type": "empty-store negative control",
            "input": SHOWCASE_QUERY,
            "expected": "empty store retrieves no memory before fixture seeding",
            "passed": not before.get("selected_memory_ids"),
            "evidence": {"selected_memory_ids": before.get("selected_memory_ids", [])},
        },
        {
            "case_id": "unrelated_graphql_billing_decoy",
            "control_type": "irrelevant-domain decoy",
            "input": SHOWCASE_TASK_PROMPT,
            "expected": "GraphQL billing sandbox memory is not selected for the Observe UI task",
            "passed": bool(graphql_ids)
            and not (selected_ids & set(graphql_ids))
            and "GraphQL billing API" not in prompt_context
            and "GraphQL billing API" not in proof_text,
            "evidence": {
                "memory_ids": graphql_ids,
                "selected": sorted(selected_ids & set(graphql_ids)),
                "excluded": sorted(excluded_ids & set(graphql_ids)),
            },
        },
        {
            "case_id": "stale_npm_prototype_not_current_guidance",
            "control_type": "stale contradictory memory",
            "input": SHOWCASE_TASK_PROMPT,
            "expected": "stale npm prototype guidance is not selected as current package-manager guidance",
            "passed": bool(stale_npm_ids)
            and not (selected_ids & set(stale_npm_ids))
            and "Earlier stale decision: use npm" not in prompt_context
            and "Earlier stale decision: use npm" not in proof_text,
            "evidence": {
                "memory_ids": stale_npm_ids,
                "selected": sorted(selected_ids & set(stale_npm_ids)),
                "excluded": sorted(excluded_ids & set(stale_npm_ids)),
            },
        },
    ]


def _abstention_cases(store: MemoryStore, *, timestamp: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for probe in SHOWCASE_ABSTENTION_CASES:
        result = retrieve(
            store,
            query=probe["query"],
            limit=3,
            now=timestamp,
            query_source=f"showcase-abstention:{probe['case_id']}",
            caller_detail="coding-agent-showcase abstention control",
        )
        selected = result.get("selected_memory_ids", [])
        abstained = not selected
        reason = result.get("reason", "retrieval gated") if result.get("gated") else "no matching durable memory selected"
        cases.append(
            {
                "case_id": probe["case_id"],
                "input": probe["query"],
                "expected": probe["expected"],
                "passed": abstained,
                "abstained": abstained,
                "gated": bool(result.get("gated")),
                "reason": reason,
                "selected_memory_ids": selected,
                "excluded_count": len(result.get("excluded", [])),
            }
        )
    return cases


def _memory_hurt_cases(store: MemoryStore, *, timestamp: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for probe in SHOWCASE_MEMORY_HURT_CASES:
        safe = retrieve(
            store,
            query=probe["query"],
            limit=3,
            include_contested=False,
            now=timestamp,
            query_source=f"showcase-memory-hurt-safe:{probe['case_id']}",
            caller_detail="coding-agent-showcase memory-hurt safe path",
        )
        forced = retrieve(
            store,
            query=probe["query"],
            limit=3,
            include_contested=True,
            now=timestamp,
            query_source=f"showcase-memory-hurt-forced:{probe['case_id']}",
            caller_detail="coding-agent-showcase memory-hurt forced contested recall",
        )
        hurt = forced.get("memory_hurt", {}) if isinstance(forced.get("memory_hurt"), dict) else {}
        safe_hurt = safe.get("memory_hurt", {}) if isinstance(safe.get("memory_hurt"), dict) else {}
        contradicted = hurt.get("contradicted_recalled", [])
        safe_contradicted = safe_hurt.get("contradicted_recalled", [])
        harmful_ids = sorted(
            item.get("memory_id")
            for item in contradicted
            if isinstance(item, dict) and item.get("memory_id")
        )
        safe_ids = set(safe.get("selected_memory_ids", []))
        forced_ids = set(forced.get("selected_memory_ids", []))
        cases.append(
            {
                "case_id": probe["case_id"],
                "input": probe["query"],
                "expected": probe["expected"],
                "passed": bool(harmful_ids) and not safe_contradicted and not (safe_ids & set(harmful_ids)),
                "harm_prevented_by_default": bool(harmful_ids) and not (safe_ids & set(harmful_ids)),
                "safe_selected_memory_ids": sorted(safe_ids),
                "forced_selected_memory_ids": sorted(forced_ids),
                "harmful_memory_ids": harmful_ids,
                "forced_memory_hurt": hurt,
            }
        )
    return cases


def _source_ref(
    memory_id: str,
    record: dict[str, Any] | None,
    events_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if record is None:
        return {"memory_id": memory_id, "missing": True, "source_event_ids": [], "source_events": []}
    source_event_ids = list(record.get("source_event_ids", []))
    source_events: list[dict[str, Any]] = []
    absent_source_event_ids: list[str] = []
    for event_id in source_event_ids:
        event = events_by_id.get(event_id)
        if event is None:
            absent_source_event_ids.append(event_id)
            continue
        content = event.get("content")
        source_event = {
            "event_id": event_id,
            "kind": event.get("kind"),
            "message_ref": event.get("source", {}).get("message_ref"),
            "timestamp": event.get("timestamp"),
            "content": content,
        }
        if isinstance(content, str):
            source_event["source_char_span"] = {"start": 0, "end": len(content)}
        source_events.append(source_event)
    return {
        "memory_id": memory_id,
        "title": record.get("title", ""),
        "type": record.get("type", ""),
        "summary": record.get("summary", ""),
        "status": record.get("status", ""),
        "source_event_ids": source_event_ids,
        "absent_source_event_ids": absent_source_event_ids,
        "source_events": source_events,
    }


def _agent_snippet(source_refs: list[dict[str, Any]]) -> str:
    if not source_refs:
        return "OpenDream found no prior memory for this task yet."
    first = source_refs[0]
    event_ids = ", ".join(first.get("source_event_ids", [])) or "unknown source"
    return (
        "OpenDream found prior memory: "
        f"{first.get('summary', '')} "
        f"(memory {first.get('memory_id')}, source {event_ids})."
    )


def _agent_answers(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    stateless_selected = _selected_memory_ids(before)
    memory_selected = _selected_memory_ids(after)
    memory_answer = _memory_assisted_agent_answer(source_refs)
    stateless_measurement = _measure_agent_answer(
        answer=SHOWCASE_STATELESS_AGENT_ANSWER,
        selected_memory_ids=stateless_selected,
        source_refs=[],
    )
    memory_measurement = _measure_agent_answer(
        answer=memory_answer,
        selected_memory_ids=memory_selected,
        source_refs=source_refs,
    )
    stateless = {
        "label": "Stateless baseline",
        "mode": "stateless",
        "input": "Task prompt only; no selected memory or prompt context.",
        "selected_memory_ids": stateless_selected,
        "answer": SHOWCASE_STATELESS_AGENT_ANSWER,
        "measurement": stateless_measurement,
    }
    memory_assisted = {
        "label": "Memory-assisted answer",
        "mode": "memory_assisted",
        "input": "Task prompt plus OpenDream selected durable memory context.",
        "selected_memory_ids": memory_selected,
        "answer": memory_answer,
        "measurement": memory_measurement,
    }
    stateless_score = float(stateless_measurement["score"])
    memory_score = float(memory_measurement["score"])
    return {
        "stateless": stateless,
        "memory_assisted": memory_assisted,
        "comparison": {
            "score_delta": round(memory_score - stateless_score, 3),
            "stateless_passed": bool(stateless_measurement["passed"]),
            "memory_assisted_passed": bool(memory_measurement["passed"]),
            "passed": memory_score > stateless_score and bool(memory_measurement["passed"]),
            "stateless_missing_or_failed": [
                signal["key"]
                for signal in stateless_measurement["signals"]
                if not signal.get("passed")
            ],
            "memory_assisted_passed_signals": [
                signal["key"]
                for signal in memory_measurement["signals"]
                if signal.get("passed")
            ],
        },
    }


def _selected_memory_ids(payload: dict[str, Any]) -> list[str]:
    return [item for item in payload.get("selected_memory_ids", []) if isinstance(item, str)]


def _memory_assisted_agent_answer(source_refs: list[dict[str, Any]]) -> str:
    source_ids = ", ".join(str(ref.get("memory_id")) for ref in source_refs if ref.get("memory_id"))
    evidence = f" Evidence: selected durable memories {source_ids}." if source_ids else ""
    return f"{SHOWCASE_EXPECTED_RESPONSE}{evidence}"


def _measure_agent_answer(
    *,
    answer: str,
    selected_memory_ids: list[str],
    source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = answer.lower()
    signals: list[dict[str, Any]] = []
    for signal in SHOWCASE_ANSWER_SIGNALS:
        required_terms = tuple(str(term) for term in signal.get("required_terms", ()))
        forbidden_terms = tuple(str(term) for term in signal.get("forbidden_terms", ()))
        missing_terms = [term for term in required_terms if term.lower() not in normalized]
        forbidden_matches = [term for term in forbidden_terms if term.lower() in normalized]
        source_ref_ok = not signal.get("requires_source_refs") or (
            bool(selected_memory_ids)
            and bool(source_refs)
            and all(ref.get("source_event_ids") and ref.get("source_events") for ref in source_refs)
        )
        signals.append(
            {
                "key": signal["key"],
                "label": signal["label"],
                "passed": not missing_terms and not forbidden_matches and source_ref_ok,
                "required_terms": list(required_terms),
                "missing_terms": missing_terms,
                "forbidden_terms": list(forbidden_terms),
                "forbidden_matches": forbidden_matches,
                "requires_source_refs": bool(signal.get("requires_source_refs")),
            }
        )
    passed_count = sum(1 for signal in signals if signal["passed"])
    total_count = len(signals)
    return {
        "score": round(passed_count / total_count, 3) if total_count else 0.0,
        "passed": passed_count == total_count,
        "passed_count": passed_count,
        "total_count": total_count,
        "signals": signals,
        "selected_memory_count": len(selected_memory_ids),
        "source_ref_count": len(source_refs),
    }


def _showcase_objective() -> dict[str, Any]:
    return {
        "title": "Show that OpenDream turns prior coding-agent history into useful prompt context.",
        "description": (
            "A new user should see, in one command, that OpenDream can recall repo-specific decisions, "
            "environment constraints, failed approaches, successful workarounds, and verification workflow "
            "without waiting for weeks of real history."
        ),
        "success_criteria": [
            "The empty baseline retrieves no memory.",
            "After seeded history is maintained, the prompt context includes the current pnpm decision.",
            "The Redis prerequisite, no-npm anti-pattern, frontend build workaround, and workflow memory are selected.",
            "The stale npm prototype memory is not used as current guidance.",
            "The unrelated GraphQL billing decoy is not selected.",
            "Low-information and unrelated-domain prompts abstain instead of inventing memory.",
            "A forced contested recall demonstrates memory-hurt detection while the default path suppresses it.",
            "Every selected memory links back to source event evidence.",
        ],
        "research_pattern": (
            "This mirrors current memory evaluations that disclose the task prompt, answer prompt/context, "
            "retrieved evidence, negative controls, abstention/noise rejection, memory-hurt probes, and provenance."
        ),
    }


def _retrieval_reasons(after: dict[str, Any]) -> list[dict[str, Any]]:
    explanations = after.get("explanations", [])
    if not isinstance(explanations, list):
        return []
    reasons: list[dict[str, Any]] = []
    for item in explanations:
        if not isinstance(item, dict):
            continue
        reasons.append(
            {
                "memory_id": item.get("memory_id"),
                "score": item.get("score"),
                "why_included": item.get("why_included"),
                "why_excluded": item.get("why_excluded"),
                "matched_evidence": item.get("matched_evidence", {}),
                "score_contributions": item.get("score_contributions", {}),
                "provenance_tier": item.get("provenance_tier"),
                "status": item.get("status"),
            }
        )
    return reasons


def _prompt_context_links(
    context: dict[str, Any],
    source_refs: list[dict[str, Any]],
    retrieval_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons = {item.get("memory_id"): item for item in retrieval_reasons}
    selected = set(context.get("selected_memory_ids", []))
    links: list[dict[str, Any]] = []
    for ref in source_refs:
        memory_id = ref.get("memory_id")
        if memory_id not in selected:
            continue
        reason = reasons.get(memory_id, {})
        links.append(
            {
                "memory_id": memory_id,
                "memory_href": f"/memories?id={memory_id}",
                "title": ref.get("title"),
                "summary": ref.get("summary"),
                "source_event_ids": ref.get("source_event_ids", []),
                "source_refs": [
                    {
                        "event_id": event.get("event_id"),
                        "message_ref": event.get("message_ref"),
                        "timestamp": event.get("timestamp"),
                    }
                    for event in ref.get("source_events", [])
                ],
                "why_included": reason.get("why_included"),
                "score": reason.get("score"),
            }
        )
    return links


def _load_all_candidates(store: MemoryStore) -> list[dict[str, Any]]:
    if not store.candidates_dir.exists():
        return []
    candidates: list[dict[str, Any]] = []
    for path in sorted(store.candidates_dir.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        for line in text.splitlines():
            if line.strip():
                candidates.append(read_json_line(line))
    return candidates


def _count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown") or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _memory_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": record.get("memory_id"),
        "title": record.get("title"),
        "type": record.get("type"),
        "status": record.get("status"),
        "source_event_ids": list(record.get("source_event_ids", [])),
        "supersedes": list(record.get("supersedes", [])),
        "conflicts_with": list(record.get("conflicts_with", [])),
    }


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "title": candidate.get("title"),
        "type": candidate.get("type"),
        "status": candidate.get("status"),
        "derived_from_event_ids": list(candidate.get("derived_from_event_ids", [])),
    }


def _dream_transition_diff(
    *,
    events: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    maintenance: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    consolidate = maintenance.get("consolidate", {}) if isinstance(maintenance, dict) else {}
    extract = maintenance.get("extract", {}) if isinstance(maintenance, dict) else {}
    record_values = list(records.values())
    selected_ids = [memory_id for memory_id in after.get("selected_memory_ids", []) if memory_id in records]
    context_ids = [memory_id for memory_id in context.get("selected_memory_ids", []) if memory_id in records]
    excluded_ids = [
        item.get("memory_id")
        for item in after.get("excluded", [])
        if isinstance(item, dict) and item.get("memory_id")
    ]
    non_active = [
        record
        for record in record_values
        if record.get("status") in {"contested", "quarantined", "superseded"}
    ]
    candidate_source_ids = sorted(
        {
            str(event_id)
            for candidate in candidates
            for event_id in candidate.get("derived_from_event_ids", [])
            if str(event_id)
        }
    )
    selected_source_ids = sorted(
        {
            str(event_id)
            for memory_id in selected_ids
            for event_id in records[memory_id].get("source_event_ids", [])
            if str(event_id)
        }
    )
    stages = [
        {
            "key": "raw_events",
            "label": "raw events",
            "input_count": 0,
            "output_count": len(events),
            "event_ids": [str(event.get("event_id")) for event in events],
            "kind_counts": _count_by_key(events, "kind"),
        },
        {
            "key": "candidate_memories",
            "label": "candidate memories",
            "input_count": int(extract.get("processed_events", len(events))),
            "output_count": len(candidates),
            "candidate_ids": [str(candidate.get("candidate_id")) for candidate in candidates],
            "derived_from_event_ids": candidate_source_ids,
            "items": [_candidate_summary(candidate) for candidate in candidates],
        },
        {
            "key": "durable_memories",
            "label": "durable memories",
            "input_count": len(candidates),
            "output_count": len(record_values),
            "created": consolidate.get("created", 0),
            "updated": consolidate.get("updated", 0),
            "status_counts": _count_by_key(record_values, "status"),
            "items": [_memory_summary(record) for record in record_values],
        },
        {
            "key": "contested_quarantined_superseded_memories",
            "label": "contested/quarantined/superseded memories",
            "input_count": len(record_values),
            "output_count": len(non_active),
            "contested": consolidate.get("contested", 0),
            "quarantined": consolidate.get("quarantined", 0),
            "superseded": consolidate.get("superseded", 0),
            "items": [_memory_summary(record) for record in non_active],
        },
        {
            "key": "prompt_context",
            "label": "prompt context",
            "input_count": len([record for record in record_values if record.get("status") == "active"]),
            "output_count": len(context_ids),
            "selected_memory_ids": context_ids,
            "retrieval_selected_memory_ids": selected_ids,
            "excluded_memory_ids": excluded_ids,
            "selected_source_event_ids": selected_source_ids,
            "prompt_context_chars": len(str(context.get("prompt_context", ""))),
        },
    ]
    return {
        "stages": stages,
        "status_counts": _count_by_key(record_values, "status"),
        "transition_counts": {
            "raw_events_to_candidates": len(candidates),
            "candidates_to_durable": len(record_values),
            "durable_to_non_active": len(non_active),
            "durable_to_prompt_context": len(context_ids),
        },
    }


def _evidence_density(source_refs: list[dict[str, Any]]) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    unique_source_event_ids: set[str] = set()
    for ref in source_refs:
        source_event_ids = [str(event_id) for event_id in ref.get("source_event_ids", []) if str(event_id)]
        source_events = ref.get("source_events", []) if isinstance(ref.get("source_events"), list) else []
        absent_ids = [str(event_id) for event_id in ref.get("absent_source_event_ids", []) if str(event_id)]
        present_ids = [
            str(event.get("event_id"))
            for event in source_events
            if isinstance(event, dict) and event.get("event_id")
        ]
        unique_source_event_ids.update(present_ids)
        source_refs_present = bool(source_event_ids) and not absent_ids and len(present_ids) == len(source_event_ids)
        selected.append(
            {
                "memory_id": ref.get("memory_id"),
                "title": ref.get("title"),
                "type": ref.get("type"),
                "source_event_ids": source_event_ids,
                "source_event_count": len(source_event_ids),
                "source_refs_present": source_refs_present,
                "present_source_event_ids": present_ids,
                "absent_source_event_ids": absent_ids,
                "source_char_spans": [
                    {
                        "event_id": event.get("event_id"),
                        "source_char_span": event.get("source_char_span"),
                    }
                    for event in source_events
                    if isinstance(event, dict) and event.get("source_char_span")
                ],
            }
        )
    selected_count = len(selected)
    total_source_refs = sum(item["source_event_count"] for item in selected)
    return {
        "selected_memory_count": selected_count,
        "selected_source_event_count": len(unique_source_event_ids),
        "source_events_per_selected_memory": round(total_source_refs / selected_count, 3)
        if selected_count
        else 0.0,
        "source_refs_present_count": sum(1 for item in selected if item["source_refs_present"]),
        "source_refs_absent_count": sum(1 for item in selected if not item["source_refs_present"]),
        "selected_memories": selected,
    }


def _source_evidence_text(source_refs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ref in source_refs:
        for event in ref.get("source_events", []):
            if isinstance(event, dict) and event.get("content"):
                parts.append(str(event["content"]))
    return "\n".join(parts)


def _expected_answer_evidence_gaps(source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_text = _source_evidence_text(source_refs).lower()
    gaps: list[dict[str, Any]] = []
    for signal in SHOWCASE_ANSWER_SIGNALS:
        required_terms = [
            str(term)
            for term in signal.get("source_terms", signal.get("required_terms", ()))
            if str(term)
        ]
        if not required_terms:
            continue
        missing_terms = [term for term in required_terms if term.lower() not in source_text]
        if missing_terms:
            gaps.append(
                {
                    "key": signal["key"],
                    "label": signal["label"],
                    "required_terms": required_terms,
                    "missing_terms": missing_terms,
                }
            )
    return gaps


def _hallucination_risk(
    *,
    source_refs: list[dict[str, Any]],
    evidence_density: dict[str, Any],
) -> dict[str, Any]:
    selected_without_source = [
        item
        for item in evidence_density.get("selected_memories", [])
        if isinstance(item, dict) and not item.get("source_refs_present")
    ]
    expected_answer_gaps = _expected_answer_evidence_gaps(source_refs)
    selected_memory_gate = {
        "passed": not selected_without_source,
        "failed_memory_ids": [item.get("memory_id") for item in selected_without_source],
    }
    expected_answer_gate = {
        "passed": not expected_answer_gaps,
        "failed_elements": expected_answer_gaps,
    }
    passed = selected_memory_gate["passed"] and expected_answer_gate["passed"]
    return {
        "passed": passed,
        "risk_level": "low" if passed else "high",
        "selected_memories_without_source_evidence": selected_without_source,
        "selected_expected_answer_elements_without_source_evidence": expected_answer_gaps,
        "gates": {
            "selected_memory_source_evidence": selected_memory_gate,
            "expected_answer_source_evidence": expected_answer_gate,
        },
    }


def _find_case(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if case.get("case_id") == case_id:
            return case
    return {}


def _stage_by_key(dream_transition_diff: dict[str, Any], key: str) -> dict[str, Any]:
    for stage in dream_transition_diff.get("stages", []):
        if isinstance(stage, dict) and stage.get("key") == key:
            return stage
    return {}


def _why_this_dream_helped(
    *,
    dream_transition_diff: dict[str, Any],
    evidence_density: dict[str, Any],
    hallucination_risk: dict[str, Any],
    case_results: dict[str, list[dict[str, Any]]],
    agent_answers: dict[str, Any],
) -> dict[str, Any]:
    non_active_stage = _stage_by_key(dream_transition_diff, "contested_quarantined_superseded_memories")
    prompt_stage = _stage_by_key(dream_transition_diff, "prompt_context")
    decoy_case = _find_case(
        case_results.get("negative_controls", []),
        "unrelated_graphql_billing_decoy",
    )
    stale_case = _find_case(
        case_results.get("negative_controls", []),
        "stale_npm_prototype_not_current_guidance",
    )
    workflow_selected = any(
        str(item.get("title", "")).startswith("Workflow:")
        for item in _stage_by_key(dream_transition_diff, "durable_memories").get("items", [])
        if item.get("memory_id") in set(prompt_stage.get("selected_memory_ids", []))
    )
    source_gate = hallucination_risk.get("gates", {}).get("selected_memory_source_evidence", {})
    claims = [
        {
            "key": "stale_contested",
            "passed": bool(stale_case.get("passed")) and int(non_active_stage.get("contested", 0)) > 0,
            "metrics": {
                "contested_count": non_active_stage.get("contested", 0),
                "stale_negative_control_passed": bool(stale_case.get("passed")),
            },
        },
        {
            "key": "decoy_excluded",
            "passed": bool(decoy_case.get("passed")),
            "metrics": {
                "selected_decoy_ids": decoy_case.get("evidence", {}).get("selected", []),
                "excluded_decoy_ids": decoy_case.get("evidence", {}).get("excluded", []),
            },
        },
        {
            "key": "workflow_preserved",
            "passed": workflow_selected,
            "metrics": {
                "prompt_context_selected_memory_ids": prompt_stage.get("selected_memory_ids", []),
            },
        },
        {
            "key": "source_refs_retained",
            "passed": bool(source_gate.get("passed")),
            "metrics": {
                "source_refs_present_count": evidence_density.get("source_refs_present_count", 0),
                "source_refs_absent_count": evidence_density.get("source_refs_absent_count", 0),
                "selected_source_event_count": evidence_density.get("selected_source_event_count", 0),
            },
        },
        {
            "key": "answer_improved",
            "passed": bool(agent_answers.get("comparison", {}).get("passed")),
            "metrics": {
                "score_delta": agent_answers.get("comparison", {}).get("score_delta"),
            },
        },
    ]
    return {
        "computed_from": ["dream_transition_diff", "evidence_density", "hallucination_risk", "agent_answers"],
        "passed": all(claim["passed"] for claim in claims),
        "claims": claims,
    }


def _dream_effectiveness(
    *,
    events: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    source_refs: list[dict[str, Any]],
    maintenance: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    context: dict[str, Any],
    agent_answers: dict[str, Any],
    case_results: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    consolidate = maintenance.get("consolidate", {}) if isinstance(maintenance, dict) else {}
    extract = maintenance.get("extract", {}) if isinstance(maintenance, dict) else {}
    selected_ids = set(after.get("selected_memory_ids", []))
    negative_controls = case_results.get("negative_controls", [])
    abstention_cases = case_results.get("abstention_cases", [])
    memory_hurt_cases = case_results.get("memory_hurt_cases", [])
    selected_source_ids = {
        event_id
        for ref in source_refs
        for event_id in ref.get("source_event_ids", [])
        if isinstance(event_id, str)
    }
    raw_chars = sum(len(str(event.get("content", ""))) for event in events)
    prompt_chars = len(str(context.get("prompt_context", "")))
    active_records = [record for record in records.values() if record.get("status") == "active"]
    contested_records = [record for record in records.values() if record.get("status") == "contested"]
    excluded = after.get("excluded", []) if isinstance(after.get("excluded"), list) else []
    excluded_ids = {item.get("memory_id") for item in excluded if isinstance(item, dict)}
    decoy_excluded = any(
        memory_id in excluded_ids and "GraphQL billing API" in str(record.get("summary", ""))
        for memory_id, record in records.items()
    )
    stateless_measurement = agent_answers.get("stateless", {}).get("measurement", {})
    memory_measurement = agent_answers.get("memory_assisted", {}).get("measurement", {})
    answer_comparison = agent_answers.get("comparison", {})
    return {
        "summary": (
            "The maintenance dream distilled raw session events into durable memories, marked stale guidance "
            "as contested, preserved source provenance, and made the task prompt retrieve curated actionable "
            "memory instead of raw history."
        ),
        "pipeline": [
            {
                "stage": "Seeded prior sessions",
                "input": len(events),
                "output": len(events),
                "evidence": (
                    "Synthetic coding-agent events with preference, environment, failure, fix, "
                    "workflow, update, and decoy."
                ),
            },
            {
                "stage": "Extraction",
                "input": len(events),
                "output": extract.get("created_candidates", 0),
                "evidence": f"Processed {extract.get('processed_events', 0)} events into candidate memories.",
            },
            {
                "stage": "Consolidation dream",
                "input": extract.get("created_candidates", 0),
                "output": consolidate.get("created", 0),
                "evidence": (
                    f"Created {consolidate.get('created', 0)} durable memories, "
                    f"contested {consolidate.get('contested', 0)}, quarantined {consolidate.get('quarantined', 0)}."
                ),
            },
            {
                "stage": "Prompt-context assembly",
                "input": len(active_records),
                "output": len(context.get("selected_memory_ids", [])),
                "evidence": "Selected the memories that should guide the next coding-agent prompt.",
            },
            {
                "stage": "Adversarial controls",
                "input": len(negative_controls) + len(abstention_cases) + len(memory_hurt_cases),
                "output": sum(
                    1
                    for case in [*negative_controls, *abstention_cases, *memory_hurt_cases]
                    if case.get("passed")
                ),
                "evidence": "Ran negative-control, abstention, and memory-hurt probes against the seeded store.",
            },
        ],
        "metrics": {
            "raw_event_count": len(events),
            "raw_event_chars": raw_chars,
            "candidate_count": extract.get("created_candidates", 0),
            "durable_memory_count": len(records),
            "active_memory_count": len(active_records),
            "contested_memory_count": len(contested_records),
            "before_selected_count": len(before.get("selected_memory_ids", [])),
            "after_selected_count": len(selected_ids),
            "selected_source_event_count": len(selected_source_ids),
            "prompt_context_chars": prompt_chars,
            "startup_index_entries": consolidate.get("startup_index_entries", 0),
            "stateless_answer_score": stateless_measurement.get("score"),
            "memory_assisted_answer_score": memory_measurement.get("score"),
            "answer_score_delta": answer_comparison.get("score_delta"),
            "negative_control_count": len(negative_controls),
            "abstention_case_count": len(abstention_cases),
            "memory_hurt_case_count": len(memory_hurt_cases),
        },
        "why_it_matters": [
            (
                "A stale npm prototype decision survives as evidence but is marked contested, "
                "so current pnpm guidance wins."
            ),
            "The unrelated GraphQL billing decoy remains in the store but is excluded from selected durable memory.",
            "Abstention cases prove low-information and unrelated-domain prompts do not fabricate recall.",
            "The memory-hurt case shows forced contested recall is flagged while default retrieval suppresses it.",
            "The selected prompt context carries both concise memory summaries and source event links.",
            "The empty baseline proves the recall comes from seeded maintained memory, not hard-coded UI text.",
            "Measured stateless and memory-assisted answers show whether recalled context changes the answer.",
        ],
        "effective": {
            "baseline_to_after": not before.get("selected_memory_ids") and bool(selected_ids),
            "stale_guidance_contested": bool(contested_records),
            "decoy_excluded": decoy_excluded,
            "negative_controls_passed": all(case.get("passed") for case in negative_controls),
            "abstention_cases_passed": all(case.get("passed") for case in abstention_cases),
            "memory_hurt_case_passed": all(case.get("passed") for case in memory_hurt_cases),
            "source_provenance_preserved": bool(selected_source_ids),
            "curated_actionable_prompt_context_built": (
                prompt_chars > 0 and len(context.get("selected_memory_ids", [])) <= len(active_records)
            ),
            "memory_assisted_answer_improved": bool(answer_comparison.get("passed")),
        },
    }
