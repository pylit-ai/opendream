from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LARGE_FILE_BYTES = 5 * 1024 * 1024
GENERATED_STATE_NAMES = {
    "observability_index.json",
    "observability_compact_index.json",
    "cache_config.json",
}
LARGE_FILE_ALLOW_PREFIXES = (
    "docs/assets/",
    "opendream/static/dist/",
    "archive/",
)


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_generated_state_path(path: str) -> bool:
    normalized = _normalize(path)
    parts = tuple(part for part in normalized.split("/") if part)
    if not parts:
        return False
    if ".opendream" in parts:
        return True
    if parts[0] == "memory":
        return True
    if len(parts) >= 2 and parts[-2] == "state" and parts[-1] in GENERATED_STATE_NAMES:
        return True
    return parts[-1] in GENERATED_STATE_NAMES


def is_large_file_allowed(path: str) -> bool:
    normalized = _normalize(path)
    return any(normalized.startswith(prefix) for prefix in LARGE_FILE_ALLOW_PREFIXES)


def _git_paths(command: list[str]) -> list[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode not in (0, 1):
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(stderr.strip() or f"command failed: {' '.join(command)}")
    return [
        item.decode("utf-8", errors="replace")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def tracked_or_staged_paths() -> list[str]:
    paths = set(_git_paths(["git", "ls-files", "-z"]))
    paths.update(_git_paths(["git", "diff", "--cached", "--name-only", "-z"]))
    return sorted(paths)


def staged_large_file_violations(paths: list[str], *, max_bytes: int = LARGE_FILE_BYTES) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for path in paths:
        if is_large_file_allowed(path):
            continue
        full_path = REPO_ROOT / path
        try:
            size = full_path.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            violations.append({"path": path, "bytes": size, "max_bytes": max_bytes})
    return violations


def build_report(*, max_bytes: int = LARGE_FILE_BYTES) -> dict[str, Any]:
    paths = tracked_or_staged_paths()
    generated = [path for path in paths if is_generated_state_path(path)]
    staged = _git_paths(["git", "diff", "--cached", "--name-only", "-z"])
    large_staged = staged_large_file_violations(staged, max_bytes=max_bytes)
    status = "passed" if not generated and not large_staged else "failed"
    return {
        "status": status,
        "generated_state_paths": generated,
        "large_staged_files": large_staged,
        "max_large_file_bytes": max_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-large-file-bytes", type=int, default=LARGE_FILE_BYTES)
    args = parser.parse_args()
    report = build_report(max_bytes=args.max_large_file_bytes)
    if report["status"] != "passed":
        print("generated state check failed:", file=sys.stderr)
        for path in list(report["generated_state_paths"]):
            print(f"  generated state tracked/staged: {path}", file=sys.stderr)
        for item in list(report["large_staged_files"]):
            print(
                f"  large staged file: {item['path']} ({item['bytes']} > {item['max_bytes']} bytes)",
                file=sys.stderr,
            )
        return 1
    print("generated state check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
