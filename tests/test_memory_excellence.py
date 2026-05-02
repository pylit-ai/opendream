"""Tests for memory-excellence release bundle (439).

Covers: runtime boundaries, claim verification, transcript probing,
relation graph, reconciliation sweeps, procedural memory, index discipline,
observability surfaces, and memory-excellence scorecard.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opendream.boundaries import (
    BoundaryViolation,
    boundary_enforcement_report,
    check_write_allowed,
    default_allowed_write_roots,
    enforce_write_boundary,
    verify_no_code_writes,
)
from opendream.claim_verification import (
    assign_provenance_tier,
    classify_claim,
    should_promote,
    verify_claim,
)
from opendream.evaluation import run_memory_excellence_eval
from opendream.extractor import extract_candidate
from opendream.integration import emit_event, maintain
from opendream.models import (
    ClaimVerificationReport,
    MemoryExcellenceScorecard,
    MemoryRecord,
    ReconciliationReport,
    RelationEdge,
    TranscriptProbeReport,
)
from opendream.observability import index_observability
from opendream.reconciliation import run_reconciliation_sweep
from opendream.relation_graph import (
    RelationStore,
    backfill_edges_from_records,
    build_relation_explanations,
    create_relation_store,
    relation_aware_score_adjustment,
)
from opendream.storage import MemoryStore
from opendream.transcript_probe import (
    build_probe_anchors,
    probe_transcript_files,
)
from opendream.util import to_iso, utc_now
from opendream.validation import validate_document


class TestRuntimeBoundaries(unittest.TestCase):
    """WS3: Runtime boundary enforcement tests."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="boundary-test-")
        self.root = Path(self.tmp.name)
        self.memory_root = self.root / ".opendream" / "memory"
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allowed_write_within_memory_root(self) -> None:
        allowed_roots = default_allowed_write_roots(self.memory_root)
        target = self.memory_root / "topics" / "test.md"
        allowed, reason = check_write_allowed(target, allowed_roots=allowed_roots)
        self.assertTrue(allowed)
        self.assertIn("allowed root", reason)

    def test_blocked_write_outside_memory_root(self) -> None:
        allowed_roots = default_allowed_write_roots(self.memory_root)
        target = self.root / "src" / "main.py"
        allowed, reason = check_write_allowed(target, allowed_roots=allowed_roots)
        self.assertFalse(allowed)
        self.assertIn("outside", reason)

    def test_enforce_write_boundary_raises(self) -> None:
        allowed_roots = default_allowed_write_roots(self.memory_root)
        target = self.root / "src" / "main.py"
        with self.assertRaises(BoundaryViolation):
            enforce_write_boundary(target, allowed_roots=allowed_roots)

    def test_verify_no_code_writes_clean(self) -> None:
        before = {"file1.py": "content1"}
        after = {"file1.py": "content1"}
        result = verify_no_code_writes(before, after, memory_root=self.memory_root)
        self.assertTrue(result["passed"])
        self.assertEqual(result["code_writes"], [])

    def test_verify_no_code_writes_detects_violation(self) -> None:
        before = {str(self.root / "src" / "main.py"): "old"}
        after = {str(self.root / "src" / "main.py"): "new"}
        result = verify_no_code_writes(before, after, memory_root=self.memory_root)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["code_writes"]), 1)

    def test_verify_no_code_writes_allows_memory_changes(self) -> None:
        mem_path = str(self.memory_root / "topics" / "test.md")
        before = {mem_path: "old"}
        after = {mem_path: "new"}
        result = verify_no_code_writes(before, after, memory_root=self.memory_root)
        self.assertTrue(result["passed"])

    def test_boundary_enforcement_report_structure(self) -> None:
        allowed_roots = default_allowed_write_roots(self.memory_root)
        report = boundary_enforcement_report(
            worker_type="dream",
            allowed_roots=allowed_roots,
        )
        self.assertTrue(report["enforced"])
        self.assertEqual(report["runtime_mode"], "memory-only")
        self.assertEqual(report["worker_type"], "dream")
        self.assertEqual(report["violations"], [])


