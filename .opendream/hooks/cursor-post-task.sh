#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
MESSAGE_REF="${OPENDREAM_REF:-cursor-post-task}"
opendream emit-event --workspace "$WORKSPACE" --memory-dir .opendream/memory --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF"
opendream maintain --workspace "$WORKSPACE" --memory-dir .opendream/memory
opendream dream worker --workspace "$WORKSPACE" --memory-dir .opendream/memory --once
