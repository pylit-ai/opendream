# Spec: Worker Health and Doctor

- worker heartbeat MUST persist under the memory root
- status MUST surface install state, running state, health, heartbeat age, backlog, and last success
- doctor MUST return actionable remediation
