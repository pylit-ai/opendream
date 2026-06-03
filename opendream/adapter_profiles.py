from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import activation_primitives as P
from .storage import MemoryStore

CLAUDE_PRE_TASK_COMMAND = (
    'env OPENDREAM_WORKSPACE="$CLAUDE_PROJECT_DIR" '
    'sh "$CLAUDE_PROJECT_DIR"/.opendream/hooks/claude-pre-task.sh'
)
CLAUDE_POST_TASK_COMMAND = (
    'env OPENDREAM_WORKSPACE="$CLAUDE_PROJECT_DIR" '
    'sh "$CLAUDE_PROJECT_DIR"/.opendream/hooks/claude-post-task.sh'
)


def _req_install(manifest: dict[str, Any], *keys: str) -> dict[str, Any]:
    inst = manifest.get("install")
    if not isinstance(inst, dict):
        raise ValueError(f"adapter {manifest.get('id')!r} requires install object")
    for k in keys:
        if k not in inst or not isinstance(inst[k], str) or not inst[k].strip():
            raise ValueError(f"adapter {manifest.get('id')!r} install.{k} must be a non-empty string")
    return inst


def detect_from_manifest(workspace: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    det = manifest["detection"]

    def run(rule: dict[str, Any]) -> bool:
        paths = rule.get("any_path_exists", [])
        return any((workspace / Path(p)).exists() for p in paths)

    return run(det["detected"]), run(det["configured"])


def install_adapter(store: MemoryStore, manifest: dict[str, Any]) -> dict[str, Any]:
    profile = manifest["install_profile"]
    if profile == "claude_code_hooks":
        return _install_claude_code_hooks(store, manifest["id"])
    if profile == "codex_bundle":
        return _install_codex_bundle(store, manifest["id"])
    if profile == "openclaw_hooks":
        return _install_openclaw_hooks(store, manifest["id"])
    if profile == "shell_hooks_mdc_block":
        return _install_shell_hooks_mdc(store, manifest)
    if profile == "shell_hooks_markdown_block":
        return _install_shell_hooks_markdown(store, manifest)
    raise ValueError(f"unsupported install_profile: {profile}")


def remove_adapter(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    profile = manifest["install_profile"]
    if profile == "claude_code_hooks":
        return _remove_claude_code_hooks(workspace, manifest["id"])
    if profile == "codex_bundle":
        return _remove_codex_bundle(workspace, manifest["id"])
    if profile == "openclaw_hooks":
        return _remove_openclaw_hooks(workspace, manifest["id"])
    if profile == "shell_hooks_mdc_block":
        return _remove_shell_hooks_mdc(workspace, manifest)
    if profile == "shell_hooks_markdown_block":
        return _remove_shell_hooks_markdown(workspace, manifest)
    raise ValueError(f"unsupported install_profile: {profile}")


def expected_surfaces(store: MemoryStore, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    aid = manifest["id"]
    profile = manifest["install_profile"]
    if profile == "claude_code_hooks":
        pre_hook = {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": CLAUDE_PRE_TASK_COMMAND,
                        }
                    ]
                }
            ]
        }
        post_hook = {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": CLAUDE_POST_TASK_COMMAND,
                        }
                    ]
                }
            ]
        }
        return [
            P.file_surface(aid, P.HOOKS_DIR / "claude-pre-task.sh", "hook-script", P.pre_task_script(store, "claude")),
            P.file_surface(
                aid, P.HOOKS_DIR / "claude-post-task.sh", "hook-script", P.post_task_script(store, "claude")
            ),
            P.json_surface(
                aid,
                P.CLAUDE_SETTINGS_PATH,
                "native-hooks",
                {"hooks": {**pre_hook, **post_hook}},
            ),
        ]
    if profile == "codex_bundle":
        return [
            P.file_surface(aid, P.HOOKS_DIR / "codex-pre-task.sh", "hook-script", P.pre_task_script(store, "codex")),
            P.file_surface(aid, P.HOOKS_DIR / "codex-post-task.sh", "hook-script", P.post_task_script(store, "codex")),
            P.file_surface(aid, P.BIN_DIR / "codex-task-wrapper.sh", "managed-wrapper", P.codex_wrapper_script(store)),
            P.block_surface(
                aid,
                P.CODEX_AGENTS_PATH,
                "repo-instructions",
                P.codex_block(store),
                "codex",
            ),
        ]
    if profile == "openclaw_hooks":
        pre_cmd = 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
        post_cmd = 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
        return [
            P.file_surface(aid, P.HOOKS_DIR / "openclaw-hooks.sh", "hook-script", P.openclaw_hook_script(store)),
            P.file_surface(aid, P.OPENCLAW_EVENT_MAP_PATH, "event-map", P.openclaw_event_map()),
            P.json_surface(
                aid,
                P.OPENCLAW_CONFIG_PATH,
                "native-hooks",
                {"hooks": {"prePlan": [pre_cmd], "postTask": [post_cmd]}},
            ),
        ]
    if profile == "shell_hooks_mdc_block":
        inst = _req_install(manifest, "hook_tag", "mdc_relative_path", "block_id", "markdown_kind")
        tag = inst["hook_tag"]
        block_id = inst["block_id"]
        mdc_path = Path(inst["mdc_relative_path"])
        return [
            P.file_surface(aid, P.HOOKS_DIR / f"{tag}-pre-task.sh", "hook-script", P.pre_task_script(store, tag)),
            P.file_surface(aid, P.HOOKS_DIR / f"{tag}-post-task.sh", "hook-script", P.post_task_script(store, tag)),
            P.block_surface(
                aid,
                mdc_path,
                inst["markdown_kind"],
                P.shell_hook_instruction_block(block_id, store),
                block_id,
            ),
        ]
    if profile == "shell_hooks_markdown_block":
        inst = _req_install(
            manifest,
            "hook_tag",
            "markdown_relative_path",
            "block_id",
            "markdown_kind",
            "initial_content_prefix",
        )
        tag = inst["hook_tag"]
        block_id = inst["block_id"]
        md_path = Path(inst["markdown_relative_path"])
        return [
            P.file_surface(aid, P.HOOKS_DIR / f"{tag}-pre-task.sh", "hook-script", P.pre_task_script(store, tag)),
            P.file_surface(aid, P.HOOKS_DIR / f"{tag}-post-task.sh", "hook-script", P.post_task_script(store, tag)),
            P.block_surface(
                aid,
                md_path,
                inst["markdown_kind"],
                P.shell_hook_instruction_block(block_id, store),
                block_id,
            ),
        ]
    raise ValueError(f"unsupported install_profile: {profile}")


