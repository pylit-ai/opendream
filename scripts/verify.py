from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from opendream.util import write_json

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / ".tmp" / "verification" / "verification_report.json"


def run_command(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    started_at = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "status": "FAIL",
            "returncode": None,
            "duration_seconds": round(time.time() - started_at, 3),
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "error": "timeout",
        }
    return {
        "command": command,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "duration_seconds": round(time.time() - started_at, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_lint_probe(*, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        probe_path = Path(temp_dir) / "lint_probe.py"
        probe_path.write_text("import os\n", encoding="utf-8")
        result = run_command([sys.executable, "-m", "ruff", "check", str(probe_path)], timeout_seconds=timeout_seconds)
        result["status"] = "PASS" if result["returncode"] not in (0, None) else "FAIL"
        result["probe"] = "lint"
        return result


def run_typecheck_probe(*, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        probe_path = Path(temp_dir) / "type_probe.py"
        probe_path.write_text('value: int = "bad"\n', encoding="utf-8")
        result = run_command([sys.executable, "-m", "mypy", str(probe_path)], timeout_seconds=timeout_seconds)
        result["status"] = "PASS" if result["returncode"] not in (0, None) else "FAIL"
        result["probe"] = "typecheck"
        return result


def build_report(*, timeout_seconds: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        eval_workspace = Path(temp_dir) / "dream-fidelity-eval"
        stages = [
            ("public-boundary", [str(REPO_ROOT / "scripts" / "check_public_boundary.sh")]),
            ("package-boundaries", [sys.executable, "scripts/check_package_boundaries.py"]),
            ("public-artifacts", [sys.executable, "scripts/check_public_artifacts.py"]),
            ("vendor-assets", [sys.executable, "scripts/check_vendor_assets.py"]),
            ("provenance-risk", [sys.executable, "scripts/check_provenance_risk.py"]),
            ("lint", [sys.executable, "scripts/lint.py"]),
            ("typecheck", [sys.executable, "scripts/typecheck.py"]),
            ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
            (
                "dream-fidelity-eval",
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "eval",
                    "dream-fidelity",
                    "--workspace",
                    str(eval_workspace),
                    "--compat-mode",
                    "autodream",
                ],
            ),
            (
                "performance-eval",
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "eval",
                    "performance",
                    "--workspace",
                    str(Path(temp_dir) / "perf-eval"),
                ],
            ),
            ("adapters-check", [sys.executable, "scripts/check_adapters.py"]),
            ("packaging-smoke", [sys.executable, "-m", "unittest", "tests.test_release_artifact", "-v"]),
            ("showcase-doc-smoke", [sys.executable, "scripts/smoke_showcase_docs.py"]),
            (
                "semantic-benchmark",
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "eval",
                    "semantic-benchmark",
                    "--workspace",
                    str(Path(temp_dir) / "semantic-eval"),
                    "--mode",
                    "hybrid",
                ],
            ),
        ]
        for name, command in stages:
            result = run_command(command, timeout_seconds=timeout_seconds)
            result["stage"] = name
            results.append(result)

    probe_results = [
        {"stage": "lint-probe", **run_lint_probe(timeout_seconds=timeout_seconds)},
        {"stage": "typecheck-probe", **run_typecheck_probe(timeout_seconds=timeout_seconds)},
    ]
    results.extend(probe_results)
    verdict = "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL"
    return {"verdict": verdict, "stages": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    report = build_report(timeout_seconds=args.timeout_seconds)
    report["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["report_path"] = str(Path(args.report_path))
    write_json(Path(args.report_path), report)
    print(Path(args.report_path))
    if report["verdict"] != "PASS":
        for stage in report["stages"]:
            if stage["status"] == "PASS":
                continue
            print(f"{stage['stage']}: {stage['status']} rc={stage.get('returncode')}")
            stdout = str(stage.get("stdout") or "").strip()
            stderr = str(stage.get("stderr") or "").strip()
            if stdout:
                print(stdout[-2000:])
            if stderr:
                print(stderr[-2000:])
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
