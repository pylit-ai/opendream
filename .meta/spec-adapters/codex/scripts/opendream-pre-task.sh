#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"

echo "[opendream] status/prepare-context $WORKSPACE" >&2
opendream status --workspace "$WORKSPACE"
if [ -n "$GLOBAL" ]; then
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" --include-global --global-workspace "$GLOBAL"
else
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY"
fi
