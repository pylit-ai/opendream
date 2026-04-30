#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"
OUTPUT="$WORKSPACE/.opendream/context/cursor-pre-task.json"
mkdir -p "$(dirname "$OUTPUT")"
if [ -n "$GLOBAL" ]; then
  opendream prepare-context --workspace "$WORKSPACE" --memory-dir .opendream/memory --query "$QUERY" --output compact-json --include-global --global-workspace "$GLOBAL" > "$OUTPUT"
else
  opendream prepare-context --workspace "$WORKSPACE" --memory-dir .opendream/memory --query "$QUERY" --output compact-json > "$OUTPUT"
fi
cat "$OUTPUT"
