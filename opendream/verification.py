from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .activation import detect_agents, inspect_target
from .adapter_loader import load_bundled_adapters
from .storage import MemoryStore
from .util import CLI_JSON_VERSION, stable_id, to_iso, utc_now, write_json

REPORTS_DIR = Path(".opendream/reports")
ACTIVATION_CAPTURE_LATEST_PATH = REPORTS_DIR / "activation-capture-latest.json"

CAPTURE_TIMEOUT_SECONDS = 90


def verify_activation_capture(store: MemoryStore, *, targets: str) -> dict[str, Any]:
    """Run a mutating capture smoke through generated agent activation surfaces."""

    generated_at = to_iso(utc_now())
    workspace = store.workspace
    if not workspace.exists():
        return _failed_setup_report(
            store,
            generated_at=generated_at,
            targets=targets,
            warning=f"workspace path does not exist: {workspace}",
            next_action=f"create the workspace, then run `opendream init --workspace {workspace}`",
        )
    if not store.is_initialized():
        return _failed_setup_report(
            store,
            generated_at=generated_at,
            targets=targets,
            warning="workspace is not initialized",
            next_action=f"run `opendream init --workspace {workspace}`",
        )

    store.ensure_layout()
    selected = _select_capture_targets(store, targets)
    if not selected:
        return _write_capture_report(
            store,
            {
                "cli_output_version": CLI_JSON_VERSION,
                "generated_at": generated_at,
                "workspace": str(workspace),
                "selector": targets,
                "selected_targets": [],
                "status": "failed",
                "results": [],
                "event_delta": 0,
                "durable_record_delta": 0,
                "warnings": ["no configured supported agent surfaces were detected"],
                "next_action": f"run `opendream activate --workspace {workspace} --targets <target>`",
            },
        )

    run_id = stable_id("activation-capture", workspace.resolve(), generated_at, ",".join(selected))
    before_event_ids = _event_ids(store)
    before_record_count = len(store.load_durable_records())
    results = [_verify_target(store, target, generated_at=generated_at, run_id=run_id) for target in selected]
    after_event_ids = _event_ids(store)
    after_record_count = len(store.load_durable_records())

    event_delta = len(after_event_ids - before_event_ids)
    durable_delta = after_record_count - before_record_count
    status = "passed" if all(item["status"] == "passed" for item in results) else "failed"
    warnings = sorted({warning for result in results for warning in result.get("warnings", [])})
    next_action = "no action required"
    if status != "passed":
        failed = [result["target_kind"] for result in results if result["status"] != "passed"]
        next_action = (
            f"run `opendream activate --workspace {workspace} --targets {','.join(failed)} --repair`, "
            "then rerun `opendream verify activation-capture`"
        )

    return _write_capture_report(
        store,
        {
            "cli_output_version": CLI_JSON_VERSION,
            "generated_at": generated_at,
            "workspace": str(workspace),
            "selector": targets,
            "selected_targets": selected,
            "status": status,
            "results": results,
            "event_delta": event_delta,
            "durable_record_delta": durable_delta,
            "warnings": warnings,
            "next_action": next_action,
        },
    )


def _failed_setup_report(
    store: MemoryStore,
    *,
    generated_at: str,
    targets: str,
    warning: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "cli_output_version": CLI_JSON_VERSION,
        "generated_at": generated_at,
        "workspace": str(store.workspace),
        "selector": targets,
        "selected_targets": [],
        "status": "failed",
        "results": [],
        "event_delta": 0,
        "durable_record_delta": 0,
        "warnings": [warning],
        "next_action": next_action,
    }


def _select_capture_targets(store: MemoryStore, selector: str) -> list[str]:
    supported = load_bundled_adapters()
    supported_ids = set(supported)
    if selector == "all-supported":
        return sorted(supported_ids)
    if selector == "configured":
        return [
            item["target_kind"]
            for item in detect_agents(store.workspace)
            if item["configured"] and item["target_kind"] in supported_ids
        ]
    requested = [part.strip() for part in selector.split(",") if part.strip()]
    if not requested:
        raise ValueError("activation-capture requires at least one target")
    unknown = [target for target in requested if target not in supported_ids]
    if unknown:
        raise ValueError(f"unsupported activation-capture target(s): {', '.join(unknown)}")
    return requested


