# unsupported-path-policy/spec.md

## Requirements

### Requirement: unsupported Gemini OAuth reuse is never recommended
OpenDream MUST treat Gemini OAuth reuse into third-party runtime logic as unsupported.

#### Scenario: Gemini detected
- **WHEN** setup sees Gemini tooling
- **THEN** it does not recommend Gemini OAuth reuse and explains why

### Requirement: negative recommendations are visible
Unsupported paths MUST appear as blocked/unsupported, not silently disappear.

#### Scenario: inspect setup report
- **WHEN** unsupported strategies are present
- **THEN** they appear in the blocked-strategies section with reasons
