#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
MESSAGE_REF="${OPENDREAM_REF:-claude-post-task}"
opendream hook claude-post-task --workspace "$WORKSPACE" --memory-dir .opendream/memory --fallback-summary "$SUMMARY" --message-ref "$MESSAGE_REF"
