# verified-writes/spec.md

## Requirements

### Requirement: verify-before-assert for concrete claims
Externally checkable claims MUST be verified or strongly source-backed before promotion to active memory.

#### Scenario: concrete claim lacks verification
- **WHEN** a dream run proposes an exact count/path/framework-status claim without strong evidence
- **THEN** the claim is downgraded, hedged, or quarantined
- **AND** it is not promoted as active truth

### Requirement: provenance tiers
Promoted claims MUST carry provenance tiers.

#### Scenario: inspect a promoted claim
- **WHEN** an operator inspects the claim
- **THEN** the record shows whether it is source-backed, runtime-verified, inferred, or speculative
