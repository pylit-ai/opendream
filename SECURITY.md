# Security Policy

## Reporting
Report security issues privately to the repository owner or maintainer channel before opening a public issue.

Include:
- affected version or commit
- reproduction steps
- impact assessment
- whether secrets, data integrity, or write confinement are involved

## Scope
Security issues include:
- promotion or persistence of sensitive values that should not be stored
- writes escaping the intended `memory/` subtree
- lock bypass or corruption that can damage durable memory state
- packaging or installation behavior that changes trust boundaries unexpectedly

## Response expectations
- acknowledge receipt within 5 business days
- provide a triage outcome or clarifying questions as quickly as practical
- coordinate disclosure timing with the reporter when a fix is required
