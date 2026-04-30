#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
opendream hook claude-pre-task --workspace "$WORKSPACE" --memory-dir .opendream/memory --fallback-query "$QUERY"
