#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
MESSAGE_REF="${OPENDREAM_REF:-claude-post-task}"

# Try to read from stdin (Claude Code hook JSON), fall back to args/env
if [ -t 0 ]; then
  # stdin is a terminal (not piped), use argument or env var
  SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
else
  # stdin has data (Claude Code hook), parse JSON with jq
  SUMMARY="$(jq -r '.last_assistant_message // empty' 2>/dev/null || echo "")"
  if [ -z "$SUMMARY" ]; then
    # jq failed or message was empty, fall back to argument/env
    SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
  fi
fi

echo "[opendream] emit-event/maintain/dream-worker $WORKSPACE" >&2
opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF"
opendream maintain --workspace "$WORKSPACE"
opendream dream worker --workspace "$WORKSPACE" --once
