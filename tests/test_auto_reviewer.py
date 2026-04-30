"""Unit tests for opendream.auto_reviewer (spec 445)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opendream.auto_reviewer import (
    AutoReviewerConfig,
    ContestedDominantRule,
    LowConfidenceAgeRule,
    StaleDiffRule,
    UnusedRetrievalRule,
    apply_recommendations,
    apply_rules,
    in_cooldown,
)
from opendream.models import Annotation, MemoryRecord, ReviewDecision
from opendream.observability import index_observability, load_or_build_index
from opendream.storage import MemoryStore


def _now() -> datetime:
    return datetime(2026, 4, 29, 12, 0, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _queue_item(memory_id: str) -> dict:
    return {
        "id": f"review:lc:{memory_id}",
        "queue_item_id": memory_id,
        "queue_item_type": "low_confidence_memory",
        "object_type": "memory",
        "object_id": memory_id,
        "reason": "low confidence durable memory",
    }


def _memory(memory_id: str, *, confidence: float, age_hours: float) -> dict:
    created_at = _iso(_now() - timedelta(hours=age_hours))
    return {
        "memory_id": memory_id,
        "confidence": confidence,
        "status": "active",
        "type": "fact",
        "created_at": created_at,
        "updated_at": created_at,
    }


class LowConfidenceAgeRuleTests(unittest.TestCase):
    def test_suppresses_low_confidence_aged_memory(self) -> None:
        item = _queue_item("mem_aged")
        memory = _memory("mem_aged", confidence=0.3, age_hours=48)
        proposals = apply_rules(
            queue=[item],
            memories=[memory],
            runs=[],
            retrievals=[],
            now=_now(),
        )
        self.assertEqual(len(proposals), 1)
        produced_item, proposal = proposals[0]
        self.assertIs(produced_item, item)
        self.assertEqual(proposal.rule_id, "low_confidence_age")
        self.assertEqual(proposal.action, "suppress")
        self.assertEqual(proposal.snapshot["confidence"], 0.3)
        self.assertGreaterEqual(proposal.snapshot["age_hours"], 47.0)

    def test_skips_recent_low_confidence_memory(self) -> None:
        # Below threshold but too young — only fires when operator explicitly
        # configures a non-zero min_age. Default age gate is 0 since the
        # queue trigger (< 0.65 confidence) already pre-filters.
        cfg = AutoReviewerConfig(low_confidence_min_age_hours=24)
        item = _queue_item("mem_young")
        memory = _memory("mem_young", confidence=0.3, age_hours=2)
        self.assertEqual(
            apply_rules(
                queue=[item], memories=[memory], runs=[], retrievals=[], config=cfg, now=_now()
            ),
            [],
        )

    def test_skips_high_confidence_memory(self) -> None:
        item = _queue_item("mem_high")
        memory = _memory("mem_high", confidence=0.9, age_hours=72)
        self.assertEqual(
            apply_rules(queue=[item], memories=[memory], runs=[], retrievals=[], now=_now()),
            [],
        )

    def test_skips_when_rule_disabled(self) -> None:
        cfg = AutoReviewerConfig(low_confidence_age_enabled=False)
        item = _queue_item("mem_disabled")
        memory = _memory("mem_disabled", confidence=0.1, age_hours=200)
        self.assertEqual(
            apply_rules(
                queue=[item], memories=[memory], runs=[], retrievals=[], config=cfg, now=_now()
            ),
            [],
        )

    def test_threshold_edge_inclusive_below(self) -> None:
        # confidence == threshold should NOT trigger (strict <)
        cfg = AutoReviewerConfig()
        item = _queue_item("mem_edge")
        memory = _memory("mem_edge", confidence=cfg.low_confidence_threshold, age_hours=48)
        self.assertEqual(
            apply_rules(
                queue=[item], memories=[memory], runs=[], retrievals=[], config=cfg, now=_now()
            ),
            [],
        )

    def test_skips_unknown_memory(self) -> None:
        item = _queue_item("missing_mem")
        # No matching memory record
        self.assertEqual(
            apply_rules(queue=[item], memories=[], runs=[], retrievals=[], now=_now()), []
        )


class CooldownTests(unittest.TestCase):
    def test_in_cooldown_within_window(self) -> None:
        cfg = AutoReviewerConfig(cooldown_hours=24)
        cooldown = {"low_confidence_age:mem_x": _iso(_now() - timedelta(hours=12))}
        self.assertTrue(
            in_cooldown(
                cooldown, rule_id="low_confidence_age", queue_item_id="mem_x", config=cfg, now=_now()
            )
        )

    def test_not_in_cooldown_after_window(self) -> None:
        cfg = AutoReviewerConfig(cooldown_hours=24)
        cooldown = {"low_confidence_age:mem_x": _iso(_now() - timedelta(hours=48))}
        self.assertFalse(
            in_cooldown(
                cooldown, rule_id="low_confidence_age", queue_item_id="mem_x", config=cfg, now=_now()
            )
        )

    def test_cooldown_blocks_apply(self) -> None:
        item = _queue_item("mem_cooled")
        memory = _memory("mem_cooled", confidence=0.2, age_hours=72)
        cooldown = {"low_confidence_age:mem_cooled": _iso(_now() - timedelta(hours=1))}
        self.assertEqual(
            apply_rules(
                queue=[item],
                memories=[memory],
                runs=[],
                retrievals=[],
                cooldown=cooldown,
                now=_now(),
            ),
            [],
        )


class ConfigTests(unittest.TestCase):
    def test_global_disabled_returns_no_proposals(self) -> None:
        cfg = AutoReviewerConfig(enabled=False)
        item = _queue_item("mem_a")
        memory = _memory("mem_a", confidence=0.1, age_hours=72)
        self.assertEqual(
            apply_rules(
                queue=[item], memories=[memory], runs=[], retrievals=[], config=cfg, now=_now()
            ),
            [],
        )

    def test_from_dict_partial(self) -> None:
        cfg = AutoReviewerConfig.from_dict(
            {"low_confidence_threshold": 0.55, "unknown_field_ignored": True}
        )
        self.assertAlmostEqual(cfg.low_confidence_threshold, 0.55)


class RuleProtocolTests(unittest.TestCase):
    def test_low_confidence_age_rule_id(self) -> None:
        self.assertEqual(LowConfidenceAgeRule().rule_id, "low_confidence_age")

    def test_contested_dominant_rule_id(self) -> None:
        self.assertEqual(ContestedDominantRule().rule_id, "contested_dominant")

    def test_stale_diff_rule_id(self) -> None:
        self.assertEqual(StaleDiffRule().rule_id, "stale_diff")

    def test_unused_retrieval_rule_id(self) -> None:
        self.assertEqual(UnusedRetrievalRule().rule_id, "unused_retrieval")


# ---------------------------------------------------------------------------
# ContestedDominantRule helpers
# ---------------------------------------------------------------------------

def _contested_queue_item(memory_id: str) -> dict:
    return {
        "id": f"review:cd:{memory_id}",
        "queue_item_id": memory_id,
        "queue_item_type": "contested_memory",
        "object_type": "memory",
        "object_id": memory_id,
        "reason": "contested memory",
    }


def _contested_memory(
    memory_id: str,
    *,
    confidence: float,
    age_hours: float,
    conflicts_with: str | None = None,
    superseded_by: str | None = None,
) -> dict:
    ts = _iso(_now() - timedelta(hours=age_hours))
    m: dict = {
        "memory_id": memory_id,
        "confidence": confidence,
        "status": "active",
        "type": "fact",
        "created_at": ts,
        "updated_at": ts,
        "contested_at": ts,
    }
    if conflicts_with:
        m["conflicts_with"] = conflicts_with
    if superseded_by:
        m["superseded_by"] = superseded_by
    return m


class ContestedDominantRuleTests(unittest.TestCase):
    def _cfg(self) -> AutoReviewerConfig:
        return AutoReviewerConfig(contested_dominant_enabled=True)

    def test_approves_dominant_side(self) -> None:
        winner = _contested_memory("mem_w", confidence=0.9, age_hours=24, conflicts_with="mem_l")
        loser = _contested_memory("mem_l", confidence=0.5, age_hours=24, conflicts_with="mem_w")
        item = _contested_queue_item("mem_w")
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(len(proposals), 1)
        _, proposal = proposals[0]
        self.assertEqual(proposal.rule_id, "contested_dominant")
        self.assertEqual(proposal.action, "approve")
        self.assertAlmostEqual(proposal.snapshot["delta"], 0.4, places=3)

    def test_skips_loser_side(self) -> None:
        winner = _contested_memory("mem_w2", confidence=0.9, age_hours=24, conflicts_with="mem_l2")
        loser = _contested_memory("mem_l2", confidence=0.5, age_hours=24, conflicts_with="mem_w2")
        item = _contested_queue_item("mem_l2")  # subject is loser
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_when_delta_too_small(self) -> None:
        # delta = 0.1 < default contested_min_delta=0.25
        winner = _contested_memory("mem_a", confidence=0.6, age_hours=24, conflicts_with="mem_b")
        loser = _contested_memory("mem_b", confidence=0.5, age_hours=24, conflicts_with="mem_a")
        item = _contested_queue_item("mem_a")
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_when_too_young(self) -> None:
        winner = _contested_memory("mem_c", confidence=0.9, age_hours=2, conflicts_with="mem_d")
        loser = _contested_memory("mem_d", confidence=0.5, age_hours=2, conflicts_with="mem_c")
        item = _contested_queue_item("mem_c")
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_when_disabled(self) -> None:
        cfg = AutoReviewerConfig(contested_dominant_enabled=False)
        winner = _contested_memory("mem_e", confidence=0.9, age_hours=24, conflicts_with="mem_f")
        loser = _contested_memory("mem_f", confidence=0.5, age_hours=24, conflicts_with="mem_e")
        item = _contested_queue_item("mem_e")
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_missing_opponent(self) -> None:
        winner = _contested_memory("mem_g", confidence=0.9, age_hours=24, conflicts_with="mem_missing")
        item = _contested_queue_item("mem_g")
        proposals = apply_rules(
            queue=[item],
            memories=[winner],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_delta_exactly_at_threshold_not_triggered(self) -> None:
        # delta == contested_min_delta should NOT trigger (strict >)
        cfg = self._cfg()
        winner = _contested_memory(
            "mem_h", confidence=0.5 + cfg.contested_min_delta, age_hours=24, conflicts_with="mem_i"
        )
        loser = _contested_memory("mem_i", confidence=0.5, age_hours=24, conflicts_with="mem_h")
        item = _contested_queue_item("mem_h")
        proposals = apply_rules(
            queue=[item],
            memories=[winner, loser],
            runs=[],
            retrievals=[],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])


# ---------------------------------------------------------------------------
# StaleDiffRule helpers
# ---------------------------------------------------------------------------

def _stale_queue_item(run_id: str, item_type: str = "large_diff") -> dict:
    return {
        "id": f"review:sd:{run_id}",
        "queue_item_id": run_id,
        "queue_item_type": item_type,
        "object_type": "run",
        "object_id": run_id,
        "reason": "large diff",
    }


def _run(run_id: str, *, age_hours: float) -> dict:
    started = _iso(_now() - timedelta(hours=age_hours))
    return {
        "run_id": run_id,
        "status": "completed",
        "started_at": started,
        "created_at": started,
    }


class StaleDiffRuleTests(unittest.TestCase):
    def _cfg(self) -> AutoReviewerConfig:
        return AutoReviewerConfig(stale_diff_enabled=True)

    def test_marks_stale_old_run(self) -> None:
        run = _run("run_old", age_hours=200)
        item = _stale_queue_item("run_old")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[run],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(len(proposals), 1)
        _, proposal = proposals[0]
        self.assertEqual(proposal.rule_id, "stale_diff")
        self.assertEqual(proposal.action, "mark_stale")
        self.assertGreater(proposal.snapshot["age_hours"], 199)

    def test_skips_recent_run(self) -> None:
        run = _run("run_new", age_hours=10)
        item = _stale_queue_item("run_new")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[run],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_applies_to_failed_run_type(self) -> None:
        run = _run("run_fail", age_hours=200)
        item = _stale_queue_item("run_fail", item_type="failed_run")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[run],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(len(proposals), 1)
        _, proposal = proposals[0]
        self.assertEqual(proposal.action, "mark_stale")

    def test_skips_when_disabled(self) -> None:
        cfg = AutoReviewerConfig(stale_diff_enabled=False)
        run = _run("run_dis", age_hours=500)
        item = _stale_queue_item("run_dis")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[run],
            retrievals=[],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_missing_run(self) -> None:
        item = _stale_queue_item("run_missing")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_threshold_edge_not_triggered(self) -> None:
        # age == threshold should NOT trigger (strict >)
        cfg = self._cfg()
        run = _run("run_edge", age_hours=cfg.large_diff_max_age_hours)
        item = _stale_queue_item("run_edge")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[run],
            retrievals=[],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])


# ---------------------------------------------------------------------------
# UnusedRetrievalRule helpers
# ---------------------------------------------------------------------------

def _retrieval_queue_item(retrieval_id: str) -> dict:
    return {
        "id": f"review:ur:{retrieval_id}",
        "queue_item_id": retrieval_id,
        "queue_item_type": "suspicious_retrieval",
        "object_type": "retrieval",
        "object_id": retrieval_id,
        "reason": "suspicious retrieval",
    }


def _retrieval(retrieval_id: str, *, age_hours: float) -> dict:
    ts = _iso(_now() - timedelta(hours=age_hours))
    return {
        "id": retrieval_id,
        "retrieved_at": ts,
        "created_at": ts,
    }


class UnusedRetrievalRuleTests(unittest.TestCase):
    def _cfg(self) -> AutoReviewerConfig:
        return AutoReviewerConfig(unused_retrieval_enabled=True)

    def test_suppresses_old_unreferenced_retrieval(self) -> None:
        ret = _retrieval("ret_old", age_hours=96)
        item = _retrieval_queue_item("ret_old")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(len(proposals), 1)
        _, proposal = proposals[0]
        self.assertEqual(proposal.rule_id, "unused_retrieval")
        self.assertEqual(proposal.action, "suppress")
        self.assertEqual(proposal.snapshot["reference_count"], 0)

    def test_skips_recent_retrieval(self) -> None:
        ret = _retrieval("ret_new", age_hours=10)
        item = _retrieval_queue_item("ret_new")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_referenced_retrieval(self) -> None:
        ret = _retrieval("ret_ref", age_hours=96)
        item = _retrieval_queue_item("ret_ref")
        context = {"retrieval_id": "ret_ref", "assembled_text": "some text"}
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            contexts=[context],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_when_disabled(self) -> None:
        cfg = AutoReviewerConfig(unused_retrieval_enabled=False)
        ret = _retrieval("ret_dis", age_hours=200)
        item = _retrieval_queue_item("ret_dis")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_skips_missing_retrieval(self) -> None:
        item = _retrieval_queue_item("ret_missing")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_threshold_edge_not_triggered(self) -> None:
        cfg = self._cfg()
        ret = _retrieval("ret_edge", age_hours=cfg.retrieval_grace_hours)
        item = _retrieval_queue_item("ret_edge")
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            config=cfg,
            now=_now(),
        )
        self.assertEqual(proposals, [])

    def test_source_retrieval_id_counts_as_reference(self) -> None:
        ret = _retrieval("ret_src", age_hours=96)
        item = _retrieval_queue_item("ret_src")
        context = {"source_retrieval_id": "ret_src"}
        proposals = apply_rules(
            queue=[item],
            memories=[],
            runs=[],
            retrievals=[ret],
            contexts=[context],
            config=self._cfg(),
            now=_now(),
        )
        self.assertEqual(proposals, [])


class ApplyRecommendationsPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="auto-reviewer-")
        self.workspace = Path(self.tmp.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.workspace)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_apply_recommendations_invalidates_stale_disk_index_after_same_day_append(self) -> None:
        now = _iso(_now())
        record = MemoryRecord(
            memory_id="mem_apply_stale",
            type="semantic_fact",
            scope="project",
            title="Low confidence memory",
            summary="Needs review",
            body="Needs review",
            status="active",
            confidence=0.2,
            salience=0.5,
            source_event_ids=[],
            supersedes=[],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=_iso(_now() - timedelta(hours=72)),
            updated_at=_iso(_now() - timedelta(hours=72)),
        )
        self.store.save_durable_records([record])

        # Existing same-day files make apply append to files instead of creating
        # them. That was the stale on-disk index path.
        self.store.append_review_decision(
            ReviewDecision(
                id="review-existing",
                queue_item_type="low_confidence_memory",
                queue_item_id="mem_already_resolved",
                action="approve",
                rationale="seed",
                actor="operator",
                created_at=now,
            )
        )
        self.store.append_annotation(
            Annotation(
                id="annotation-existing",
                object_type="memory",
                object_id="mem_already_resolved",
                actor="operator",
                label="seed",
                score=None,
                note="seed",
                created_at=now,
            )
        )

        baseline = index_observability(self.store, now=now)
        self.assertEqual(
            [item["queue_item_id"] for item in baseline["entities"]["reviews"]],
            ["mem_apply_stale"],
        )

        result = apply_recommendations(self.store, now=now)
        self.assertEqual(result["applied_count"], 1)

        rebuilt = load_or_build_index(self.store)
        self.assertEqual(rebuilt["entities"]["reviews"], [])


if __name__ == "__main__":
    unittest.main()
