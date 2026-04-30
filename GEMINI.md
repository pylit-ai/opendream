# Repository Builder

[metactl Instruction Index]|target:gemini-cli|policy:brownfield-safe-builder|mode:reference_index
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.
|budget:warn=8192B|max=32768B
|packs:none

<!-- BEGIN OPENDREAM MANAGED BLOCK: gemini -->

## OpenDream

Before substantial work, run:
`sh .opendream/hooks/gemini-pre-task.sh "${OPENDREAM_QUERY:-current task}"`

Before the final response, run:
`sh .opendream/hooks/gemini-post-task.sh "${OPENDREAM_SUMMARY:-Task completed.}"`

<!-- END OPENDREAM MANAGED BLOCK: gemini -->