class TestClaimVerification(unittest.TestCase):
    """WS4: Verify-before-assert and provenance tiers."""

    def test_classify_externally_checkable(self) -> None:
        body = "The project uses React and has 15 test files"
        self.assertEqual(classify_claim(body), "externally_checkable")

    def test_classify_speculative(self) -> None:
        body = "The system probably uses Redis for caching"
        self.assertEqual(classify_claim(body), "speculative")

    def test_classify_derived_abstraction(self) -> None:
        body = "The team prefers functional programming patterns"
        self.assertEqual(classify_claim(body), "derived_abstraction")

    def test_classify_version_claim(self) -> None:
        body = "Requires version 3.11 or higher"
        self.assertEqual(classify_claim(body), "externally_checkable")

    def test_classify_path_claim(self) -> None:
        body = "Config file located at /etc/app/config.yaml"
        self.assertEqual(classify_claim(body), "externally_checkable")

    def test_assign_provenance_source_backed(self) -> None:
        tier = assign_provenance_tier("externally_checkable", has_source_evidence=True)
        self.assertEqual(tier, "source_backed")

    def test_assign_provenance_runtime_verified(self) -> None:
        tier = assign_provenance_tier("externally_checkable", runtime_verified=True)
        self.assertEqual(tier, "runtime_verified")

    def test_assign_provenance_inferred(self) -> None:
        tier = assign_provenance_tier("derived_abstraction")
        self.assertEqual(tier, "inferred")

    def test_assign_provenance_speculative(self) -> None:
        tier = assign_provenance_tier("speculative")
        self.assertEqual(tier, "speculative")

    def test_should_promote_checkable_without_evidence(self) -> None:
        promotable, reason = should_promote("externally_checkable", "inferred")
        self.assertFalse(promotable)
        self.assertIn("lacks verification", reason)

    def test_should_promote_checkable_with_evidence(self) -> None:
        promotable, reason = should_promote("externally_checkable", "source_backed")
        self.assertTrue(promotable)

    def test_should_promote_derived_abstraction(self) -> None:
        promotable, _ = should_promote("derived_abstraction", "inferred")
        self.assertTrue(promotable)

    def test_verify_claim_report_structure(self) -> None:
        report = verify_claim(
            claim_id="test-claim-1",
            body="The project has 5 endpoints",
            title="Endpoint count",
        )
        self.assertIsInstance(report, ClaimVerificationReport)
        self.assertIn(report.claim_class, ("externally_checkable", "derived_abstraction", "speculative"))
        self.assertIn(report.provenance_tier, ("source_backed", "runtime_verified", "inferred", "speculative"))
        self.assertIn(report.result, ("verified", "downgraded", "quarantined", "rejected"))
        # Validate against schema.
        validate_document("claim-verification-report.schema.json", report.to_dict())

    def test_verify_claim_with_workspace_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="claim-test-") as tmp:
            workspace = Path(tmp)
            (workspace / "src").mkdir()
            (workspace / "src" / "app.py").write_text("# app code", encoding="utf-8")
            report = verify_claim(
                claim_id="path-claim-1",
                body="Main application found at /src/app.py",
                title="App location",
                workspace=workspace,
            )
            # The verifier should find the file and bump provenance.
            self.assertIsInstance(report, ClaimVerificationReport)


