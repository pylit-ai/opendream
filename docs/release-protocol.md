# Release Protocol

This public protocol describes evidence required before a release candidate is
advertised. Account-specific notes, credentials, and non-public service details
must stay out of the public repository.

## Change Preparation

- Work on a branch named for the ticket or milestone, such as
  `release/provenance-cleanup` or `feature/memory-showcase`.
- Keep public changes limited to code, tests, docs, CI, release metadata, and
  public-safe assets.
- Do not commit secrets, local machine paths, account-specific details,
  non-public URLs, or generated runtime state.

## Local Gates

```bash
make setup
make verify
scripts/check_public_boundary.sh --strict-local
python scripts/release_check.py --timeout-seconds 300
python -m json.tool .tmp/release-check/release_manifest.json >/dev/null
```

Before tagging, confirm the repository is still private and that no public
release, PyPI publish, Product Hunt post, or visibility change has happened in
the preparation branch.

## Release Notes

Release notes should include:

- public branch and commit SHA
- dirty-state check
- boundary, package, provenance, vendor, and public-artifact scans
- test and eval status
- built artifact hashes
- unresolved risks and waivers
- post-publish rollback/yank plan
- visibility guard output
- benchmark fixture scope and any dry-run cost guard for provider-backed checks

Keep account-specific verification, unpublished service URLs, and issue-tracker
writeback outside public artifacts.
