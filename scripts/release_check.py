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

from opendream.storage import FileLock, LockError
from opendream.util import sha256_path, write_json

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO_ROOT / ".tmp" / "release-check"
LOCK_PATH = ARTIFACT_ROOT / "release-check.lock"


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


def preferred_release_blockers() -> list[str]:
    next_gen = [
        "418-transcript-native-dream-engine",
        "419-dream-fidelity-evals",
        "420-truthful-verification-and-release",
    ]
    if all((REPO_ROOT / "specs" / spec_id / "tasks.md").exists() for spec_id in next_gen):
        return next_gen
    return ["410-truthful-verification", "411-autodream-fidelity", "412-memory-quality"]


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
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "eval-dream-fidelity",
                [
                    str(venv_dir / scripts_dir / "opendream"),
                    "eval",
                    "dream-fidelity",
                    "--workspace",
                    str(eval_workspace),
                    "--compat-mode",
                    "autodream",
                    "--memory-dir",
                    ".dream-memory",
                ],
                cwd=temp_path,
                timeout_seconds=timeout_seconds,
            )
        )
        stages.append(
            run_stage(
                "verify-clean-venv",
                [str(venv_python), "scripts/verify.py", "--report-path", str(temp_path / "verify.json")],
                cwd=REPO_ROOT,
                timeout_seconds=timeout_seconds,
            )
        )

        built_artifacts = sorted(dist_dir.glob("*"))
        artifact_hashes = {path.name: sha256_path(path) for path in built_artifacts}

    overall_verdict = "PASS" if all(stage["status"] == "PASS" for stage in stages) else "FAIL"
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
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": git_sha,
        "python": sys.version,
        "platform": platform.platform(),
        "timeout_seconds": timeout_seconds,
        "verdict": overall_verdict,
        "stages": stages,
        "artifact_hashes": artifact_hashes,
    }
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
    lock = FileLock(LOCK_PATH, ttl_seconds=args.timeout_seconds)
    try:
        with lock:
            manifest = release_manifest(args.timeout_seconds)
    except LockError:
        manifest = {
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
