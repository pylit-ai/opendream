# 09-security-and-policy.md

## Goal
Encode the policy boundary directly into the product.

## Rules
- never recommend unsupported third-party OAuth piggybacking
- never recommend Gemini OAuth reuse from OpenDream
- never expose `auth.json` contents in logs or reports
- Codex account-backed mode is only for trusted local/private infra
- Claude/Cursor account-backed modes are delegated runtimes, not token-sharing modes
- direct-provider mode remains the recommended path for public CI/CD and generic automation

## Setup-wizard negative cases
If Gemini is detected, setup must say:
- Gemini CLI OAuth reuse into OpenDream is unsupported
- use direct-provider mode or deterministic-only
- or use a supported vendor-owned execution path if one is later implemented
