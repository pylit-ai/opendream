from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .util import CLI_JSON_VERSION, SCHEMA_ROOT


def _payload_sha256(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def top_level_command_names() -> tuple[str, ...]:
    """Return top-level CLI command names; keep aligned with build_parser()."""
    from .cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices is not None:
            return tuple(sorted(choices.keys()))
    return ()


CONTRACT_EXPORT_DOCUMENT_VERSION = "2"
CONTRACT_SCHEMA_FILE = "contract-export.schema.json"


def build_contract_export(_workspace: Path) -> dict[str, Any]:
    """Assemble the machine-readable OpenDream CLI/schema contract."""
    commands = [{"name": n} for n in top_level_command_names()]
    schemas = [{"name": n} for n in sorted(p.name for p in SCHEMA_ROOT.glob("*.schema.json"))]
    output_version_map = {
        "cli_json": str(CLI_JSON_VERSION),
        "contract_export": CONTRACT_EXPORT_DOCUMENT_VERSION,
    }
    minimal_event: dict[str, Any] = {
        "kind": "task_outcome",
        "content": "example",
        "message_ref": "contract-export-example",
        "channel": "cli",
        "scope": "project",
    }
    examples: list[dict[str, Any]] = [
        {
            "id": "memory-event-minimal",
            "summary": "Minimal memory event shape used for hashing smoke",
            "payload_sha256": _payload_sha256(minimal_event),
            "schema_name": "memory-event.schema.json",
        },
        {
            "id": "empty-object",
            "summary": "Degenerate object for parser sanity",
            "payload_sha256": _payload_sha256({}),
        },
    ]
    # Semantic adapter inventory (438 bundle)
    adapter_inventory = [
        {
            "adapter_id": "codex-account",
            "execution_owner": "opendream-local",
            "auth_source": "chatgpt-account",
            "ingest_mode": "direct-report",
        },
        {
            "adapter_id": "claude-scheduled-task",
            "execution_owner": "vendor-runtime",
            "auth_source": "claude-account-task",
            "ingest_mode": "delegated-envelope",
        },
        {
            "adapter_id": "cursor-automation",
            "execution_owner": "vendor-runtime",
            "auth_source": "cursor-account-automation",
            "ingest_mode": "delegated-envelope",
        },
    ]
    auth_matrix = {
        "strategies": [
            "deterministic",
            "direct-provider",
            "codex-account",
            "claude-scheduled-task",
            "cursor-automation",
        ],
        "unsupported": ["gemini-oauth-reuse"],
    }

    return {
        "opendream_version": __version__,
        "cli_output_version": CLI_JSON_VERSION,
        "contract_schema_version": CONTRACT_SCHEMA_FILE,
        "command_inventory": commands,
        "schema_inventory": schemas,
        "output_version_map": output_version_map,
        "supported_engine_ids": [
            "builtin://projection-engine",
            "builtin://semantic-dreamer",
            "builtin://harness-optimizer",
            "builtin://claim-verifier",
            "builtin://transcript-prober",
            "builtin://reconciliation-sweeper",
        ],
        "supported_package_targets": [
            "codex",
            "claude-code",
            "cursor",
            "github-copilot",
        ],
        "example_payloads": examples,
        "semantic_adapter_inventory": adapter_inventory,
        "semantic_auth_matrix": auth_matrix,
    }
