"""Semantic adapter registry — vendor-specific execution manifests and scaffolding.

Implements WS4-WS6 (T18-T38): adapter manifests, detection, scaffolding,
status/health reporting, and structured-output invocation contracts for
codex-account, claude-scheduled-task, and cursor-automation adapters.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .util import write_json
from .validation import validate_document

VALID_ADAPTER_KINDS = frozenset({
    "codex-account",
    "claude-scheduled-task",
    "cursor-automation",
})

VALID_EXECUTION_OWNERS = frozenset({"opendream-local", "vendor-runtime"})

VALID_AUTH_SOURCES = frozenset({
    "chatgpt-account",
    "claude-account-task",
    "cursor-account-automation",
    "cursor-api-key",
    "provider-api-key",
})

VALID_INGEST_MODES = frozenset({"direct-report", "delegated-envelope"})

# --- Adapter manifests -------------------------------------------------------

CODEX_ACCOUNT_MANIFEST: dict[str, Any] = {
    "adapter_id": "codex-account",
    "kind": "codex-account",
    "execution_owner": "opendream-local",
    "auth_source": "chatgpt-account",
    "supports_local_files": True,
    "supports_background_schedule": False,
    "ingest_mode": "direct-report",
    "trust_boundary": "trusted-local-or-controlled-infrastructure-only",
    "notes": [
        "Uses Codex CLI subprocess with account-backed auth (~/.codex/auth.json).",
        "Do NOT use on shared runners or untrusted infrastructure.",
        "Do NOT parse or refresh tokens manually; let Codex manage its own auth cache.",
    ],
}

CLAUDE_SCHEDULED_TASK_MANIFEST: dict[str, Any] = {
    "adapter_id": "claude-scheduled-task",
    "kind": "claude-scheduled-task",
    "execution_owner": "vendor-runtime",
    "auth_source": "claude-account-task",
    "supports_local_files": True,
    "supports_background_schedule": True,
    "ingest_mode": "delegated-envelope",
    "trust_boundary": "vendor-owned-runtime",
    "notes": [
        "Claude runs the semantic refresh as a scheduled task or command/skill invocation.",
        "Results return via delegated semantic envelope into .opendream/inbox/semantic/.",
        "OpenDream does NOT directly borrow Claude account auth.",
    ],
}

CURSOR_AUTOMATION_MANIFEST: dict[str, Any] = {
    "adapter_id": "cursor-automation",
    "kind": "cursor-automation",
    "execution_owner": "vendor-runtime",
    "auth_source": "cursor-account-automation",
    "supports_local_files": False,
    "supports_background_schedule": True,
    "ingest_mode": "delegated-envelope",
    "trust_boundary": "vendor-owned-runtime",
    "notes": [
        "A Cursor Automation runs a background cloud agent on a schedule or event trigger.",
        "Results are written as envelope artifacts into .opendream/inbox/semantic/cursor-automation/.",
        "The no-extra-key default is the account-backed automation UI path, NOT the API.",
    ],
}

BUILTIN_MANIFESTS: dict[str, dict[str, Any]] = {
    "codex-account": CODEX_ACCOUNT_MANIFEST,
    "claude-scheduled-task": CLAUDE_SCHEDULED_TASK_MANIFEST,
    "cursor-automation": CURSOR_AUTOMATION_MANIFEST,
}


def get_adapter_manifest(adapter_id: str) -> dict[str, Any] | None:
    """Return the builtin manifest for a given adapter id."""
    return BUILTIN_MANIFESTS.get(adapter_id)


def list_adapter_manifests() -> list[dict[str, Any]]:
    """Return all builtin semantic adapter manifests."""
    return list(BUILTIN_MANIFESTS.values())


def validate_adapter_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a semantic adapter manifest against the schema."""
    validate_document("semantic-adapter-manifest.schema.json", manifest)
    return {"valid": True, "adapter_id": manifest.get("adapter_id", "")}


# --- Adapter detection -------------------------------------------------------

