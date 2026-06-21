# Cache and Generated-State Management

OpenDream keeps durable memory under the configured memory root, usually
`.opendream/memory/`. Some files in that tree are rebuildable read models used
to keep the Observe UI fast.

## Generated cache files

The main generated cache artifacts are:

- `state/observability_compact_index.json` - compact read model for list views.
- `state/observability_index.json` - full read model for detailed observability.
- `state/cache_config.json` - optional local cache policy overrides.

These files are local workspace state. They are ignored by the public repo, are
not package assets, and are safe to delete when you want OpenDream to rebuild
them from the filesystem source of truth.

## Inspect disk usage

```bash
opendream cache info --workspace "$PWD"
```

The JSON output lists each generated artifact, byte size, configured cap, path,
and Git tracking state.

## Verify release safety

```bash
opendream cache verify --workspace "$PWD"
```

This fails when a generated cache file exceeds its configured cap or is tracked
by Git. Maintainers also get this check through:

```bash
python scripts/check_generated_state.py
make verify
make release-check
```

## Configure limits

The full observability index is capped by default. If the generated full index
would exceed the cap, OpenDream still returns the in-memory result and writes
the compact index, but it does not persist the oversized full JSON file.

```bash
opendream cache configure --workspace "$PWD" --max-full-index-bytes 26214400
opendream cache configure --workspace "$PWD" --persist-full-index false
opendream cache configure --workspace "$PWD" --max-compact-index-bytes 5242880
```

Use `0` for a byte cap to disable that specific cap.

## Prune generated cache files

Preview first:

```bash
opendream cache prune --workspace "$PWD" --dry-run --full-index
```

Delete after review:

```bash
opendream cache prune --workspace "$PWD" --yes --full-index
```

Use `--all-generated` only when you want every rebuildable generated cache
artifact removed. The next Observe request recreates the files it needs.
