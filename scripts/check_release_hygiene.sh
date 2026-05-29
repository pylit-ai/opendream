#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir/.." rev-parse --show-toplevel 2>/dev/null || (cd "$script_dir/.." && pwd))"
cd "$repo_root"
is_git_checkout=0
if git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  is_git_checkout=1
fi

strict_local=0
for arg in "$@"; do
  case "$arg" in
    --strict-local)
      strict_local=1
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done
if [ "${STRICT_LOCAL:-0}" = "1" ]; then
  strict_local=1
fi

blocked_paths='^(CLAUDE\.md|GEMINI\.md|CODEX\.md|AGENTS\.local\.md|CLAUDE\.local\.md|GEMINI\.local\.md|metactl\.yaml|metactl\.lock\.json|\.claudeignore|\.codexignore|\.cursorignore|\.geminiignore|\.mcp\.json|opencode\.json|\.metactl/|\.agents/|\.codex/|\.codex-goal/|\.claude/|\.cursor/|\.gemini/|(.*/)?\.omc/|(.*/)?\.opendream/|\.ruler/|\.aider/|\.windsurf/|\.superpowers/|docs/superpowers/|(.*/)?memory/|(.*/)?notepads/|(.*/)?scratch/|\.tmp/|tmp/|frontend/node_modules/|node_modules/|\.mypy_cache/|\.pytest_cache|\.ruff_cache/|htmlcov/|\.coverage|skills/|Modelfile\.|.*\.code-workspace$|.*\.zip$)'
allowed_agent_docs='^(AGENTS\.md|opendream/AGENTS\.md|tests/AGENTS\.md|\.meta/spec-adapters/AGENTS\.md)$'
agent_doc_paths='(^|/)(AGENTS|CLAUDE|GEMINI|CODEX)\.md$'

tracked_or_new="$(mktemp)"
existing_paths="$(mktemp)"
blocked_hits="$(mktemp)"
agent_doc_hits="$(mktemp)"
content_hits="$(mktemp)"
content_filtered="$(mktemp)"
tracked_codex_goal="$(mktemp)"
trap 'rm -f "$tracked_or_new" "$existing_paths" "$blocked_hits" "$agent_doc_hits" "$content_hits" "$content_filtered" "$tracked_codex_goal"' EXIT

if [ "$is_git_checkout" = "1" ]; then
  git ls-files --cached -- .codex-goal >"$tracked_codex_goal"
elif [ -e .codex-goal ]; then
  find .codex-goal -print | sed 's#^\./##' >"$tracked_codex_goal"
fi
if [ -s "$tracked_codex_goal" ]; then
  echo "Release tree tracks or stages local launch metadata:"
  cat "$tracked_codex_goal"
  exit 1
fi

if [ "$is_git_checkout" = "1" ]; then
  {
    git ls-files
    git ls-files --others --exclude-standard
    if [ "$strict_local" = "1" ]; then
      git ls-files --others --ignored --exclude-standard | grep -Ev '^(\.mypy_cache/|\.pytest_cache/|\.ruff_cache/|\.tmp/|tmp/|htmlcov/|frontend/node_modules/|node_modules/|\.coverage$)' || true
    fi
  } | grep -Ev '^\.codex-goal(/|$)' | sort -u >"$tracked_or_new"
else
  find . -mindepth 1 -print \
    | sed 's#^\./##' \
    | grep -Ev '^(\.git(/|$)|\.codex-goal(/|$))' \
    | sort -u >"$tracked_or_new"
fi

while IFS= read -r path; do
  [ -e "$path" ] && printf '%s\n' "$path"
done <"$tracked_or_new" >"$existing_paths"

grep -E "$blocked_paths" "$existing_paths" >"$blocked_hits" || true
if [ -s "$blocked_hits" ]; then
  echo "Release tree contains generated or local-only paths:"
  cat "$blocked_hits"
  exit 1
fi

grep -E "$agent_doc_paths" "$existing_paths" | grep -Ev "$allowed_agent_docs" >"$agent_doc_hits" || true
if [ -s "$agent_doc_hits" ]; then
  echo "Release tree contains unexpected agent instruction documents:"
  cat "$agent_doc_hits"
  exit 1
fi

private_repo_marker='opendream-[p]rivate'
agent_archive_marker='archived-[p]ublic-agent-artifacts'
provider_detail_marker='provider-specific ([p]rivate|non-[p]ublic):'
content_markers="/Users/[[:alnum:]_.-]+|/home/[[:alnum:]_.-]+|[A-Za-z]:\\\\Users\\\\|${private_repo_marker}|${agent_archive_marker}|customer/provider-specific|${provider_detail_marker}|internal URL:|internal_url|https?://internal"
while IFS= read -r path; do
  case "$path" in
    scripts/check_release_hygiene.sh|scripts/check_provenance_risk.py|.gitignore|uv.lock|frontend/pnpm-lock.yaml)
      continue
      ;;
    .venv/*)
      continue
      ;;
  esac
  if [ -f "$path" ] && grep -Iq . "$path"; then
    grep -n -E "$content_markers" "$path" | sed "s#^#$path:#" >>"$content_hits" || true
  fi
done <"$existing_paths"

grep -Ev '(/Users/example|/Users/me|/home/example|[A-Za-z]:\\Users\\example)' "$content_hits" >"$content_filtered" || true
if [ -s "$content_filtered" ]; then
  echo "Release tree contains local-only or sensitive content markers:"
  cat "$content_filtered"
  exit 1
fi

echo "Release hygiene OK"