CODEX_DETECTION_PATHS = [
    Path.home() / ".codex",
    Path.home() / ".codex" / "auth.json",
]

CLAUDE_DETECTION_PATHS = [
    Path.home() / ".claude",
    Path.home() / ".claude" / "settings.json",
]

CURSOR_DETECTION_PATHS = [
    Path.home() / ".cursor",
    Path.home() / "Library" / "Application Support" / "Cursor",
]


def detect_tool(tool_name: str, workspace: Path | None = None) -> dict[str, Any]:
    """Detect whether a given tool is available on this system."""
    result: dict[str, Any] = {
        "tool": tool_name,
        "detected": False,
        "binary_found": False,
        "config_found": False,
    }

    # Check for binary
    binary = shutil.which(tool_name.split("-")[0])
    if binary:
        result["binary_found"] = True

    # Check for config paths
    paths_map = {
        "codex": CODEX_DETECTION_PATHS,
        "claude": CLAUDE_DETECTION_PATHS,
        "cursor": CURSOR_DETECTION_PATHS,
    }
    tool_key = tool_name.split("-")[0]
    for path in paths_map.get(tool_key, []):
        if path.exists():
            result["config_found"] = True
            break

    result["detected"] = result["binary_found"] or result["config_found"]
    return result


def detect_all_tools(workspace: Path | None = None) -> dict[str, Any]:
    """Detect all known tools and return a summary."""
    tools = ["codex", "claude", "cursor"]
    results: list[dict[str, Any]] = []
    detected_names: list[str] = []
    for tool in tools:
        r = detect_tool(tool, workspace)
        results.append(r)
        if r["detected"]:
            detected_names.append(tool)
    return {
        "detected_tools": detected_names,
        "details": results,
    }


# --- Adapter status -----------------------------------------------------------

def adapter_status(
    workspace: Path,
    active_strategy: str = "deterministic",
    active_adapter: str | None = None,
) -> dict[str, Any]:
    """Build semantic adapter status report for a workspace."""
    detection = detect_all_tools(workspace)
    detected = detection["detected_tools"]

    candidates: list[dict[str, Any]] = []

    # Always include deterministic
    candidates.append({
        "strategy": "deterministic",
        "supported": True,
        "reason": "always available as fallback",
    })

    # Direct provider
    candidates.append({
        "strategy": "direct-provider",
        "supported": True,
        "reason": "requires explicit API key configuration",
    })

    # Codex
    codex_detected = "codex" in detected
    candidates.append({
        "strategy": "codex-account",
        "supported": codex_detected,
        "reason": "Codex CLI detected" if codex_detected else "Codex CLI not detected",
    })

    # Claude
    claude_detected = "claude" in detected
    candidates.append({
        "strategy": "claude-scheduled-task",
        "supported": claude_detected,
        "reason": "Claude detected" if claude_detected else "Claude not detected",
    })

    # Cursor
    cursor_detected = "cursor" in detected
    candidates.append({
        "strategy": "cursor-automation",
        "supported": cursor_detected,
        "reason": "Cursor detected" if cursor_detected else "Cursor not detected",
    })

    # Status
    if (
        active_strategy in ("deterministic", "direct-provider")
        or any(c["strategy"] == active_strategy and c["supported"] for c in candidates)
    ):
        status = "ok"
    else:
        status = "degraded"

    auth_source = _strategy_to_auth_source(active_strategy)

    report: dict[str, Any] = {
        "workspace": str(workspace),
        "active_strategy": active_strategy,
        "auth_source": auth_source,
        "candidates": candidates,
        "status": status,
        "last_run_owner": active_adapter or active_strategy,
        "last_error": None,
        "next_steps": [],
    }

    validate_document("semantic-adapter-status.schema.json", report)
    return report


