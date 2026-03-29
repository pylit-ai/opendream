# 434-zero-touch-activation-and-command-surface-compression

## Why
OpenDream now exposes too much of its implementation topology to normal users. The common path should not require understanding daemon versus worker, autowire versus activation, or where reference scripts live.

## Goal
Compress the normal user contract to init plus activation, one status view, one repair command, and one deactivate command.

## What Changes
- promote init, activate, status, repair, and deactivate as the primary UX
- keep advanced commands available but secondary
- add compressed status and deactivation behavior
- update docs and release gates to the compressed contract

## Success criteria
- supported configured targets work without manual `.meta/` copying
- status answers the common operator questions in one place
- deactivation cleanly removes managed surfaces
