"""Meta-harness bootstrap and optimization.

Implements WS11 (T62-T68): environment bootstrap capture, harness optimizer
scaffolding, search spaces, toy optimization workflow.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import HarnessOptimizationReport
from .storage import MemoryStore
from .util import stable_id, to_iso, utc_now

# ── Environment bootstrap ───────────────────────────────────────────────

def capture_environment_bootstrap(
    workspace: Path,
    *,
    store: MemoryStore | None = None,
) -> dict[str, Any]:
    """Capture environment context for coding-agent harness bootstrap.

    Inspired by Meta-Harness: captures working directory, repo structure,
    tool availability, and memory mode/health for injection into agent prompts.
    """
    workspace = Path(workspace).expanduser().resolve()

    bootstrap: dict[str, Any] = {
        "workspace": str(workspace),
        "captured_at": to_iso(utc_now()),
    }

    # Working directory info
    bootstrap["cwd"] = str(Path.cwd())
    bootstrap["workspace_exists"] = workspace.exists()

    # Repo structure sketch
    if workspace.exists():
        tree_items: list[str] = []
        try:
            for item in sorted(workspace.iterdir()):
                if item.name.startswith(".") and item.name not in (".opendream", ".claude"):
                    continue
                kind = "dir" if item.is_dir() else "file"
                tree_items.append(f"{kind}: {item.name}")
        except PermissionError:
            tree_items.append("(permission denied)")
        bootstrap["repo_tree_sketch"] = tree_items[:50]

    # Git info
    git_dir = workspace / ".git"
    if git_dir.exists():
        bootstrap["git"] = {"present": True}
        try:
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=str(workspace),
                timeout=5,
            )
            if branch.returncode == 0:
                bootstrap["git"]["branch"] = branch.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    else:
        bootstrap["git"] = {"present": False}

    # Tool availability
    tools: dict[str, bool] = {}
    for tool_name in ["python", "python3", "node", "npm", "cargo", "go", "make", "git"]:
        try:
            result = subprocess.run(
                ["which", tool_name],
                capture_output=True,
                timeout=2,
            )
            tools[tool_name] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            tools[tool_name] = False
    bootstrap["tools"] = tools

    # Python version
    bootstrap["python_version"] = sys.version.split()[0]

    # Package manager detection
    bootstrap["package_managers"] = {
        "pyproject.toml": (workspace / "pyproject.toml").exists(),
        "requirements.txt": (workspace / "requirements.txt").exists(),
        "package.json": (workspace / "package.json").exists(),
        "Cargo.toml": (workspace / "Cargo.toml").exists(),
        "go.mod": (workspace / "go.mod").exists(),
        "Makefile": (workspace / "Makefile").exists(),
    }

    # Memory mode/health
    if store:
        semantic_config = store.load_semantic_config()
        bootstrap["memory"] = {
            "mode": semantic_config.get("mode", "deterministic"),
            "initialized": store.is_initialized(),
            "durable_record_count": len(store.load_durable_records()),
            "learned_context_count": len(store.load_learned_context_records()),
            "provider_count": len(store.load_provider_registry()),
        }
        dream_state = store.load_dream_state()
        bootstrap["memory"]["dream_state"] = dream_state.get("state", "unknown")
        queue = store.load_dream_queue()
        bootstrap["memory"]["queue_depth"] = len(
            [j for j in queue if j.get("status") == "queued"]
        )

    return bootstrap


# ── Harness optimizer scaffolding ────────────────────────────────────────

# Default search space for harness optimization
DEFAULT_SEARCH_SPACE: dict[str, Any] = {
    "memory_injection": {
        "description": "How much learned context to inject into agent prompts",
        "variants": [
            {"id": "none", "injection_limit": 0},
            {"id": "minimal", "injection_limit": 3},
            {"id": "moderate", "injection_limit": 10},
            {"id": "aggressive", "injection_limit": 25},
        ],
    },
    "retrieval_policy": {
        "description": "Retrieval scoring weights and thresholds",
        "variants": [
            {"id": "lexical-heavy", "lexical_weight": 6, "semantic_weight": 1},
            {"id": "balanced", "lexical_weight": 4, "semantic_weight": 3},
            {"id": "semantic-heavy", "lexical_weight": 2, "semantic_weight": 5},
        ],
    },
    "query_family_selection": {
        "description": "How many query families to target",
        "variants": [
            {"id": "conservative", "max_families": 3},
            {"id": "moderate", "max_families": 7},
            {"id": "aggressive", "max_families": 15},
        ],
    },
    "gating_threshold": {
        "description": "Minimum content tokens to trigger retrieval",
        "variants": [
            {"id": "strict", "min_tokens": 5},
            {"id": "normal", "min_tokens": 3},
            {"id": "permissive", "min_tokens": 1},
        ],
    },
}


def run_optimization(
    store: MemoryStore,
    *,
    search_space: dict[str, Any] | None = None,
    max_iterations: int = 10,
    now: str | None = None,
) -> dict[str, Any]:
    """Run a toy harness optimization workflow.

    Evaluates variants from the search space and reports the best configuration.
    In production, this would run actual task evaluations. This implementation
    provides the structural scaffolding with deterministic scoring.
    """
    timestamp = now or to_iso(utc_now())
    run_id = stable_id("harness-opt", timestamp)
    space = search_space or DEFAULT_SEARCH_SPACE

    proposals: list[dict[str, Any]] = []
    baseline_score = 0.5
    best_score = baseline_score
    best_variant_id = "baseline"
    iteration = 0

    for dimension, config in space.items():
        variants = config.get("variants", [])
        for variant in variants:
            if iteration >= max_iterations:
                break
            iteration += 1

            variant_id = f"{dimension}:{variant.get('id', iteration)}"

            # Score is deterministic based on variant properties
            # In production, this would run actual evals
            score = _score_variant(store, dimension, variant)

            proposals.append({
                "variant_id": variant_id,
                "description": f"{dimension} = {variant.get('id', 'unknown')}",
                "score": round(score, 4),
                "details": variant,
            })

            if score > best_score:
                best_score = score
                best_variant_id = variant_id

    improvement_delta = round(best_score - baseline_score, 4)

    report = HarnessOptimizationReport(
        run_id=run_id,
        status="completed",
        started_at=timestamp,
        ended_at=to_iso(utc_now()),
        search_space=space,
        proposals=proposals,
        winning_variant_id=best_variant_id,
        baseline_score=baseline_score,
        best_score=round(best_score, 4),
        improvement_delta=improvement_delta,
        iterations=iteration,
    )

    payload = report.to_dict()
    store.write_harness_report(run_id, payload)
    return payload


def _score_variant(
    store: MemoryStore,
    dimension: str,
    variant: dict[str, Any],
) -> float:
    """Score a harness variant.

    Deterministic scoring based on heuristic preferences.
    Production would run actual task evaluations.
    """
    durable_count = len(store.load_durable_records())
    learned_count = len(store.load_learned_context_records())
    total_memory = durable_count + learned_count

    base = 0.5

    if dimension == "memory_injection":
        limit = int(variant.get("injection_limit", 0))
        if total_memory == 0:
            return base
        optimal_ratio = min(1.0, limit / max(1, total_memory))
        if optimal_ratio < 0.1:
            return base - 0.05
        elif optimal_ratio > 0.8:
            return base + 0.02
        else:
            return float(base + 0.1 * optimal_ratio)

    elif dimension == "retrieval_policy":
        # Balanced tends to work best
        lex = int(variant.get("lexical_weight", 4))
        sem = int(variant.get("semantic_weight", 3))
        balance = 1.0 - abs(lex - sem) / max(lex, sem)
        return float(base + 0.1 * balance)

    elif dimension == "query_family_selection":
        max_fam = variant.get("max_families", 7)
        if max_fam < 3:
            return base - 0.02
        elif max_fam > 12:
            return base + 0.01
        else:
            return base + 0.05

    elif dimension == "gating_threshold":
        min_tokens = variant.get("min_tokens", 3)
        if min_tokens >= 5:
            return base + 0.03
        elif min_tokens <= 1:
            return base - 0.03
        else:
            return base + 0.05

    return base


def load_optimization_reports(store: MemoryStore) -> list[dict[str, Any]]:
    """Load all harness optimization reports."""
    from .util import read_json

    reports: list[dict[str, Any]] = []
    for path in sorted(store.audit_harness_dir.glob("*.json")):
        payload = read_json(path, {})
        if isinstance(payload, dict):
            reports.append(payload)
    return reports
