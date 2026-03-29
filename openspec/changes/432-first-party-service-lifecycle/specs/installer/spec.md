# Spec: First-party Service Installer

- installer MUST render launchd or systemd manifests from internal templates
- installer MUST write a machine-readable install report
- installer MUST keep repeated installs idempotent
- uninstall MUST remove only generated artifacts by default
