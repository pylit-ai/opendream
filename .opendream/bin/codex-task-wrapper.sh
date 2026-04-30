#!/bin/sh
set -eu

SUMMARY="${OPENDREAM_SUMMARY:-Codex task completed.}"
QUERY="${OPENDREAM_QUERY:-$SUMMARY}"
if [ "${1:-}" = "--summary" ]; then
  SUMMARY="$2"
  shift 2
fi
if [ "${1:-}" = "--query" ]; then
  QUERY="$2"
  shift 2
fi
if [ "${1:-}" = "--" ]; then
  shift
fi
sh .opendream/hooks/codex-pre-task.sh "$QUERY"
status=0
if [ "$#" -gt 0 ]; then
  "$@" || status=$?
fi
post_status=0
sh .opendream/hooks/codex-post-task.sh "$SUMMARY" || post_status=$?
if [ "$status" -eq 0 ] && [ "$post_status" -ne 0 ]; then
  status="$post_status"
fi
exit "$status"
