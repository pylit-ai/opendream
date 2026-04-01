# 11-rollout-and-migration.md

## Rollout strategy
1. add schemas and storage for learned context
2. add semantic provider registry and dreamer
3. add verifier / promotion
4. add retrieval fusion
5. add semantic automation jobs
6. add benchmark suite and release gates
7. add meta-harness bootstrap / optimizer surfaces
8. update docs and package outputs
9. run release matrix

## Migration expectations
- current deterministic users should continue to work
- if provider config exists, status surfaces should recommend hybrid mode
- docs must explain when fallback occurred
- benchmark and release evidence must always state active mode

## Release positioning
Ship as:
- OpenDream with semantic sleep-time mode
- deterministic mode remains for offline / cost-constrained use
- hybrid mode is the recommended production path once configured

## Completion rule
When this bundle is complete, no further semantic-mode engineering should be required before release.
Only routine post-release iteration is allowed.
