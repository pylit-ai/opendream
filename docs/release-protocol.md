# Release Protocol

This protocol describes evidence required before a release candidate is
advertised. Account-specific notes, credentials, and internal service details
must stay out of the repository.

## Change Preparation

- Work on a branch named for the ticket or milestone, such as
  `release/provenance-cleanup` or `feature/memory-showcase`.
- Keep release changes limited to code, tests, docs, CI, release metadata, and
  reviewed assets.
- Do not commit secrets, local machine paths, account-specific details,
  internal URLs, or generated runtime state.

## Local Gates

```bash
make setup
make verify
scripts/check_release_hygiene.sh --strict-local
python scripts/release_check.py --timeout-seconds 300
python -m json.tool .tmp/release-check/release_manifest.json >/dev/null
```

Before tagging, confirm no release, PyPI publish, Product Hunt post, or
visibility change has happened from the preparation branch.

## Release Notes

Release notes should include:

- release branch and commit SHA
- dirty-state check
- release hygiene, package, provenance, vendor, and artifact scans
- test and eval status
- built artifact hashes
- unresolved risks and waivers
- post-publish rollback/yank plan
- visibility guard output
- benchmark fixture scope and any dry-run cost guard for provider-backed checks

Keep account-specific verification, unpublished service URLs, and issue-tracker
writeback outside release artifacts.
