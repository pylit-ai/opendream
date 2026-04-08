# 04-dashboard-ui.md

## Goal
Provide one central location in the UI for all known workspaces.

## Route
- `/workspaces`

## Dashboard sections
1. summary bar
   - total workspaces
   - activated
   - with service installed
   - stale/missing
2. search/filter controls
   - by path/name
   - by status kind
   - by service installed
   - by semantic mode enabled
3. workspace cards/table
   - name
   - path
   - last seen
   - activation status
   - service status
   - memory root
   - semantic state
   - quick actions:
     - open workspace
     - rescan
     - doctor
     - forget

## Rendering model
Use the machine-local catalog for fast initial render.
Probe expensive status lazily or on refresh.
