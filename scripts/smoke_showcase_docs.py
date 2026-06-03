from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_cli_json(result: dict[str, Any]) -> dict[str, Any]:
    if result["returncode"] != 0:
        raise AssertionError(
            f"command failed: {' '.join(result['command'])}\n{result['stderr'] or result['stdout']}"
        )
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not emit JSON: {' '.join(result['command'])}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"command emitted non-object JSON: {' '.join(result['command'])}")
    return payload


def global_cli_status() -> dict[str, Any]:
    executable = shutil.which("opendream")
    if not executable:
        return {"status": "missing", "path": None, "supports_showcase_scenario": False}

    help_result = run_command([executable, "demo", "--help"], timeout_seconds=30)
    supports = "--scenario" in help_result["stdout"] and "agent-workspace-showcase" in help_result["stdout"]
    return {
        "status": "fresh" if supports else "stale",
        "path": executable,
        "supports_showcase_scenario": supports,
        "returncode": help_result["returncode"],
    }


def validate_demo(payload: dict[str, Any]) -> None:
    if payload.get("scenario") != "agent-workspace-showcase":
        raise AssertionError("demo scenario mismatch")
    if payload.get("status") != "passed":
        raise AssertionError("demo did not pass")
    checks = payload.get("checks", {})
    passed_checks = [item.get("passed") for item in checks.values() if isinstance(item, dict)]
    if not isinstance(checks, dict) or not passed_checks or not all(passed_checks):
        raise AssertionError("demo checks did not all pass")
    for check_name in ("negative_controls", "abstention", "memory_hurt"):
        if not checks.get(check_name, {}).get("passed"):
            raise AssertionError(f"demo check did not pass: {check_name}")
    if not payload.get("selected_memory_ids"):
        raise AssertionError("demo did not report selected memory ids")
    if not all(case.get("passed") for case in payload.get("negative_controls", [])):
        raise AssertionError("demo negative controls did not all pass")
    if not all(case.get("abstained") for case in payload.get("abstention_cases", [])):
        raise AssertionError("demo abstention cases did not all abstain")
    if not all(case.get("harm_prevented_by_default") for case in payload.get("memory_hurt_cases", [])):
        raise AssertionError("demo memory-hurt cases did not show default suppression")
    if "OpenDream found prior memory:" not in str(payload.get("agent_snippet", "")):
        raise AssertionError("demo did not emit agent-facing memory snippet")
    agent_answers = payload.get("agent_answers", {})
    stateless = agent_answers.get("stateless", {}) if isinstance(agent_answers, dict) else {}
    memory_assisted = agent_answers.get("memory_assisted", {}) if isinstance(agent_answers, dict) else {}
    comparison = agent_answers.get("comparison", {}) if isinstance(agent_answers, dict) else {}
    if stateless.get("measurement", {}).get("passed"):
        raise AssertionError("stateless baseline answer unexpectedly passed")
    if not memory_assisted.get("measurement", {}).get("passed"):
        raise AssertionError("memory-assisted answer did not pass measured answer checks")
    if not comparison.get("passed"):
        raise AssertionError("memory-assisted answer did not improve over stateless baseline")
    for key in (
        "claim_verification",
        "memory_safety",
        "agent_observability_trace",
        "evidence_drilldown",
        "selected_vs_excluded",
        "score_visualization",
        "glossary",
        "copy_actions",
    ):
        if key not in payload:
            raise AssertionError(f"demo missing upgraded report field: {key}")
    if payload["claim_verification"].get("trust_level") != "strong":
        raise AssertionError("demo claim verification did not reach strong trust")
    if not payload["memory_safety"].get("passed"):
        raise AssertionError("demo memory safety did not pass")
    trace = payload["agent_observability_trace"]
    if not trace.get("run_id") or not trace.get("context_id"):
        raise AssertionError("demo observability trace missing run/context ids")
    trace_operations = {span.get("operation") for span in trace.get("spans", []) if isinstance(span, dict)}
    if not {"memory_read", "memory_write", "context_read", "answer_generation", "eval_scoring"} <= trace_operations:
        raise AssertionError("demo observability trace missing required operation types")
    report_path = payload.get("report_path")
    if not report_path or not (REPO_ROOT / str(report_path)).exists():
        raise AssertionError("demo report_path missing or not written")


def validate_eval(payload: dict[str, Any]) -> None:
    if payload.get("scenario") != "agent-workspace-showcase":
        raise AssertionError("eval scenario mismatch")
    if payload.get("status") != "passed":
        raise AssertionError("eval did not pass")
    checks = payload.get("checks", {})
    if not isinstance(checks, dict) or not all(checks.values()):
        raise AssertionError("eval checks did not all pass")
    for check_name in ("negative_controls", "abstention", "memory_hurt"):
        if not checks.get(check_name, {}).get("passed"):
            raise AssertionError(f"eval check did not pass: {check_name}")
    if not all(case.get("passed") for case in payload.get("negative_controls", [])):
        raise AssertionError("eval negative controls did not all pass")
    if not all(case.get("abstained") for case in payload.get("abstention_cases", [])):
        raise AssertionError("eval abstention cases did not all abstain")
    if not all(case.get("harm_prevented_by_default") for case in payload.get("memory_hurt_cases", [])):
        raise AssertionError("eval memory-hurt cases did not show default suppression")


def build_report(*, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="opendream-showcase-docs-") as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        demo = parse_cli_json(
            run_command(
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "demo",
                    "--scenario",
                    "agent-workspace-showcase",
                    "--workspace",
                    str(workspace),
                ],
                timeout_seconds=timeout_seconds,
            )
        )
        validate_demo(demo)

        eval_payload = parse_cli_json(
            run_command(
                [
                    sys.executable,
                    "-m",
                    "opendream.cli",
                    "eval",
                    "showcase",
                    "--scenario",
                    "agent-workspace-showcase",
                    "--workspace",
                    str(workspace),
                ],
                timeout_seconds=timeout_seconds,
            )
        )
        validate_eval(eval_payload)

        return {
            "status": "PASS",
            "commands": {
                "demo": demo.get("scenario"),
                "eval": eval_payload.get("scenario"),
            },
            "generated_at": demo.get("generated_at"),
            "agent_snippet": demo.get("agent_snippet"),
            "answer_score_delta": demo.get("agent_answers", {}).get("comparison", {}).get("score_delta"),
            "claim_trust_level": demo.get("claim_verification", {}).get("trust_level"),
            "memory_safety_risk_level": demo.get("memory_safety", {}).get("risk_level"),
            "trace_span_count": len(demo.get("agent_observability_trace", {}).get("spans", [])),
            "global_cli": global_cli_status(),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    report = build_report(timeout_seconds=args.timeout_seconds)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
