# Service model

## Supported modes
- default user service
- optional explicit system service

## Supported supervisors
- launchd on macOS
- systemd on Linux

## Runtime mode
- managed backend for portable install, start, stop, and restart verification
- native backend for best-effort launchd or systemd activation when operators opt in
