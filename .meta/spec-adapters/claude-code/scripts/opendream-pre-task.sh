#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"

echo "[opendream] prepare-context $WORKSPACE" >&2
if [ -n "$GLOBAL" ]; then
  opendream-memory prepare-context --workspace "$WORKSPACE" --query "$QUERY" --include-global --global-workspace "$GLOBAL"
else
  opendream-memory prepare-context --workspace "$WORKSPACE" --query "$QUERY"
fi
