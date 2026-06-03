#!/bin/sh
set -eu

WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"
QUERY="${1:-${OPENDREAM_QUERY:-current task}}"
GLOBAL="${OPENDREAM_GLOBAL_WORKSPACE:-}"
AGENT_LABEL="${OPENDREAM_AGENT_LABEL:-${CODEX_INTERNAL_ORIGINATOR_OVERRIDE:-Codex}}"
AGENT_MODEL_ID="${OPENDREAM_AGENT_MODEL_ID:-${OPENAI_MODEL:-${MODEL:-unknown}}}"
AGENT_MODEL_VERSION="${OPENDREAM_AGENT_MODEL_VERSION:-${OPENAI_MODEL_VERSION:-${MODEL_VERSION:-unknown}}}"

echo "[opendream] status/prepare-context $WORKSPACE" >&2
opendream status --workspace "$WORKSPACE"
if [ -n "$GLOBAL" ]; then
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" --output compact-json --include-global --global-workspace "$GLOBAL" \
    --agent-id "${OPENDREAM_AGENT_ID:-codex}" \
    --agent-label "$AGENT_LABEL" \
    --agent-runtime "${OPENDREAM_AGENT_RUNTIME:-codex-cli}" \
    --agent-adapter-id "${OPENDREAM_AGENT_ADAPTER_ID:-codex-account}" \
    --agent-model-id "$AGENT_MODEL_ID" \
    --agent-model-version "$AGENT_MODEL_VERSION"
else
  opendream prepare-context --workspace "$WORKSPACE" --query "$QUERY" --output compact-json \
    --agent-id "${OPENDREAM_AGENT_ID:-codex}" \
    --agent-label "$AGENT_LABEL" \
    --agent-runtime "${OPENDREAM_AGENT_RUNTIME:-codex-cli}" \
    --agent-adapter-id "${OPENDREAM_AGENT_ADAPTER_ID:-codex-account}" \
    --agent-model-id "$AGENT_MODEL_ID" \
    --agent-model-version "$AGENT_MODEL_VERSION"
fi
