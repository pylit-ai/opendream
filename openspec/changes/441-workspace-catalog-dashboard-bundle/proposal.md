# 441-workspace-catalog-dashboard-bundle

## Why

OpenDream is currently activation-first and workspace-scoped. Durable memory, activation metadata, targets, queue state, and service artifacts all live under the individual workspace, which is the right local-first default. But once an operator uses OpenDream across many repos, there is no single first-party place to answer basic questions such as:

- which workspaces on this machine are initialized for OpenDream?
- which ones are activated right now?
- which ones have services installed?
- which ones are stale, broken, or missing?
- which one should I open next?

Today the answer is “search your filesystem for `.opendream/` directories,” which is technically correct and ergonomically primitive.

That gap matters because the product’s North Star explicitly aims to be the default local-first memory substrate **across multiple repos and runtimes**, while the Constitution prioritizes operator control, local-first inspectability, explicit state transitions, and diagnosable behavior. A central workspace catalog and dashboard can strengthen all of those goals if — and only if — it is implemented as a **machine-local, derived convenience index**, not as a hidden new source of truth.

## Goal

Add a first-party workspace catalog and dashboard so operators have one central place to view, search, inspect, and open all known OpenDream workspaces on the current machine.

## What Changes

- add a machine-local workspace catalog that tracks known workspaces and explicit scan roots
- keep per-workspace `.opendream/` state canonical; the global catalog is derived and repairable
- add first-party CLI commands for:
  - listing workspaces
  - scanning configured roots
  - adding/removing roots
  - forgetting stale entries
  - inspecting per-workspace status in aggregate
- add a dashboard route in the UI that lists all known workspaces and links into each workspace view
- show activation, service, memory, semantic, and queue health summaries in one place
- add explicit privacy/safety rules so OpenDream never silently scans arbitrary disks or uploads workspace metadata
- update docs so the setup is obvious and the dashboard is discoverable

## Non-goals

- cloud sync of workspace catalog
- multi-user shared registry
- turning the global catalog into canonical truth
- whole-home recursive scanning by default
- hidden background scans without user-configured roots
- modifying repository product code as part of workspace discovery

## Success criteria

- operators can run `opendream workspace list` and see all known workspaces on the current machine
- operators can opt into scan roots and refresh the catalog explicitly
- the UI has a central workspace dashboard route
- the dashboard reflects activation/service/memory health without making the global catalog canonical
- docs explain both the current local-per-workspace state model and the new machine-local catalog model clearly
- the feature strengthens operator control and local-first ergonomics without violating the Constitution