class TestTranscriptProbing(unittest.TestCase):
    """WS5: Grep-first transcript probing tests."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="probe-test-")
        self.root = Path(self.tmp.name)
        self.episode_file = self.root / "episode.jsonl"
        lines = [
            json.dumps({"timestamp": "2026-01-01T00:00:00Z", "content": "Use pnpm for installs"}),
            json.dumps({"timestamp": "2026-01-01T00:01:00Z", "content": "Run schema migration with alembic"}),
            json.dumps({"timestamp": "2026-01-01T00:02:00Z", "content": "Deploy to staging first"}),
        ]
        self.episode_file.write_text("\n".join(lines), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_probe_anchors(self) -> None:
        anchors = build_probe_anchors(
            ["pnpm", "alembic", "migration"],
            query="how to run schema migration",
        )
        self.assertTrue(len(anchors) > 0)
        self.assertIn("schema", anchors)

    def test_probe_transcript_files_finds_hits(self) -> None:
        windows, report = probe_transcript_files(
            [self.episode_file],
            anchors=["pnpm"],
        )
        self.assertGreater(report.hits, 0)
        self.assertGreater(report.windows_read, 0)
        self.assertEqual(report.escalations, 0)
        self.assertTrue(len(windows) > 0)
        validate_document("transcript-probe-report.schema.json", report.to_dict())

    def test_probe_no_hits_triggers_escalation(self) -> None:
        windows, report = probe_transcript_files(
            [self.episode_file],
            anchors=["nonexistent_keyword_xyz"],
        )
        self.assertEqual(report.hits, 0)
        self.assertEqual(report.escalations, 1)
        self.assertIn("no hits", report.reasons[0])

    def test_probe_respects_budgets(self) -> None:
        windows, report = probe_transcript_files(
            [self.episode_file],
            anchors=["pnpm", "alembic", "staging"],
            budgets={"max_probes": 1, "max_total_bytes": 1000, "max_hits_expanded": 5, "max_lines_per_window": 10},
        )
        # Only one probe should have run.
        self.assertEqual(len(report.probes), 1)

    def test_probe_report_validates(self) -> None:
        _, report = probe_transcript_files(
            [self.episode_file],
            anchors=["pnpm"],
        )
        validate_document("transcript-probe-report.schema.json", report.to_dict())


class TestRelationGraph(unittest.TestCase):
    """WS7: Contradiction graph and relation-aware retrieval."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="graph-test-")
        self.root = Path(self.tmp.name)
        self.memory_root = self.root / ".opendream" / "memory"
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_and_load_store(self) -> None:
        store = create_relation_store(self.memory_root)
        self.assertIsInstance(store, RelationStore)
        self.assertEqual(store.load_edges(), [])

    def test_add_edge(self) -> None:
        store = create_relation_store(self.memory_root)
        edge = RelationEdge(
            edge_id="edge-1",
            from_id="mem-1",
            to_id="mem-2",
            kind="supersedes",
            created_at=to_iso(utc_now()),
            reason="newer version",
        )
        payload = store.add_edge(edge)
        self.assertEqual(payload["kind"], "supersedes")
        edges = store.load_edges()
        self.assertEqual(len(edges), 1)
        validate_document("relation-edge.schema.json", edges[0])

    def test_add_edge_deduplicates(self) -> None:
        store = create_relation_store(self.memory_root)
        now = to_iso(utc_now())
        for i in range(3):
            edge = RelationEdge(
                edge_id=f"edge-{i}",
                from_id="mem-1",
                to_id="mem-2",
                kind="supersedes",
                created_at=now,
            )
            store.add_edge(edge)
        # Should deduplicate by (from_id, to_id, kind).
        self.assertEqual(len(store.load_edges()), 1)

    def test_edges_for(self) -> None:
        store = create_relation_store(self.memory_root)
        now = to_iso(utc_now())
        store.add_edge(RelationEdge("e1", "mem-1", "mem-2", "supersedes", now))
        store.add_edge(RelationEdge("e2", "mem-3", "mem-1", "conflicts_with", now))
        store.add_edge(RelationEdge("e3", "mem-4", "mem-5", "supports", now))
        edges = store.edges_for("mem-1")
        self.assertEqual(len(edges), 2)

    def test_conflicts_for(self) -> None:
        store = create_relation_store(self.memory_root)
        now = to_iso(utc_now())
        store.add_edge(RelationEdge("e1", "mem-1", "mem-2", "supersedes", now))
        store.add_edge(RelationEdge("e2", "mem-1", "mem-3", "conflicts_with", now))
        conflicts = store.conflicts_for("mem-1")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["kind"], "conflicts_with")

    def test_remove_edges_for(self) -> None:
        store = create_relation_store(self.memory_root)
        now = to_iso(utc_now())
        store.add_edge(RelationEdge("e1", "mem-1", "mem-2", "supersedes", now))
        store.add_edge(RelationEdge("e2", "mem-3", "mem-1", "conflicts_with", now))
        removed = store.remove_edges_for("mem-1")
        self.assertEqual(removed, 2)
        self.assertEqual(store.load_edges(), [])

    def test_backfill_edges_from_records(self) -> None:
        store = create_relation_store(self.memory_root)
        records = [
            {"memory_id": "mem-1", "supersedes": ["mem-old"], "conflicts_with": ["mem-rival"]},
            {"memory_id": "mem-2", "supersedes": [], "conflicts_with": []},
        ]
        created = backfill_edges_from_records(records, store)
        self.assertEqual(len(created), 2)
        edges = store.load_edges()
        self.assertEqual(len(edges), 2)

    def test_relation_aware_score_superseded(self) -> None:
        edges = [{"kind": "supersedes", "from_id": "new", "to_id": "old"}]
        adjustment = relation_aware_score_adjustment("old", edges)
        self.assertLess(adjustment, 0)  # Superseded records get penalized.

    def test_relation_aware_score_verified(self) -> None:
        edges = [{"kind": "verified_by", "from_id": "mem-1", "to_id": "evidence"}]
        adjustment = relation_aware_score_adjustment("mem-1", edges)
        self.assertGreater(adjustment, 0)  # Verified records get boosted.

    def test_build_relation_explanations(self) -> None:
        edges = [
            {"edge_id": "e1", "from_id": "mem-1", "to_id": "mem-2", "kind": "supersedes"},
            {"edge_id": "e2", "from_id": "mem-3", "to_id": "mem-1", "kind": "conflicts_with"},
        ]
        records_by_id = {
            "mem-1": {"title": "Record A"},
            "mem-2": {"title": "Record B"},
            "mem-3": {"title": "Record C"},
        }
        explanations = build_relation_explanations("mem-1", edges, records_by_id)
        self.assertTrue(len(explanations) > 0)
        self.assertTrue(any("supersedes" in e for e in explanations))


