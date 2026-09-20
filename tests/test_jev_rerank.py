from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opendream.cli import build_parser
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
