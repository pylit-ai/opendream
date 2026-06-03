from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opendream.storage import FileLock, LockError  # noqa: E402
from opendream.util import sha256_path, write_json  # noqa: E402

ARTIFACT_ROOT = REPO_ROOT / ".tmp" / "release-check"
LOCK_PATH = ARTIFACT_ROOT / "release-check.lock"
SEMANTIC_RELEASE_PROOF_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "semantic_release_proof.json"
RELEASE_EVIDENCE_SCHEMA = REPO_ROOT / "opendream" / "schema" / "release-evidence.schema.json"


def release_lock_holder_is_dead(lock_path: Path) -> bool:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    pid = payload.get("pid")
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


def remove_dead_release_lock(lock_path: Path) -> bool:
    if not lock_path.exists() or not release_lock_holder_is_dead(lock_path):
        return False
    lock_path.unlink(missing_ok=True)
    return True


def run_stage(name: str, command: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started_at = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        return {
            "name": name,
            "status": status,
            "returncode": completed.returncode,
            "duration_seconds": round(time.time() - started_at, 3),
            "command": command,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "FAIL",
            "returncode": None,
            "duration_seconds": round(time.time() - started_at, 3),
            "command": command,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "error": "timeout",
        }


def tasks_complete(spec_ids: list[str]) -> dict[str, Any]:
    incomplete: list[str] = []
    for spec_id in spec_ids:
        task_path = REPO_ROOT / "specs" / spec_id / "tasks.md"
        text = task_path.read_text(encoding="utf-8")
        if "- [ ]" in text:
            incomplete.append(spec_id)
    return {"name": "spec-blockers", "status": "PASS" if not incomplete else "FAIL", "incomplete_specs": incomplete}


def validate_release_manifest_shape(manifest: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(RELEASE_EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
    required = [str(item) for item in schema.get("required", [])]
    missing = [key for key in required if key not in manifest]
    stage_problems: list[str] = []
    stages = manifest.get("stages")
    if not isinstance(stages, list) or not stages:
        stage_problems.append("stages must be a non-empty list")
    else:
        for index, stage in enumerate(stages):
            if not isinstance(stage, dict):
                stage_problems.append(f"stage {index} is not an object")
                continue
            if "name" not in stage and "stage" not in stage:
                stage_problems.append(f"stage {index} missing name")
            if stage.get("status") not in {"PASS", "FAIL"}:
                stage_problems.append(f"stage {index} has invalid status")
    status = "PASS" if not missing and not stage_problems else "FAIL"
    return {
        "name": "release-evidence-schema",
        "status": status,
        "schema_path": str(RELEASE_EVIDENCE_SCHEMA.relative_to(REPO_ROOT)),
        "required_keys": required,
        "missing_keys": missing,
        "stage_problems": stage_problems,
    }


def preferred_release_blockers() -> list[str]:
    if not (REPO_ROOT / "specs").exists():
        return []
    next_gen = [
        "418-transcript-native-dream-engine",
        "419-dream-fidelity-evals",
        "420-truthful-verification-and-release",
    ]
    latest = [
        *next_gen,
        "430-sota-dream-runtime-bundle",
        "431-cli-ux-polish",
        "432-first-party-service-lifecycle",
        "433-zero-touch-agent-activation",
        "434-zero-touch-activation-and-command-surface-compression",
    ]
    if all((REPO_ROOT / "specs" / spec_id / "tasks.md").exists() for spec_id in latest):
        return latest
    if all((REPO_ROOT / "specs" / spec_id / "tasks.md").exists() for spec_id in next_gen):
        return next_gen
    return []


def load_semantic_release_proof_fixture(path: Path = SEMANTIC_RELEASE_PROOF_FIXTURE) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("semantic release proof fixture must be a JSON object")
    scenarios = payload.get("scenarios", {})
    required = {"unpruned_baseline", "degraded_semantic_first", "semantic_ready_progressive"}
    missing = sorted(required - set(scenarios))
    if missing:
        raise ValueError(f"semantic release proof fixture missing scenarios: {', '.join(missing)}")
    return payload


def _truthful_degraded_labeling(degraded: dict[str, Any]) -> bool:
    return (
        degraded.get("product_posture") == "semantic-first"
        and degraded.get("semantic_capability_state") == "degraded"
        and bool(str(degraded.get("semantic_unavailability_reason") or "").strip())
        and bool(str(degraded.get("next_action") or "").strip())
    )


def _pruning_advantage(baseline: dict[str, Any], ready: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    baseline_pruning = baseline.get("context_pruning", {})
    ready_pruning = ready.get("context_pruning", {})
    evidence = {
        "baseline_saved_characters": int(baseline_pruning.get("saved_characters", 0) or 0),
        "ready_saved_characters": int(ready_pruning.get("saved_characters", 0) or 0),
        "baseline_injected_count": int(baseline_pruning.get("injected_count", 0) or 0),
        "ready_injected_count": int(ready_pruning.get("injected_count", 0) or 0),
        "baseline_candidate_count": int(baseline_pruning.get("candidate_count", 0) or 0),
        "ready_candidate_count": int(ready_pruning.get("candidate_count", 0) or 0),
    }
    passed = (
        evidence["ready_saved_characters"] > evidence["baseline_saved_characters"]
        and evidence["ready_injected_count"] < evidence["baseline_injected_count"]
        and evidence["ready_candidate_count"] >= evidence["baseline_candidate_count"]
    )
    return passed, evidence


def _repeated_task_improvements(baseline: dict[str, Any], ready: dict[str, Any]) -> dict[str, float]:
    baseline_task = baseline.get("repeated_task", {})
    ready_task = ready.get("repeated_task", {})
    improvements: dict[str, float] = {}
    success_delta = round(
        float(ready_task.get("success_rate", 0.0) or 0.0) - float(baseline_task.get("success_rate", 0.0) or 0.0),
        4,
    )
    if success_delta > 0:
        improvements["success_rate_delta"] = success_delta
    reuse_delta = int(ready_task.get("procedural_reuse_hits", 0) or 0) - int(
        baseline_task.get("procedural_reuse_hits", 0) or 0
    )
    if reuse_delta > 0:
        improvements["procedural_reuse_delta"] = reuse_delta
    latency_delta = int(baseline_task.get("resolution_latency_ms", 0) or 0) - int(
        ready_task.get("resolution_latency_ms", 0) or 0
    )
    if latency_delta > 0:
        improvements["resolution_latency_improvement_ms"] = latency_delta
    return improvements


def semantic_release_proof_stage(fixture: dict[str, Any]) -> dict[str, Any]:
    scenarios = fixture["scenarios"]
    baseline = scenarios["unpruned_baseline"]
    degraded = scenarios["degraded_semantic_first"]
    ready = scenarios["semantic_ready_progressive"]

    truthful_degraded = _truthful_degraded_labeling(degraded)
    pruning_advantage, pruning_evidence = _pruning_advantage(baseline, ready)
    repeated_task_improvements = _repeated_task_improvements(baseline, ready)
    repeated_task_benefit = bool(repeated_task_improvements)

    checks = {
        "truthful_degraded_labeling": truthful_degraded,
        "pruning_advantage": pruning_advantage,
        "repeated_task_benefit": repeated_task_benefit,
    }
    return {
        "name": "semantic-release-proof",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "evidence": {
            "pruning": pruning_evidence,
            "repeated_task_improvements": repeated_task_improvements,
            "degraded_reason": degraded.get("semantic_unavailability_reason"),
            "degraded_next_action": degraded.get("next_action"),
        },
    }


def release_manifest(timeout_seconds: int) -> dict[str, Any]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    stages: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        dist_dir = temp_path / "dist"
        venv_dir = temp_path / "venv"
        scripts_dir = "Scripts" if os.name == "nt" else "bin"
        venv_python = venv_dir / scripts_dir / "python"
        venv_pip = [str(venv_python), "-m", "pip"]

        stages.append(
            run_stage(
                "verify",
                [sys.executable, "scripts/verify.py"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "package-boundaries",
                [sys.executable, "scripts/check_package_boundaries.py"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "release-artifacts",
                [sys.executable, "scripts/check_release_artifacts.py"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "vendor-assets",
                [sys.executable, "scripts/check_vendor_assets.py"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "provenance-risk",
                [sys.executable, "scripts/check_provenance_risk.py"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(tasks_complete(preferred_release_blockers()))
        stages.append(
            run_stage(
                "build",
                [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "venv",
                [sys.executable, "-m", "venv", str(venv_dir)],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "install-dev",
                [*venv_pip, "install", "--upgrade", "pip", "setuptools", "wheel"],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "install-package",
                [*venv_pip, "install", "-e", ".[dev]"],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "cli-help",
                [str(venv_dir / scripts_dir / "opendream"), "--help"],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        demo_workspace = temp_path / "demo-workspace"
        dream_workspace = temp_path / "dream-workspace"
        eval_workspace = temp_path / "eval-workspace"
        stages.append(
            run_stage(
                "demo",
                [str(venv_dir / scripts_dir / "opendream"), "demo", "--workspace", str(demo_workspace)],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "dream-run",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "dream",
                    "run",
                    "--workspace",
                    str(dream_workspace),
                    "--episodes",
                    str(REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"),
                    "--compat-mode",
                    "project-user",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "dream-enqueue",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "dream",
                    "enqueue",
                    "--workspace",
                    str(dream_workspace),
                    "--episodes",
                    str(REPO_ROOT / "tests" / "fixtures" / "transcript_only_dream.jsonl"),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "dream-worker-once",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "dream",
                    "worker",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--once",
                    "--max-jobs-per-poll",
                    "1",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "install-service",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "install-service",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--install-root",
                    str(temp_path / "services"),
                    "--interval-seconds",
                    "0.2",
                    "--no-start",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-start",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "service",
                    "start",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-status",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "service",
                    "status",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-restart",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "service",
                    "restart",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-stop",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "service",
                    "stop",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-autowire",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "service",
                    "autowire",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--target",
                    "codex",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "service-uninstall",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "uninstall-service",
                    "--workspace",
                    str(dream_workspace),
                    "--memory-dir",
                    ".dream-memory",
                    "--purge",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "eval-dream-layout",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "eval",
                    "dream-layout",
                    "--workspace",
                    str(eval_workspace),
                    "--compat-mode",
                    "project-user",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        perf_workspace = temp_path / "perf-eval"
        perf_result = run_stage(
            "eval-performance",
            [
                str(venv_dir / scripts_dir / "opendream"),
                "eval",
                "performance",
                "--workspace",
                str(perf_workspace),
            ],
            cwd=temp_path,
            timeout_seconds=timeout_seconds,
        )
        stages.append(perf_result)
        perf_scorecard = None
        if perf_result["status"] == "PASS" and perf_result.get("stdout"):
            try:
                perf_output = json.loads(perf_result["stdout"])
                perf_scorecard = perf_output.get("scorecard")
            except (json.JSONDecodeError, TypeError):
                pass
        semantic_workspace = temp_path / "semantic-eval"
        semantic_result = run_stage(
            "eval-semantic-benchmark",
            [
                str(venv_dir / scripts_dir / "opendream"),
                "eval",
                "semantic-benchmark",
                "--workspace",
                str(semantic_workspace),
                "--mode",
                "hybrid",
            ],
            cwd=temp_path,
            timeout_seconds=timeout_seconds,
        )
        stages.append(semantic_result)
        stages.append(semantic_release_proof_stage(load_semantic_release_proof_fixture()))
        stages.append(
            run_stage(
                "verify-clean-venv",
                [str(venv_python), "scripts/verify.py", "--report-path", str(temp_path / "verify.json")],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )
        runtime_workspace = temp_path / "runtime-eval"
        stages.append(
            run_stage(
                "eval-advanced-runtime",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "eval",
                    "advanced-runtime",
                    "--workspace",
                    str(runtime_workspace),
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )

        built_artifacts = sorted(dist_dir.glob("*"))
        artifact_hashes = {path.name: sha256_path(path) for path in built_artifacts}

    git_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "unknown"
    )
    manifest = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": git_sha,
        "python": sys.version,
        "platform": platform.platform(),
        "timeout_seconds": timeout_seconds,
        "verdict": "FAIL",
        "stages": stages,
        "artifact_hashes": artifact_hashes,
        "performance_scorecard": perf_scorecard,
    }
    schema_stage = validate_release_manifest_shape(manifest)
    manifest["schema_validation"] = {
        key: value for key, value in schema_stage.items() if key not in {"name"}
    }
    stages.append(schema_stage)
    manifest["verdict"] = "PASS" if all(stage["status"] == "PASS" for stage in stages) else "FAIL"
    return manifest


def write_summary(manifest: dict[str, Any], summary_path: Path) -> None:
    lines = [
        "# Release Check Summary",
        "",
        f"- verdict: {manifest['verdict']}",
        f"- git_sha: {manifest['git_sha']}",
        "",
    ]
    for stage in manifest["stages"]:
        lines.append(f"- {stage['name']}: {stage['status']}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = ARTIFACT_ROOT / "release_manifest.json"
    summary_path = ARTIFACT_ROOT / "release_summary.md"
    remove_dead_release_lock(LOCK_PATH)
    lock = FileLock(LOCK_PATH, ttl_seconds=args.timeout_seconds)
    try:
        with lock:
            manifest = release_manifest(args.timeout_seconds)
    except LockError:
        manifest = {
            "schema_version": 1,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_sha": "unknown",
            "python": sys.version,
            "platform": platform.platform(),
            "timeout_seconds": args.timeout_seconds,
            "verdict": "FAIL",
            "stages": [{"name": "lock", "status": "FAIL", "error": "lock-held"}],
            "artifact_hashes": {},
        }

    write_json(manifest_path, manifest)
    write_summary(manifest, summary_path)
    print(json.dumps({"manifest": str(manifest_path), "summary": str(summary_path), "verdict": manifest["verdict"]}))
    return 0 if manifest["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
