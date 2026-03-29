# Managed fallbacks

Wrappers and generated shell glue are allowed only where the target lacks a sufficient native lifecycle surface.

They must remain generated, inspectable, reversible, exit-code preserving, and idempotent.