def _strategy_to_auth_source(strategy: str) -> str:
    """Map execution strategy to its auth source."""
    mapping = {
        "deterministic": "none",
        "direct-provider": "provider-api-key",
        "codex-account": "chatgpt-account",
        "claude-scheduled-task": "claude-account-task",
        "cursor-automation": "cursor-account-automation",
    }
    return mapping.get(strategy, "none")


# --- Adapter scaffolding ------------------------------------------------------

def scaffold_adapter(
    workspace: Path,
    adapter_id: str,
) -> dict[str, Any]:
    """Generate scaffold artifacts for a semantic adapter."""
    manifest = get_adapter_manifest(adapter_id)
    if manifest is None:
        raise ValueError(f"unknown adapter: {adapter_id}")

    scaffold_dir = workspace / ".opendream" / "semantic-adapters" / adapter_id
    scaffold_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest
    write_json(scaffold_dir / "manifest.json", manifest)

    created_files: list[str] = [str(scaffold_dir / "manifest.json")]

    if adapter_id == "codex-account":
        created_files.extend(_scaffold_codex(workspace, scaffold_dir))
    elif adapter_id == "claude-scheduled-task":
        created_files.extend(_scaffold_claude(workspace, scaffold_dir))
    elif adapter_id == "cursor-automation":
        created_files.extend(_scaffold_cursor(workspace, scaffold_dir))

    # Ensure inbox directory exists for delegated adapters
    if manifest.get("ingest_mode") == "delegated-envelope":
        inbox = workspace / ".opendream" / "inbox" / "semantic" / adapter_id
        inbox.mkdir(parents=True, exist_ok=True)

    return {
        "adapter_id": adapter_id,
        "scaffold_dir": str(scaffold_dir),
        "created_files": created_files,
        "ingest_mode": manifest.get("ingest_mode"),
    }


def _scaffold_codex(workspace: Path, scaffold_dir: Path) -> list[str]:
    """Scaffold Codex-specific wrapper and config docs."""
    docs = scaffold_dir / "README.md"
    docs.write_text(
        "# Codex account-auth semantic adapter\n\n"
        "This adapter uses the Codex CLI as a local subprocess for semantic synthesis.\n\n"
        "## Requirements\n"
        "- Codex CLI installed and signed in (`codex auth login`)\n"
        "- Trusted local or controlled infrastructure only\n"
        "- Do NOT use on shared CI runners\n\n"
        "## Trust boundary\n"
        "- `~/.codex/auth.json` is treated as a secret\n"
        "- OpenDream never reads or logs auth token contents\n"
        "- Let Codex manage its own auth cache\n\n"
        "## Usage\n"
        "```\n"
        "opendream semantic setup --workspace . --prefer no-extra-key\n"
        "opendream semantic adapters scaffold --workspace . --adapter codex-account\n"
        "```\n",
        encoding="utf-8",
    )

    invocation = scaffold_dir / "invocation-contract.json"
    write_json(invocation, {
        "adapter_id": "codex-account",
        "invocation_type": "subprocess",
        "binary": "codex",
        "structured_output": True,
        "trust_boundary": "trusted-local-or-controlled-infrastructure-only",
        "concurrency": "single-instance",
    })

    return [str(docs), str(invocation)]