def _verify_target(store: MemoryStore, target: str, *, generated_at: str, run_id: str) -> dict[str, Any]:
    workspace = store.workspace
    manifest = load_bundled_adapters()[target]
    inspection = inspect_target(store, target)
    instruction_only = str(manifest["activation_mode"]) == "managed_prompt_snippet"
    summary = _diagnostic_summary(target, run_id)
    query = (
        f"{target} activation-capture diagnostic query. "
        f"Retrieve context before proving capture for run_id={run_id}."
    )
    before_event_ids = _event_ids(store)
    before_record_count = len(store.load_durable_records())

    plan = _command_plan(workspace, target, manifest, query=query, summary=summary)
    missing_paths = [str(path.relative_to(workspace)) for path in plan["required_paths"] if not path.exists()]
    if missing_paths:
        return _target_result(
            target,
            manifest,
            inspection,
            instruction_only=instruction_only,
            status="failed",
            pre_context_ok=False,
            post_capture_ok=False,
            event_delta=0,
            durable_record_delta=0,
            warnings=[f"missing activation surface(s): {', '.join(missing_paths)}"],
            next_action=f"run `opendream activate --workspace {workspace} --targets {target} --repair`",
        )

    env = _verification_env(target, query=query, summary=summary)
    pre_result = _run_command(plan["pre"], workspace=workspace, env=env) if plan["pre"] else None
    post_result = _run_command(plan["post"], workspace=workspace, env=env)

    after_event_ids = _event_ids(store)
    after_record_count = len(store.load_durable_records())
    event_delta = len(after_event_ids - before_event_ids)
    durable_delta = after_record_count - before_record_count
    pre_context_ok = _context_file(workspace, target).exists() and (pre_result is None or pre_result["returncode"] == 0)
    post_capture_ok = post_result["returncode"] == 0 and event_delta > 0 and durable_delta > 0
    warnings: list[str] = []
    if pre_result is not None and pre_result["returncode"] != 0:
        warnings.append(_command_warning("pre-task", pre_result))
    if post_result["returncode"] != 0:
        warnings.append(_command_warning("post-task", post_result))
    if event_delta <= 0:
        warnings.append("post-task did not append an event")
    if durable_delta <= 0:
        warnings.append("post-task did not produce a durable memory record")
    if instruction_only:
        warnings.append("host auto-invocation is instruction-only; direct hook execution was verified")

    return _target_result(
        target,
        manifest,
        inspection,
        instruction_only=instruction_only,
        status="passed" if pre_context_ok and post_capture_ok else "failed",
        pre_context_ok=pre_context_ok,
        post_capture_ok=post_capture_ok,
        event_delta=event_delta,
        durable_record_delta=durable_delta,
        warnings=warnings,
        next_action=(
            "no action required"
            if pre_context_ok and post_capture_ok
            else f"run `opendream activate --workspace {workspace} --targets {target} --repair`"
        ),
        pre_result=pre_result,
        post_result=post_result,
    )


def _diagnostic_summary(target: str, run_id: str) -> str:
    unique_terms = {
        "claude-code": "Claude settings stop hook transcript prompt submit session fallback capture.",
        "codex": "Codex wrapper command exit shell agents configuration child process capture.",
        "cursor": "Cursor mdc rule editor project instruction snippet shell capture.",
        "hermes": "Hermes project context prompt instruction block terminal capture.",
        "github-copilot": "GitHub repository copilot instructions pull request editor capture.",
        "openclaw": "OpenClaw planner worker event map preplan posttask capture.",
    }
    terms = unique_terms.get(target, f"{target} adapter hook capture.")
    return f"Use {target} marker {target}-activation-capture. {terms} run_id={run_id}."


def _command_plan(
    workspace: Path,
    target: str,
    manifest: dict[str, Any],
    *,
    query: str,
    summary: str,
) -> dict[str, Any]:
    hooks = workspace / ".opendream" / "hooks"
    if target == "claude-code":
        pre = hooks / "claude-pre-task.sh"
        post = hooks / "claude-post-task.sh"
        return {
            "required_paths": [pre, post],
            "pre": ["sh", str(pre), query],
            "post": ["sh", str(post), summary],
        }
    if target == "codex":
        wrapper = workspace / ".opendream" / "bin" / "codex-task-wrapper.sh"
        return {
            "required_paths": [wrapper],
            "pre": None,
            "post": [
                "sh",
                str(wrapper),
                "--query",
                query,
                "--summary",
                summary,
                "--",
                "/bin/sh",
                "-c",
                "exit 0",
            ],
        }
    if target == "openclaw":
        hook = hooks / "openclaw-hooks.sh"
        return {
            "required_paths": [hook],
            "pre": ["sh", str(hook), "pre-plan", query],
            "post": ["sh", str(hook), "post-task", summary],
        }
    raw_install = manifest.get("install")
    install: dict[str, Any] = raw_install if isinstance(raw_install, dict) else {}
    tag = str(install.get("hook_tag") or target)
    pre = hooks / f"{tag}-pre-task.sh"
    post = hooks / f"{tag}-post-task.sh"
    return {
        "required_paths": [pre, post],
        "pre": ["sh", str(pre), query],
        "post": ["sh", str(post), summary],
    }