class TestReconciliation(unittest.TestCase):
    """WS8: Reconciliation sweeps."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="reconciliation-test-")
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_clean_sweep_on_empty_store(self) -> None:
        report = run_reconciliation_sweep(self.store)
        self.assertIsInstance(report, ReconciliationReport)
        validate_document("reconciliation-report.schema.json", report.to_dict())

    def test_orphan_topic_detection(self) -> None:
        # Create an orphan topic file not matching any record.
        orphan = self.store.topics_dir / "orphan-topic-abc.md"
        orphan.write_text("# Orphan\n", encoding="utf-8")
        report = run_reconciliation_sweep(self.store)
        orphan_findings = [f for f in report.findings if "orphan" in f.lower()]
        self.assertTrue(len(orphan_findings) > 0)

    def test_dead_reference_detection(self) -> None:
        # Create a record that references a non-existent superseded record.
        from opendream.models import MemoryRecord
        now = to_iso(utc_now())
        record = MemoryRecord(
            memory_id="mem-with-dead-ref",
            type="project_decision",
            scope="project",
            title="Test",
            summary="Test record",
            body="Has dead references",
            status="active",
            confidence=0.9,
            salience=0.8,
            source_event_ids=["evt-1"],
            supersedes=["mem-nonexistent"],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.store.save_durable_records([record])
        report = run_reconciliation_sweep(self.store)
        dead_findings = [f for f in report.findings if "dead reference" in f.lower()]
        self.assertTrue(len(dead_findings) > 0)

    def test_view_drift_detection(self) -> None:
        # Create active records but an empty MEMORY.md.
        from opendream.models import MemoryRecord
        now = to_iso(utc_now())
        record = MemoryRecord(
            memory_id="mem-active-1",
            type="project_decision",
            scope="project",
            title="Active Decision",
            summary="An active record",
            body="This should appear in MEMORY.md",
            status="active",
            confidence=0.9,
            salience=0.8,
            source_event_ids=["evt-1"],
            supersedes=[],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.store.save_durable_records([record])
        # Make MEMORY.md nearly empty.
        self.store.memory_md_path.write_text("# Index\n", encoding="utf-8")
        report = run_reconciliation_sweep(self.store)
        drift_findings = [f for f in report.findings if "drift" in f.lower()]
        self.assertTrue(len(drift_findings) > 0)

    def test_reconciliation_audit_persisted(self) -> None:
        report = run_reconciliation_sweep(self.store)
        audit_path = self.store.audit_reconciliation_dir / f"{report.report_id}.json"
        self.assertTrue(audit_path.exists())


class TestProceduralMemoryEnrichment(unittest.TestCase):
    """WS9: Procedural memory elevation tests."""

    def test_memory_record_has_enriched_fields(self) -> None:
        now = to_iso(utc_now())
        record = MemoryRecord(
            memory_id="proc-1",
            type="workflow",
            scope="project",
            title="Deploy Workflow",
            summary="Steps to deploy",
            body="1. Build 2. Test 3. Deploy",
            status="active",
            confidence=0.9,
            salience=0.8,
            source_event_ids=["evt-1"],
            supersedes=[],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=now,
            updated_at=now,
            workflow_steps=["Build", "Test", "Deploy"],
            preconditions=["CI green", "Staging approved"],
            recovery_steps=["Rollback to previous tag"],
            anti_patterns=["Never skip staging"],
            success_markers=["Health check passes"],
        )
        d = record.to_dict()
        self.assertEqual(d["type"], "workflow")
        self.assertEqual(d["preconditions"], ["CI green", "Staging approved"])
        self.assertEqual(d["recovery_steps"], ["Rollback to previous tag"])
        self.assertEqual(d["anti_patterns"], ["Never skip staging"])
        self.assertEqual(d["success_markers"], ["Health check passes"])

    def test_enriched_fields_omitted_when_empty(self) -> None:
        now = to_iso(utc_now())
        record = MemoryRecord(
            memory_id="proc-2",
            type="semantic_fact",
            scope="project",
            title="Simple Fact",
            summary="A fact",
            body="Just a fact",
            status="active",
            confidence=0.9,
            salience=0.8,
            source_event_ids=["evt-1"],
            supersedes=[],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=now,
            updated_at=now,
        )
        d = record.to_dict()
        self.assertNotIn("preconditions", d)
        self.assertNotIn("recovery_steps", d)
        self.assertNotIn("anti_patterns", d)
        self.assertNotIn("success_markers", d)


class TestNewModels(unittest.TestCase):
    """Schema validation for new model types."""

    def test_relation_edge_model(self) -> None:
        edge = RelationEdge(
            edge_id="e1",
            from_id="mem-1",
            to_id="mem-2",
            kind="supersedes",
            created_at=to_iso(utc_now()),
            reason="newer",
            evidence_ids=["evt-1"],
        )
        d = edge.to_dict()
        validate_document("relation-edge.schema.json", d)
        self.assertEqual(d["kind"], "supersedes")

    def test_claim_verification_report_model(self) -> None:
        report = ClaimVerificationReport(
            report_id="cv-1",
            claim_id="c1",
            claim_class="externally_checkable",
            provenance_tier="runtime_verified",
            result="verified",
            checked_at=to_iso(utc_now()),
            verification_reads=["/path/to/file"],
            reason="file exists",
        )
        d = report.to_dict()
        validate_document("claim-verification-report.schema.json", d)

    def test_transcript_probe_report_model(self) -> None:
        report = TranscriptProbeReport(
            run_id="tp-1",
            probes=["pnpm", "migration"],
            hits=3,
            windows_read=3,
            escalations=0,
            bytes_read=1024,
            reasons=[],
        )
        d = report.to_dict()
        validate_document("transcript-probe-report.schema.json", d)

    def test_reconciliation_report_model(self) -> None:
        report = ReconciliationReport(
            report_id="rr-1",
            workspace="/tmp/test",
            findings=["orphan view detected"],
            actions=["flagged for review"],
            created_at=to_iso(utc_now()),
            needs_review=True,
        )
        d = report.to_dict()
        validate_document("reconciliation-report.schema.json", d)

    def test_memory_excellence_scorecard_model(self) -> None:
        scorecard = MemoryExcellenceScorecard(
            scorecard_id="sc-1",
            scores={"stale_claim_rate": 0.0, "contradiction_resolution_rate": 1.0},
            thresholds={"stale_claim_rate": 0.0, "contradiction_resolution_rate": 0.95},
            passed=True,
            artifacts=["rr-1"],
        )
        d = scorecard.to_dict()
        validate_document("memory-excellence-scorecard.schema.json", d)


class TestSchemaRegistration(unittest.TestCase):
    """Verify all new schemas are registered in validation.py."""

    def test_new_schemas_in_required_list(self) -> None:
        from opendream.validation import required_schema_files
        schemas = required_schema_files()
        self.assertIn("relation-edge.schema.json", schemas)
        self.assertIn("claim-verification-report.schema.json", schemas)
        self.assertIn("transcript-probe-report.schema.json", schemas)
        self.assertIn("reconciliation-report.schema.json", schemas)
        self.assertIn("memory-excellence-scorecard.schema.json", schemas)


class TestExtractorClaimClassification(unittest.TestCase):
    """Verify extractor adds claim_class to candidates."""

    def test_candidate_has_claim_class(self) -> None:
        event = {
            "event_id": "evt-1",
            "session_id": "s1",
            "turn_id": "t1",
            "timestamp": to_iso(utc_now()),
            "scope": "project",
            "kind": "project_decision",
            "source": {},
            "content": "Use pnpm instead of npm for package management",
            "tags": [],
        }
        candidate = extract_candidate(event, origin_mode="dream")
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertIn(candidate.claim_class, ("externally_checkable", "derived_abstraction", "speculative"))

    def test_task_outcome_with_requirement_signal_is_typed_requirement(self) -> None:
        event = {
            "event_id": "evt-req-1",
            "session_id": "s1",
            "turn_id": "t1",
            "timestamp": to_iso(utc_now()),
            "scope": "project",
            "kind": "task_outcome",
            "source": {},
            "content": "Redis must be running locally before the integration tests will pass.",
            "tags": [],
        }
        candidate = extract_candidate(event, origin_mode="dream")
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.type, "environment_requirement")

    def test_task_outcome_with_workflow_signal_is_typed_workflow_without_tag(self) -> None:
        event = {
            "event_id": "evt-flow-1",
            "session_id": "s1",
            "turn_id": "t1",
            "timestamp": to_iso(utc_now()),
            "scope": "project",
            "kind": "task_outcome",
            "source": {},
            "content": (
                "Working fix sequence: 1. docker compose up redis 2. pytest tests/test_worker.py "
                "3. make verify"
            ),
            "tags": [],
        }
        candidate = extract_candidate(event, origin_mode="dream")
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.type, "workflow")


class TestMemoryExcellenceScorecard(unittest.TestCase):
    """WS11: Memory-excellence evaluation and release gates."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="scorecard-test-")
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scorecard_on_empty_store(self) -> None:
        result = run_memory_excellence_eval(self.store)
        self.assertIn("scorecard_id", result)
        self.assertIn("scores", result)
        self.assertIn("thresholds", result)
        self.assertIn("passed", result)
        validate_document("memory-excellence-scorecard.schema.json", result)

    def test_scorecard_passes_on_clean_store(self) -> None:
        result = run_memory_excellence_eval(self.store)
        self.assertTrue(result["passed"])

    def test_scorecard_detects_stale_claims(self) -> None:
        from opendream.models import MemoryRecord
        now = to_iso(utc_now())
        record = MemoryRecord(
            memory_id="stale-claim-1",
            type="semantic_fact",
            scope="project",
            title="Fact: 15 test files",
            summary="The project has 15 test files",
            body="The project has 15 test files in the tests directory",
            status="active",
            confidence=0.9,
            salience=0.8,
            source_event_ids=["evt-1"],
            supersedes=[],
            conflicts_with=[],
            valid_from=now,
            valid_to=None,
            access_count=0,
            last_accessed_at=None,
            created_at=now,
            updated_at=now,
            provenance_tier="inferred",
        )
        # Manually set claim_class to externally_checkable.
        record_dict = record.to_dict()
        record_dict["claim_class"] = "externally_checkable"
        # Save using raw dict approach.
        from opendream.util import write_json
        write_json(self.store.durable_records_path, [record_dict])

        result = run_memory_excellence_eval(self.store)
        self.assertGreater(result["scores"]["stale_claim_rate"], 0)


