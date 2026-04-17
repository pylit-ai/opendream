#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
SUMMARY="${1:-${OPENDREAM_SUMMARY:-Task completed.}}"
MESSAGE_REF="${OPENDREAM_REF:-codex-post-task}"
AGENT_LABEL="${OPENDREAM_AGENT_LABEL:-${CODEX_INTERNAL_ORIGINATOR_OVERRIDE:-Codex}}"
AGENT_MODEL_ID="${OPENDREAM_AGENT_MODEL_ID:-${OPENAI_MODEL:-${MODEL:-unknown}}}"
AGENT_MODEL_VERSION="${OPENDREAM_AGENT_MODEL_VERSION:-${OPENAI_MODEL_VERSION:-${MODEL_VERSION:-unknown}}}"

echo "[opendream] emit-event/maintain/dream-worker $WORKSPACE" >&2
opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "$SUMMARY" --message-ref "$MESSAGE_REF" \
  --agent-id "${OPENDREAM_AGENT_ID:-codex}" \
  --agent-label "$AGENT_LABEL" \
  --agent-runtime "${OPENDREAM_AGENT_RUNTIME:-codex-cli}" \
  --agent-adapter-id "${OPENDREAM_AGENT_ADAPTER_ID:-codex-account}" \
  --agent-model-id "$AGENT_MODEL_ID" \
  --agent-model-version "$AGENT_MODEL_VERSION"
opendream maintain --workspace "$WORKSPACE"
opendream dream worker --workspace "$WORKSPACE" --once
