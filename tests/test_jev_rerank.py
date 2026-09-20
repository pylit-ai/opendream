from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from opendream.cli import build_parser, main
from opendream.jev_rerank import MODEL, RUBRIC, _request, rerank
from opendream.storage import MemoryStore
from opendream.util import write_json
from opendream.validation import validate_document
from tests.test_retriever_explanations import NOW, durable_record


def response() -> dict:
    return {"model": MODEL, "usage": {"input_tokens": 10, "output_tokens": 5}, "answers": {
        f"candidate_{index}": {
            "type": "score", "score": score, "confidence": 0.9,
            "probabilities": {str(i): float(i == score) for i in range(3)},
            "legend": {str(i): text for i, text in enumerate(RUBRIC)},
        } for index, score in enumerate([0, 2])
    }}


class JevConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoryStore(Path(self.tmp.name))
        self.store.initialize(store_kind="project")
        self.records = [durable_record(
            identifier, title=f"{identifier} package dependency installation",
            body="package dependency installation",
        ) for identifier in ("a", "b", "c")]
        self.records.append(durable_record(
            "retired", title="package dependency installation", body="package", status="retired",
        ))
        write_json(self.store.durable_records_path, self.records)

    def run_retrieve(self, *extra: str) -> dict:
        args = build_parser().parse_args([
            "retrieve", "--workspace", str(self.store.workspace),
            "--query", "package dependency installation", "--now", NOW, "--limit", "2", *extra,
        ])
        return args.func(args)

    def opted(self) -> dict:
        return self.run_retrieve("--jev-rerank", "--jev-allow-memory", "a", "--jev-allow-memory", "b")

    def run_main(self, *, opted: bool) -> dict:
        argv = ["opendream", "retrieve", "--workspace", str(self.store.workspace),
                "--query", "package dependency installation", "--now", NOW, "--limit", "2"]
        if opted:
            argv += ["--jev-rerank", "--jev-allow-memory", "a", "--jev-allow-memory", "b"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main()
        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        return json.loads(stdout.getvalue())

    def test_real_cli_availability_matrix_preserves_baseline(self) -> None:
        huge_score = response()
        huge_score["answers"]["candidate_0"]["score"] = 10 ** 400
        cases = [
            ("default_with_key", False, "synthetic-key", 200, response(), None, 0, None),
            ("default_without_key", False, "", 200, response(), None, 0, None),
            ("opt_in_no_key", True, "", 200, response(), None, 0, "missing_credentials"),
            ("available", True, "synthetic-key", 200, response(), None, 1, "applied"),
            ("auth_401", True, "synthetic-key", 401, {}, None, 1, "provider_failure"),
            ("rate_429", True, "synthetic-key", 429, {}, None, 1, "provider_failure"),
            ("network", True, "synthetic-key", 200, {}, OSError("offline"), 1, "provider_failure"),
            ("timeout", True, "synthetic-key", 200, {}, TimeoutError("timed out"), 1, "provider_failure"),
            ("malformed_json", True, "synthetic-key", 200, b"not JSON", None, 1, "provider_failure"),
            ("non_object", True, "synthetic-key", 200, [], None, 1, "provider_failure"),
            ("invalid_encoding", True, "synthetic-key", 200, b"\xff", None, 1, "provider_failure"),
            ("deep_json", True, "synthetic-key", 200, b"[" * 2000 + b"]" * 2000,
             None, 1, "provider_failure"),
            ("huge_score", True, "synthetic-key", 200, huge_score, None, 1, "provider_failure"),
        ]
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": ""}):
            baseline = self.run_main(opted=False)
        for name, opted, key, status, body, error, attempts, reason in cases:
            with self.subTest(case=name), patch.dict("os.environ", {"TYPESAFE_API_KEY": key}), \
                    patch("opendream.jev_rerank.http.client.HTTPSConnection") as connection:
                client = connection.return_value
                client.getresponse.side_effect = error
                client.getresponse.return_value.status = status
                client.getresponse.return_value.read.return_value = (
                    body if isinstance(body, bytes) else json.dumps(body).encode()
                )
                result = self.run_main(opted=opted)
                if reason == "applied":
                    self.assertEqual(result["selected_memory_ids"], ["b", "a"])
                else:
                    for field in ("selected_memory_ids", "why", "explanations", "excluded", "memory_hurt"):
                        self.assertEqual(result[field], baseline[field])
                self.assertEqual(connection.call_count, attempts)
                self.assertEqual(client.request.call_count, attempts)
                self.assertEqual(client.close.call_count, attempts)
                if opted:
                    metadata = result["rerank"]["jev"]
                    self.assertEqual(metadata["reason"], reason)
                    self.assertEqual(metadata["attempted_requests"], attempts)
                    self.assertEqual(metadata["baseline_memory_ids"], baseline["selected_memory_ids"])
                    validate_document("jev-rerank.schema.json", metadata)
                else:
                    self.assertNotIn("jev", result["rerank"])

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_consumer_path_reorders_only_baseline_and_minimizes_egress(self, request) -> None:
        request.return_value = response()
        baseline = self.run_retrieve()
        request.assert_not_called()
        result = self.opted()
        self.assertEqual(result["selected_memory_ids"], ["b", "a"])
        self.assertEqual(result["rerank"]["jev"]["baseline_memory_ids"], baseline["selected_memory_ids"])
        self.assertEqual([e["memory_id"] for e in result["explanations"]], ["b", "a"])
        self.assertEqual(request.call_count, 1)
        validate_document("jev-rerank.schema.json", result["rerank"]["jev"])
        payload = request.call_args.args[0]
        self.assertEqual(set(payload["state"]), {"query", "candidates"})
        self.assertEqual(set(payload["state"]["candidates"]), {"candidate_0", "candidate_1"})
        for candidate in payload["state"]["candidates"].values():
            self.assertEqual(set(candidate), {"title", "summary"})

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_missing_opt_in_or_approval_and_gated_queries_never_call(self, request) -> None:
        self.run_retrieve("--jev-allow-memory", "a", "--jev-allow-memory", "b")
        self.run_retrieve("--jev-rerank")
        self.run_retrieve("--jev-rerank", "--jev-allow-memory", "retired", "--jev-allow-memory", "c")
        self.run_retrieve("--jev-rerank", "--query", "hello")
        request.assert_not_called()

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_request_count_and_content_bounds(self, request) -> None:
        request.return_value = response()
        rerank("q" * 2000, [{"title": "t" * 300, "summary": "s" * 1000}] * 2)
        payload = request.call_args.args[0]
        self.assertEqual(len(payload["state"]["query"]), 1000)
        candidate = payload["state"]["candidates"]["candidate_0"]
        self.assertEqual(len(candidate["title"]), 160)
        self.assertEqual(len(candidate["summary"]), 400)
        request.reset_mock()
        rerank("query", [{}] * 9)
        request.assert_not_called()

    @patch("opendream.jev_rerank.http.client.HTTPSConnection")
    def test_transport_does_not_follow_redirects_or_retry_and_bounds_response(self, connection) -> None:
        client = connection.return_value
        client.getresponse.return_value.status = 302
        with self.assertRaises(ValueError):
            _request({}, "synthetic-key")
        connection.assert_called_once_with("api.typesafe.ai", timeout=3.0)
        client.request.assert_called_once()
        client.close.assert_called_once()
        client.getresponse.return_value.status = 200
        client.getresponse.return_value.read.return_value = b" " * 65537
        with self.assertRaises(ValueError):
            _request({}, "synthetic-key")
        client.getresponse.return_value.read.assert_called_once_with(65537)

    @patch.dict("os.environ", {}, clear=True)
    @patch("opendream.jev_rerank._request")
    def test_missing_credentials_falls_back(self, request) -> None:
        result = self.opted()
        self.assertEqual(result["selected_memory_ids"], ["a", "b"])
        self.assertEqual(result["rerank"]["jev"]["reason"], "missing_credentials")
        request.assert_not_called()

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_invalid_outputs_never_rescue_injected_ids(self, request) -> None:
        mutations = [
            lambda r: r.pop("usage"),
            lambda r: r["usage"].update(input_tokens=True),
            lambda r: r["usage"].update(output_tokens=-1),
            lambda r: r["answers"]["candidate_0"].pop("type"),
            lambda r: r["answers"].update(candidate_0=[]),
            lambda r: r["answers"].update({"retired": r["answers"].pop("candidate_0")}),
            lambda r: r["answers"].pop("candidate_1"),
            lambda r: r["answers"]["candidate_0"].update(score=float("nan")),
            lambda r: r["answers"]["candidate_0"].update(score=True),
            lambda r: r["answers"]["candidate_0"].update(score=3),
            lambda r: r["answers"]["candidate_0"].update(confidence=0.1),
            lambda r: r["answers"]["candidate_0"].update(probabilities={"0": 0, "1": 0, "2": 0}),
            lambda r: r["answers"]["candidate_0"].update(legend={}),
            lambda r: r.update(model="unexpected"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = copy.deepcopy(response())
                mutation(payload)
                request.return_value = payload
                result = self.opted()
                self.assertEqual(result["selected_memory_ids"], ["a", "b"])
                self.assertFalse(result["rerank"]["jev"]["applied"])
        request.side_effect = TimeoutError("private error")
        self.assertEqual(self.opted()["selected_memory_ids"], ["a", "b"])

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_rounding_and_rejection_diagnostics_are_specific_and_content_free(self, request) -> None:
        payload = response()
        payload["answers"]["candidate_1"].update(
            score=1.98, probabilities={"0": 0, "1": 0.02, "2": 0.98}, confidence=0.97,
        )
        request.return_value = payload
        accepted = self.opted()
        self.assertEqual(accepted["selected_memory_ids"], ["b", "a"])
        self.assertNotIn("failure_stage", accepted["rerank"]["jev"])
        for stage, updates in [
            ("score_expectation", {"score": 1.97}),
            ("probability_sum", {"probabilities": {"0": 0, "1": 0.02, "2": 0.97}}),
            ("rubric", {"legend": {"0": "private rejected text"}}),
            ("score", {"score": "private rejected text"}),
        ]:
            with self.subTest(stage=stage):
                malformed = copy.deepcopy(payload)
                malformed["answers"]["candidate_1"].update(updates)
                request.return_value = malformed
                result = self.opted()
                metadata = result["rerank"]["jev"]
                self.assertEqual(metadata["failure_stage"], stage)
                self.assertEqual(result["selected_memory_ids"], ["a", "b"])
                self.assertNotIn("private rejected text", json.dumps(metadata))
                validate_document("jev-rerank.schema.json", metadata)

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "synthetic-key"})
    @patch("opendream.jev_rerank._request")
    def test_conflicted_and_sensitive_records_never_leave_host(self, request) -> None:
        self.records[0]["conflicts_with"] = ["b"]
        write_json(self.store.durable_records_path, self.records)
        self.opted()
        request.assert_not_called()
        self.records[0]["conflicts_with"] = []
        write_json(self.store.durable_records_path, self.records)
        with patch.object(MemoryStore, "load_events", return_value=[{
            "event_id": "event-a", "sensitivity": "sensitive",
        }]):
            self.opted()
        request.assert_not_called()
