"""Semantic setup wizard — execution strategy detection and recommendation.

Implements WS3 (T11-T17): setup wizard, adapter detection, recommendation
policies for no-extra-key and direct-provider preferences, machine-readable
setup report output, negative recommendations, and fixture tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .semantic_adapters import (
    BUILTIN_MANIFESTS,
    detect_all_tools,
    scaffold_adapter,
)
from .storage import MemoryStore
from .validation import validate_document

EXECUTION_STRATEGIES = (
    "deterministic",
    "direct-provider",
    "codex-account",
    "claude-scheduled-task",
    "cursor-automation",
)

UNSUPPORTED_STRATEGIES = ("gemini-oauth-reuse",)


def _is_trusted_environment() -> bool:
    """Heuristic: return False if running in a known shared CI context."""
    import os

    ci_vars = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS", "BUILDKITE")
    return not any(os.environ.get(v) for v in ci_vars)


def _build_candidate(
    strategy: str,
    detected_tools: list[str],
    preference: str,
) -> dict[str, Any]:
    """Build a candidate entry for a strategy."""
    if strategy == "deterministic":
        return {
            "strategy": "deterministic",
            "supported": True,
            "requires_key": False,
            "reason": "always available, no model call",
            "rank": 100,
        }

    if strategy == "direct-provider":
        return {
            "strategy": "direct-provider",
            "supported": True,
            "requires_key": True,
            "reason": "requires explicit API key (ANTHROPIC_API_KEY or OPENAI_API_KEY)",
            "rank": 10 if preference == "direct-provider" else 50,
        }

    if strategy == "codex-account":
        codex_ok = "codex" in detected_tools
        trusted = _is_trusted_environment()
        supported = codex_ok and trusted
        reason = "Codex CLI detected on trusted infrastructure" if supported else (
            "Codex CLI not detected" if not codex_ok else "untrusted/shared CI environment"
        )
        return {
            "strategy": "codex-account",
            "supported": supported,
            "requires_key": False,
            "reason": reason,
            "rank": 20 if (preference == "no-extra-key" and supported) else 60,
        }

    if strategy == "claude-scheduled-task":
        claude_ok = "claude" in detected_tools
        return {
            "strategy": "claude-scheduled-task",
            "supported": claude_ok,
            "requires_key": False,
            "reason": "Claude detected" if claude_ok else "Claude not detected",
            "rank": 30 if (preference == "no-extra-key" and claude_ok) else 70,
        }

    if strategy == "cursor-automation":
        cursor_ok = "cursor" in detected_tools
        return {
            "strategy": "cursor-automation",
            "supported": cursor_ok,
            "requires_key": False,
            "reason": "Cursor detected" if cursor_ok else "Cursor not detected",
            "rank": 40 if (preference == "no-extra-key" and cursor_ok) else 80,
        }

    return {
        "strategy": strategy,
        "supported": False,
        "requires_key": False,
        "reason": "unknown strategy",
        "rank": 999,
    }


def _build_blocked_strategies(detected_tools: list[str]) -> list[dict[str, Any]]:
    """Build the blocked/unsupported strategies list."""
    blocked: list[dict[str, Any]] = []

    # Gemini is always blocked
    gemini_detected = "gemini" in detected_tools
    blocked.append({
        "strategy": "gemini-oauth-reuse",
        "reason": (
            "Gemini CLI OAuth reuse into OpenDream is unsupported. "
            "Use direct-provider mode with an explicit API key, or deterministic-only."
        ),
        "detected": gemini_detected,
    })

    return blocked


def semantic_setup(
    workspace: Path,
    preference: str = "no-extra-key",
) -> dict[str, Any]:
    """Run the semantic setup wizard and produce a machine-readable report.

    Args:
        workspace: path to workspace root
        preference: 'no-extra-key' or 'direct-provider'

    Returns:
        Setup report dict, validated against semantic-setup-report.schema.json.
    """
    if preference not in ("no-extra-key", "direct-provider"):
        raise ValueError(f"invalid preference: {preference!r}; use 'no-extra-key' or 'direct-provider'")

    detection = detect_all_tools(workspace)
    detected_tools = detection["detected_tools"]

    # Build candidates
    candidates: list[dict[str, Any]] = []
    for strategy in EXECUTION_STRATEGIES:
        candidate = _build_candidate(strategy, detected_tools, preference)
        candidates.append(candidate)

    # Sort by rank (lower is better)
    candidates.sort(key=lambda c: c.get("rank", 999))

    # Pick recommendation: first supported non-deterministic candidate
    recommended = "deterministic"
    for c in candidates:
        if c["supported"] and c["strategy"] != "deterministic":
            recommended = c["strategy"]
            break

    # Build blocked strategies
    blocked = _build_blocked_strategies(detected_tools)

    # Build next actions
    next_actions: list[str] = []
    if recommended == "deterministic":
        next_actions.append(
            "No vendor adapter detected. Install Codex, Claude, or Cursor"
            " for no-extra-key semantic mode, or configure a direct provider API key."
        )
    elif recommended == "direct-provider":
        next_actions.append(
            "Set ANTHROPIC_API_KEY or OPENAI_API_KEY,"
            " then run: opendream semantic setup --workspace . --prefer direct-provider --apply"
        )
    elif recommended in BUILTIN_MANIFESTS:
        next_actions.append(
            f"Run: opendream semantic setup --workspace . --prefer {preference} --apply"
        )
        next_actions.append("Run: opendream dream worker --workspace . --once --mode auto")

    # Build warnings
    warnings: list[str] = []
    if "gemini" in detected_tools:
        warnings.append(
            "Gemini CLI detected but OAuth reuse is unsupported."
            " Use direct-provider or deterministic mode."
        )
    if not _is_trusted_environment() and recommended == "codex-account":
        warnings.append("Codex account-auth should not be used on shared or untrusted CI. Falling back.")
        recommended = "deterministic"

    report: dict[str, Any] = {
        "workspace": str(workspace),
        "preference": preference,
        "detected_tools": detected_tools,
        "recommended_strategy": recommended,
        "candidates": candidates,
        "blocked_strategies": blocked,
        "next_actions": next_actions,
        "warnings": warnings,
    }

    validate_document("semantic-setup-report.schema.json", report)
    return report


def apply_setup_recommendation(
    store: MemoryStore,
    report: dict[str, Any],
    *,
    scaffold: bool = True,
) -> dict[str, Any]:
    """Apply the setup wizard recommendation to the workspace config.

    Updates semantic config with the recommended execution strategy
    and optionally scaffolds adapter artifacts.
    """
    strategy = report.get("recommended_strategy", "deterministic")
    preference = report.get("preference", "no-extra-key")

    config = store.load_semantic_config()
    if strategy != "deterministic":
        config["mode"] = "semantic"
    config["execution_strategy"] = strategy
    config["preferred_auth_mode"] = preference

    if strategy in BUILTIN_MANIFESTS:
        config["active_adapter"] = strategy
    else:
        config["active_adapter"] = None

    supported = [
        c["strategy"]
        for c in report.get("candidates", [])
        if c.get("supported")
    ]
    config["candidate_strategies"] = supported

    store.save_semantic_config(config)

    result: dict[str, Any] = {
        "applied_strategy": strategy,
        "applied_preference": preference,
        "config_updated": True,
    }

    if scaffold and strategy in BUILTIN_MANIFESTS:
        workspace = Path(report["workspace"])
        scaffold_result = scaffold_adapter(workspace, strategy)
        result["scaffold"] = scaffold_result

    return result