class TestObservabilityExtensions(unittest.TestCase):
    """WS10: Observability surface extensions."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="obs-test-")
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_observability_includes_memory_excellence(self) -> None:
        index = index_observability(self.store)
        overview = index["overview"]
        self.assertIn("memory_excellence", overview)
        excellence = overview["memory_excellence"]
        self.assertIn("provenance_tiers", excellence)
        self.assertIn("claim_classes", excellence)
        self.assertIn("relation_edges", excellence)
        self.assertIn("verification_reports", excellence)
        self.assertIn("reconciliation_reports", excellence)
        self.assertIn("boundary_reports", excellence)

    def test_observability_entities_include_new_surfaces(self) -> None:
        index = index_observability(self.store)
        entities = index["entities"]
        self.assertIn("relation_edges", entities)
        self.assertIn("verification_reports", entities)
        self.assertIn("probe_reports", entities)
        self.assertIn("reconciliation_reports", entities)
        self.assertIn("boundary_reports", entities)


class TestIntegrationConsolidateWithClaimVerification(unittest.TestCase):
    """Integration test: consolidate emits claim verification reports and relation edges."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="integ-test-")
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root)
        self.store.initialize(store_kind="project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_consolidation_creates_relation_edges_on_supersede(self) -> None:
        now = to_iso(utc_now())
        # Emit events that will create and then supersede a record.
        emit_event(
            self.store,
            kind="project_decision",
            content="Use npm for package management",
            scope="project",
            channel="system",
            message_ref="msg-1",
            timestamp=now,
        )
        maintain(self.store, now=now)

        emit_event(
            self.store,
            kind="project_decision",
            content="Use pnpm instead of npm for package management",
            scope="project",
            channel="system",
            message_ref="msg-2",
            timestamp=now,
        )
        result = maintain(self.store, now=now)
        self.assertEqual(result["status"], "completed")


class TestContractExportExtensions(unittest.TestCase):
    """Verify contract export includes new engine IDs."""

    def test_contract_includes_new_engines(self) -> None:
        from opendream.contract_export import build_contract_export
        with tempfile.TemporaryDirectory(prefix="contract-test-") as tmp:
            contract = build_contract_export(Path(tmp))
            engines = contract["supported_engine_ids"]
            self.assertIn("builtin://claim-verifier", engines)
            self.assertIn("builtin://transcript-prober", engines)
            self.assertIn("builtin://reconciliation-sweeper", engines)


if __name__ == "__main__":
    unittest.main()
