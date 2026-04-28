#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"

# Try to read from stdin (Claude Code hook JSON), fall back to args/env
if [ -t 0 ]; then
  # stdin is a terminal (not piped), use argument or env var
  QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
else
  # stdin has data (Claude Code hook), parse JSON with jq
  QUERY="$(jq -r '.prompt // empty' 2>/dev/null || echo "")"
  if [ -z "$QUERY" ]; then
    # jq failed or prompt was empty, fall back to argument/env
    QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
  fi
fi

echo "[opendream] prepare-context $WORKSPACE" >&2
if [ -n "$GLOBAL" ]; then
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" --output compact-json --include-global --global-workspace "$GLOBAL"
else
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" --output compact-json
fi
