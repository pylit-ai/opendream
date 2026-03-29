# Repair and doctor

`doctor --surface agents` reports:
- detected targets
- configured targets
- activated targets
- drifted surfaces
- missing required service state
- smoke-check failures

`activate --repair` re-renders missing or drifted managed surfaces and emits a machine-readable repair report.