def _verification_env(target: str, *, query: str, summary: str) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("OPENDREAM_BIN", _current_opendream_bin())
    env.update(
        {
            "OPENDREAM_QUERY": query,
            "OPENDREAM_SUMMARY": summary,
            "OPENDREAM_REF": f"activation-capture:{target}",
            "OPENDREAM_TAGS": (
                "diagnostic:activation-capture,"
                f"key:activation-capture-{target}"
            ),
            "OPENCLAW_TASK": query,
            "OPENCLAW_SUMMARY": summary,
            "OPENCLAW_REF": f"activation-capture:{target}",
        }
    )
    return env


def _current_opendream_bin() -> str:
    argv0 = Path(sys.argv[0])
    if argv0.exists() and os.access(argv0, os.X_OK) and argv0.suffix != ".py":
        return str(argv0)
    return shutil.which("opendream") or "opendream"


def _run_command(args: list[str], *, workspace: Path, env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=workspace,
        env={**env, "OPENDREAM_WORKSPACE": str(workspace)},
        capture_output=True,
        text=True,
        check=False,
        timeout=CAPTURE_TIMEOUT_SECONDS,
    )
    return {
        "args": _redact_args(args, workspace),
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _target_result(
    target: str,
    manifest: dict[str, Any],
    inspection: dict[str, Any],
    *,
    instruction_only: bool,
    status: str,
    pre_context_ok: bool,
    post_capture_ok: bool,
    event_delta: int,
    durable_record_delta: int,
    warnings: list[str],
    next_action: str,
    pre_result: dict[str, Any] | None = None,
    post_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "target_kind": target,
        "title": str(manifest.get("title", target)),
        "activation_mode": str(manifest["activation_mode"]),
        "install_profile": str(manifest["install_profile"]),
        "detected": bool(inspection.get("detected")),
        "configured": bool(inspection.get("configured")),
        "surface_health_state": str(inspection.get("health_state", "unknown")),
        "surface_drift_state": str(inspection.get("drift_state", "unknown")),
        "instruction_only": instruction_only,
        "host_invocation": "instruction-only" if instruction_only else "verified",
        "status": status,
        "pre_context_ok": pre_context_ok,
        "post_capture_ok": post_capture_ok,
        "event_delta": event_delta,
        "durable_record_delta": durable_record_delta,
        "warnings": sorted(dict.fromkeys(warnings)),
        "next_action": next_action,
    }
    if pre_result is not None:
        result["pre_task"] = pre_result
    if post_result is not None:
        result["post_task"] = post_result
    return result


def _context_file(workspace: Path, target: str) -> Path:
    name = "claude" if target == "claude-code" else target
    if target == "openclaw":
        name = "openclaw"
    return workspace / ".opendream" / "context" / f"{name}-pre-task.json"


def _event_ids(store: MemoryStore) -> set[str]:
    return {str(event["event_id"]) for event in store.load_events() if event.get("event_id")}


def _command_warning(phase: str, result: dict[str, Any]) -> str:
    detail = result.get("stderr_tail") or result.get("stdout_tail") or "no command output"
    return f"{phase} command failed with exit {result['returncode']}: {detail}"


def _redact_args(args: list[str], workspace: Path) -> list[str]:
    prefix = str(workspace)
    return [arg.replace(prefix, "$WORKSPACE") for arg in args]


def _tail(text: str, *, limit: int = 1200) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


def _write_capture_report(store: MemoryStore, payload: dict[str, Any]) -> dict[str, Any]:
    report_id = stable_id(
        "activation-capture",
        payload["workspace"],
        payload["generated_at"],
        payload["status"],
        ",".join(payload.get("selected_targets", [])),
    )
    report_path = store.workspace / REPORTS_DIR / f"activation-capture-{report_id}.json"
    write_json(report_path, payload)
    latest_path = store.workspace / ACTIVATION_CAPTURE_LATEST_PATH
    write_json(latest_path, payload)
    payload["report_path"] = str(report_path.relative_to(store.workspace))
    payload["latest_report_path"] = str(latest_path.relative_to(store.workspace))
    write_json(report_path, payload)
    write_json(latest_path, payload)
    return payload
