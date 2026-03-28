#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
MESSAGE_REF="${OPENDREAM_REF:-codex-post-task}"

echo "[opendream] emit-event/maintain $WORKSPACE" >&2
opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF"
opendream maintain --workspace "$WORKSPACE"