def _scaffold_claude(workspace: Path, scaffold_dir: Path) -> list[str]:
    """Scaffold Claude scheduled-task command/skill and task templates."""
    docs = scaffold_dir / "README.md"
    docs.write_text(
        "# Claude scheduled-task semantic adapter\n\n"
        "This adapter delegates semantic refresh to Claude as a scheduled task.\n"
        "Claude runs the prompt and writes a delegated semantic envelope back.\n\n"
        "## Supported submodes\n"
        "- `claude-desktop-task` — preferred when local files/tools are needed\n"
        "- `claude-cloud-task` — preferred when durability matters\n"
        "- GitHub Actions fallback — for repo-automation contexts\n\n"
        "## Key rule\n"
        "OpenDream docs describe this as **Claude-owned execution with OpenDream-owned ingest**,\n"
        "NOT as OpenDream directly using Claude account auth.\n\n"
        "## Usage\n"
        "```\n"
        "opendream semantic adapters scaffold --workspace . --adapter claude-scheduled-task\n"
        "opendream semantic ingest --workspace . --scan-inbox\n"
        "```\n",
        encoding="utf-8",
    )

    task_template = scaffold_dir / "task-template.md"
    task_template.write_text(
        "# Semantic refresh task for OpenDream\n\n"
        "Run the OpenDream semantic refresh and write the result envelope.\n\n"
        "## Instructions\n"
        "1. Read the workspace memory store and recent episodes\n"
        "2. Identify anticipated query families\n"
        "3. Synthesize learned-context proposals\n"
        "4. Write a delegated semantic envelope to:\n"
        "   `.opendream/inbox/semantic/claude-scheduled-task/<timestamp>-<run-id>.json`\n"
        "5. The envelope must conform to `delegated-semantic-envelope.schema.json`\n",
        encoding="utf-8",
    )

    return_contract = scaffold_dir / "return-contract.json"
    write_json(return_contract, {
        "adapter_id": "claude-scheduled-task",
        "return_mode": "delegated-envelope",
        "envelope_schema": "delegated-semantic-envelope.schema.json",
        "inbox_path": ".opendream/inbox/semantic/claude-scheduled-task/",
        "naming_convention": "<ISO-timestamp>-<run-id>.json",
    })

    return [str(docs), str(task_template), str(return_contract)]


def _scaffold_cursor(workspace: Path, scaffold_dir: Path) -> list[str]:
    """Scaffold Cursor automation prompt/instructions and return path."""
    docs = scaffold_dir / "README.md"
    docs.write_text(
        "# Cursor automation semantic adapter\n\n"
        "This adapter delegates semantic refresh to a Cursor Automation.\n"
        "The automation writes a bounded envelope artifact into the repo.\n\n"
        "## Account-backed UI path (default, no extra key)\n"
        "Use the Cursor Automations UI to set up a recurring semantic refresh.\n\n"
        "## API-key programmatic path (optional)\n"
        "For programmatic use, configure a Cursor API key separately.\n"
        "This is NOT the default recommendation.\n\n"
        "## Artifact return path\n"
        "`.opendream/inbox/semantic/cursor-automation/<timestamp>-<run-id>.json`\n\n"
        "## Usage\n"
        "```\n"
        "opendream semantic adapters scaffold --workspace . --adapter cursor-automation\n"
        "opendream semantic ingest --workspace . --scan-inbox\n"
        "```\n",
        encoding="utf-8",
    )

    automation_prompt = scaffold_dir / "automation-prompt.md"
    automation_prompt.write_text(
        "# OpenDream semantic refresh automation\n\n"
        "## Objective\n"
        "Run a semantic refresh cycle for the OpenDream memory workspace.\n\n"
        "## Steps\n"
        "1. Read recent transcript episodes and memory state\n"
        "2. Identify anticipated query families from usage patterns\n"
        "3. Synthesize learned-context proposals\n"
        "4. Write a delegated semantic envelope to:\n"
        "   `.opendream/inbox/semantic/cursor-automation/<timestamp>-<run-id>.json`\n"
        "5. The envelope must validate against `delegated-semantic-envelope.schema.json`\n\n"
        "## Important\n"
        "- Do NOT attempt to modify durable memory directly\n"
        "- Write only to the designated inbox path\n"
        "- Include provenance metadata in the envelope\n",
        encoding="utf-8",
    )

    return_contract = scaffold_dir / "return-contract.json"
    write_json(return_contract, {
        "adapter_id": "cursor-automation",
        "return_mode": "delegated-envelope",
        "envelope_schema": "delegated-semantic-envelope.schema.json",
        "inbox_path": ".opendream/inbox/semantic/cursor-automation/",
        "naming_convention": "<ISO-timestamp>-<run-id>.json",
    })

    return [str(docs), str(automation_prompt), str(return_contract)]