def _install_claude_code_hooks(store: MemoryStore, aid: str) -> dict[str, Any]:
    del aid
    workspace = store.workspace
    pre_path = workspace / P.HOOKS_DIR / "claude-pre-task.sh"
    post_path = workspace / P.HOOKS_DIR / "claude-post-task.sh"
    changed_files = P.write_managed_script(pre_path, P.pre_task_script(store, "claude"))
    changed_files.extend(P.write_managed_script(post_path, P.post_task_script(store, "claude")))

    settings_path = workspace / P.CLAUDE_SETTINGS_PATH
    payload = P.load_json_object(settings_path)
    hooks = payload.setdefault("hooks", {})

    # New event-based schema
    pre_command = CLAUDE_PRE_TASK_COMMAND
    post_command = CLAUDE_POST_TASK_COMMAND

    # Clean up old deprecated keys
    hooks.pop("preTask", None)
    hooks.pop("postTask", None)

    # Ensure UserPromptSubmit event exists and has the pre-task hook
    user_prompt_submit = hooks.setdefault("UserPromptSubmit", [])
    if not user_prompt_submit:
        user_prompt_submit.append({
            "hooks": [
                {"type": "command", "command": pre_command}
            ]
        })
    else:
        # Merge with existing matchers if any
        found = False
        for matcher in user_prompt_submit:
            if isinstance(matcher, dict) and "hooks" in matcher:
                hooks_list = matcher["hooks"]
                if not any(h.get("command") == pre_command for h in hooks_list if isinstance(h, dict)):
                    hooks_list.append({"type": "command", "command": pre_command})
                found = True
                break
        if not found:
            user_prompt_submit.append({
                "hooks": [
                    {"type": "command", "command": pre_command}
                ]
            })

    # Ensure Stop event exists and has the post-task hook
    stop = hooks.setdefault("Stop", [])
    if not stop:
        stop.append({
            "hooks": [
                {"type": "command", "command": post_command}
            ]
        })
    else:
        # Merge with existing matchers if any
        found = False
        for matcher in stop:
            if isinstance(matcher, dict) and "hooks" in matcher:
                hooks_list = matcher["hooks"]
                if not any(h.get("command") == post_command for h in hooks_list if isinstance(h, dict)):
                    hooks_list.append({"type": "command", "command": post_command})
                found = True
                break
        if not found:
            stop.append({
                "hooks": [
                    {"type": "command", "command": post_command}
                ]
            })

    changed_files.extend(P.write_if_changed(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"))
    return {"changed_files": changed_files, "warnings": []}


def _remove_claude_code_hooks(workspace: Path, aid: str) -> dict[str, Any]:
    del aid
    settings_path = workspace / P.CLAUDE_SETTINGS_PATH
    payload = P.load_json_object(settings_path)
    hooks = payload.setdefault("hooks", {})

    pre_command = CLAUDE_PRE_TASK_COMMAND
    post_command = CLAUDE_POST_TASK_COMMAND

    # Remove from UserPromptSubmit event
    if "UserPromptSubmit" in hooks:
        user_prompt_submit = hooks["UserPromptSubmit"]
        for matcher in user_prompt_submit:
            if isinstance(matcher, dict) and "hooks" in matcher:
                matcher["hooks"] = [
                    h for h in matcher["hooks"]
                    if not (isinstance(h, dict) and h.get("command") == pre_command)
                ]

    # Remove from Stop event
    if "Stop" in hooks:
        stop = hooks["Stop"]
        for matcher in stop:
            if isinstance(matcher, dict) and "hooks" in matcher:
                matcher["hooks"] = [
                    h for h in matcher["hooks"]
                    if not (isinstance(h, dict) and h.get("command") == post_command)
                ]

    changed_files = (
        P.write_if_changed(settings_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if settings_path.exists()
        else []
    )
    for path in [workspace / P.HOOKS_DIR / "claude-pre-task.sh", workspace / P.HOOKS_DIR / "claude-post-task.sh"]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _install_codex_bundle(store: MemoryStore, aid: str) -> dict[str, Any]:
    del aid
    workspace = store.workspace
    pre_path = workspace / P.HOOKS_DIR / "codex-pre-task.sh"
    post_path = workspace / P.HOOKS_DIR / "codex-post-task.sh"
    wrapper_path = workspace / P.BIN_DIR / "codex-task-wrapper.sh"
    changed_files = P.write_managed_script(pre_path, P.pre_task_script(store, "codex"))
    changed_files.extend(P.write_managed_script(post_path, P.post_task_script(store, "codex")))
    changed_files.extend(P.write_managed_script(wrapper_path, P.codex_wrapper_script(store)))
    agents_path = workspace / P.CODEX_AGENTS_PATH
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else "# AGENTS.md\n\n"
    block = P.codex_block(store)
    updated = P.replace_or_append_block(existing, P.block_start("codex"), P.block_end("codex"), block)
    changed_files.extend(P.write_if_changed(agents_path, updated))
    return {"changed_files": changed_files, "warnings": []}


def _remove_codex_bundle(workspace: Path, aid: str) -> dict[str, Any]:
    del aid
    changed_files: list[str] = []
    agents_path = workspace / P.CODEX_AGENTS_PATH
    if agents_path.exists():
        text = agents_path.read_text(encoding="utf-8")
        updated = P.remove_block(text, P.block_start("codex"), P.block_end("codex"))
        updated = P.remove_block(updated, P.LEGACY_CODEX_BLOCK_START, P.LEGACY_CODEX_BLOCK_END)
        changed_files.extend(P.write_if_changed(agents_path, updated))
    for path in [
        workspace / P.HOOKS_DIR / "codex-pre-task.sh",
        workspace / P.HOOKS_DIR / "codex-post-task.sh",
        workspace / P.BIN_DIR / "codex-task-wrapper.sh",
    ]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _install_openclaw_hooks(store: MemoryStore, aid: str) -> dict[str, Any]:
    del aid
    workspace = store.workspace
    hook_path = workspace / P.HOOKS_DIR / "openclaw-hooks.sh"
    map_path = workspace / P.OPENCLAW_EVENT_MAP_PATH
    changed_files = P.write_managed_script(hook_path, P.openclaw_hook_script(store))
    changed_files.extend(P.write_if_changed(map_path, P.openclaw_event_map()))

    config_path = workspace / P.OPENCLAW_CONFIG_PATH
    payload = P.load_json_object(config_path)
    hooks = payload.setdefault("hooks", {})
    pre_plan = hooks.setdefault("prePlan", [])
    post_task = hooks.setdefault("postTask", [])
    pre_cmd = 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
    post_cmd = 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
    if pre_cmd not in pre_plan:
        pre_plan.append(pre_cmd)
    if post_cmd not in post_task:
        post_task.append(post_cmd)
    changed_files.extend(P.write_if_changed(config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"))
    return {"changed_files": changed_files, "warnings": []}


def _remove_openclaw_hooks(workspace: Path, aid: str) -> dict[str, Any]:
    del aid
    config_path = workspace / P.OPENCLAW_CONFIG_PATH
    payload = P.load_json_object(config_path)
    hooks = payload.setdefault("hooks", {})
    hooks["prePlan"] = [
        item
        for item in hooks.get("prePlan", [])
        if item != 'sh .opendream/hooks/openclaw-hooks.sh pre-plan "$OPENCLAW_TASK"'
    ]
    hooks["postTask"] = [
        item
        for item in hooks.get("postTask", [])
        if item != 'sh .opendream/hooks/openclaw-hooks.sh post-task "$OPENCLAW_SUMMARY"'
    ]
    changed_files = (
        P.write_if_changed(config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if config_path.exists()
        else []
    )
    for path in [workspace / P.HOOKS_DIR / "openclaw-hooks.sh", workspace / P.OPENCLAW_EVENT_MAP_PATH]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _install_shell_hooks_mdc(store: MemoryStore, manifest: dict[str, Any]) -> dict[str, Any]:
    inst = _req_install(manifest, "hook_tag", "mdc_relative_path", "block_id", "markdown_kind")
    tag = inst["hook_tag"]
    block_id = inst["block_id"]
    workspace = store.workspace
    pre_path = workspace / P.HOOKS_DIR / f"{tag}-pre-task.sh"
    post_path = workspace / P.HOOKS_DIR / f"{tag}-post-task.sh"
    changed_files = P.write_managed_script(pre_path, P.pre_task_script(store, tag))
    changed_files.extend(P.write_managed_script(post_path, P.post_task_script(store, tag)))
    rule_path = workspace / Path(inst["mdc_relative_path"])
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    existing = rule_path.read_text(encoding="utf-8") if rule_path.exists() else ""
    updated = P.merge_cursor_mdc(existing, store, block_id)
    changed_files.extend(P.write_if_changed(rule_path, updated))
    return {"changed_files": changed_files, "warnings": []}


def _remove_shell_hooks_mdc(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    inst = _req_install(manifest, "hook_tag", "mdc_relative_path", "block_id", "markdown_kind")
    tag = inst["hook_tag"]
    block_id = inst["block_id"]
    changed_files: list[str] = []
    rule_path = workspace / Path(inst["mdc_relative_path"])
    if rule_path.exists():
        text = rule_path.read_text(encoding="utf-8")
        frontmatter, body = P.split_yaml_frontmatter(text)
        updated_body = P.remove_block(body, P.block_start(block_id), P.block_end(block_id)).strip()
        if not updated_body:
            rule_path.unlink()
            changed_files.append(str(rule_path))
        else:
            merged = frontmatter.rstrip() + "\n\n" + updated_body + "\n"
            changed_files.extend(P.write_if_changed(rule_path, merged))
    for path in [workspace / P.HOOKS_DIR / f"{tag}-pre-task.sh", workspace / P.HOOKS_DIR / f"{tag}-post-task.sh"]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}


def _install_shell_hooks_markdown(store: MemoryStore, manifest: dict[str, Any]) -> dict[str, Any]:
    inst = _req_install(
        manifest,
        "hook_tag",
        "markdown_relative_path",
        "block_id",
        "markdown_kind",
        "initial_content_prefix",
    )
    tag = inst["hook_tag"]
    block_id = inst["block_id"]
    workspace = store.workspace
    pre_path = workspace / P.HOOKS_DIR / f"{tag}-pre-task.sh"
    post_path = workspace / P.HOOKS_DIR / f"{tag}-post-task.sh"
    changed_files = P.write_managed_script(pre_path, P.pre_task_script(store, tag))
    changed_files.extend(P.write_managed_script(post_path, P.post_task_script(store, tag)))
    md_path = workspace / Path(inst["markdown_relative_path"])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    existing = md_path.read_text(encoding="utf-8") if md_path.exists() else inst["initial_content_prefix"]
    block = P.shell_hook_instruction_block(block_id, store)
    updated = P.replace_or_append_block(existing, P.block_start(block_id), P.block_end(block_id), block)
    changed_files.extend(P.write_if_changed(md_path, updated))
    return {"changed_files": changed_files, "warnings": []}


def _remove_shell_hooks_markdown(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    inst = _req_install(
        manifest,
        "hook_tag",
        "markdown_relative_path",
        "block_id",
        "markdown_kind",
        "initial_content_prefix",
    )
    tag = inst["hook_tag"]
    block_id = inst["block_id"]
    changed_files: list[str] = []
    md_path = workspace / Path(inst["markdown_relative_path"])
    if md_path.exists():
        text = md_path.read_text(encoding="utf-8")
        updated = P.remove_block(text, P.block_start(block_id), P.block_end(block_id))
        changed_files.extend(P.write_if_changed(md_path, updated))
    for path in [workspace / P.HOOKS_DIR / f"{tag}-pre-task.sh", workspace / P.HOOKS_DIR / f"{tag}-post-task.sh"]:
        if path.exists():
            path.unlink()
            changed_files.append(str(path))
    return {"changed_files": changed_files, "warnings": []}
