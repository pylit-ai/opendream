# Security Policy

## Reporting
Report security issues privately through GitHub Security Advisories when
available, or to the repository owner or maintainer channel before opening a
issue.

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
- hidden network calls, analytics, tracking, or telemetry in default runtime paths

OpenDream sends no telemetry by default. Provider/API-key execution paths are
explicit operator setup paths and should not be described as analytics.
Local-first defaults mean memory, eval fixtures, and observe UI state stay in
the selected workspace unless an operator explicitly configures provider-backed
paths.

## Supported versions

Security fixes are targeted at the latest published package and the current
`main` branch. Older alpha releases may receive a patch only when the maintainer
judges the fix low-risk and relevant to active users.

## Response expectations
- acknowledge receipt within 5 business days
- provide a triage outcome or clarifying questions as quickly as practical
- coordinate disclosure timing with the reporter when a fix is required
