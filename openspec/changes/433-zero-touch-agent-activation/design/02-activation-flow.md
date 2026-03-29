# Activation flow

## Standard path
`opendream init --workspace "$PWD" --activate-configured`

## Explicit path
`opendream activate --workspace "$PWD" --targets configured`

## Repair path
`opendream activate --workspace "$PWD" --repair`

Activation detects targets, renders managed surfaces, installs them, runs target-specific verification, and persists a report plus registry state.
