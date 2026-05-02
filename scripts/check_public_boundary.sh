#!/usr/bin/env bash
set -euo pipefail

blocked='^(AGENTS\.md|CLAUDE\.md|GEMINI\.md|CLAUDE\.local\.md|GEMINI\.local\.md|metactl\.yaml|metactl\.lock\.json|\.metactl/|\.codex/|\.claude/|\.cursor/|\.gemini/|\.omc/|\.opendream/|Modelfile\.)'

if git ls-files | grep -E "$blocked" >/dev/null; then
  echo "Public repo tracks private overlay / local agent artifacts:"
  git ls-files | grep -E "$blocked"
  exit 1
fi

echo "Public boundary OK"
