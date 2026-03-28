#!/bin/sh
set -eu

MODE="${1:-pre-plan}"
PAYLOAD="${2:-current task}"
WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"

case "$MODE" in
  pre-plan)
    echo "[opendream] status/prepare-context $WORKSPACE" >&2
    opendream status --workspace "$WORKSPACE"
    if [ -n "$GLOBAL" ]; then
      opendream prepare-context --workspace "$WORKSPACE" --query "$PAYLOAD" --include-global --global-workspace "$GLOBAL"
    else
      opendream prepare-context --workspace "$WORKSPACE" --query "$PAYLOAD"
    fi
    ;;
  post-task)
    echo "[opendream] emit-event/maintain $WORKSPACE" >&2
    opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "$PAYLOAD" --message-ref "${OPENCLAW_REF:-openclaw-post-task}"
    if [ -n "$GLOBAL" ]; then
      opendream maintain --workspace "$WORKSPACE" --include-global --global-workspace "$GLOBAL"
    else
      opendream maintain --workspace "$WORKSPACE"
    fi
    ;;
  *)
    echo "usage: $0 {pre-plan|post-task} [text]" >&2
    exit 2
    ;;
esac
