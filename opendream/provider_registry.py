"""Provider/model registry with health checks for semantic mode.

Implements WS3 (T10-T14): provider registry, config loading, structured-output
contracts, CLI inspection, and tests for missing credentials / fallback policy.
"""

from __future__ import annotations

import os
from typing import Any

from .models import ProviderEntry
from .storage import MemoryStore
from .util import to_iso, utc_now

VALID_ROLES = frozenset(
    {"anticipation", "synthesis", "verification", "benchmark_judge", "harness_optimizer"}
)

VALID_TRANSPORTS = frozenset({"anthropic", "openai", "local", "custom"})

VALID_HEALTH_STATUSES = frozenset({"healthy", "degraded", "unavailable"})


def load_providers(store: MemoryStore) -> list[dict[str, Any]]:
    """Load all registered providers."""
    return store.load_provider_registry()


def register_provider(store: MemoryStore, entry: ProviderEntry | dict[str, Any]) -> dict[str, Any]:
    """Register or update a provider entry."""
    payload = entry.to_dict() if isinstance(entry, ProviderEntry) else dict(entry)
    provider_id = str(payload.get("provider_id", ""))
    if not provider_id:
        raise ValueError("provider_id is required")
    transport = str(payload.get("transport", ""))
    if transport and transport not in VALID_TRANSPORTS:
        raise ValueError(f"unsupported transport: {transport}")
    roles = payload.get("roles", [])
    for role in roles:
        if role not in VALID_ROLES:
            raise ValueError(f"unsupported role: {role}")

    providers = store.load_provider_registry()
    existing_idx = next(
        (i for i, p in enumerate(providers) if p.get("provider_id") == provider_id),
        None,
    )
    if existing_idx is not None:
        providers[existing_idx] = payload
    else:
        providers.append(payload)
    store.save_provider_registry(providers)
    return payload


def remove_provider(store: MemoryStore, provider_id: str) -> bool:
    """Remove a provider by id. Returns True if found and removed."""
    providers = store.load_provider_registry()
    filtered = [p for p in providers if p.get("provider_id") != provider_id]
    if len(filtered) == len(providers):
        return False
    store.save_provider_registry(filtered)
    return True


def check_provider_health(provider: dict[str, Any]) -> dict[str, Any]:
    """Check health of a provider. Returns health status and details.

    For real deployments, this would make an API call. For now, it checks
    that the provider has the minimum required configuration.
    """
    provider_id = str(provider.get("provider_id", "unknown"))
    transport = str(provider.get("transport", ""))
    model_id = str(provider.get("model_id", ""))
    issues: list[str] = []

    if not transport:
        issues.append("no transport configured")
    if not model_id:
        issues.append("no model_id configured")

    # Check for API key based on transport
    if transport == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            issues.append("ANTHROPIC_API_KEY not set")
    elif transport == "openai" and not os.environ.get("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY not set")

    status = "healthy" if not issues else "unavailable"
    return {
        "provider_id": provider_id,
        "health_status": status,
        "issues": issues,
        "checked_at": to_iso(utc_now()),
    }


def check_all_provider_health(store: MemoryStore) -> dict[str, Any]:
    """Check health of all registered providers and update their status."""
    providers = store.load_provider_registry()
    results: list[dict[str, Any]] = []
    for provider in providers:
        result = check_provider_health(provider)
        provider["health_status"] = result["health_status"]
        provider["last_health_check_at"] = result["checked_at"]
        results.append(result)
    store.save_provider_registry(providers)
    return {
        "checked_at": to_iso(utc_now()),
        "provider_count": len(providers),
        "healthy": sum(1 for r in results if r["health_status"] == "healthy"),
        "degraded": sum(1 for r in results if r["health_status"] == "degraded"),
        "unavailable": sum(1 for r in results if r["health_status"] == "unavailable"),
        "results": results,
    }


def get_provider_for_role(store: MemoryStore, role: str) -> dict[str, Any] | None:
    """Get the best available provider for a given role.

    Prefers healthy providers, then degraded. Returns None if all unavailable.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"unsupported role: {role}")
    providers = store.load_provider_registry()
    candidates = [p for p in providers if role in p.get("roles", [])]
    # Sort by health: healthy first, then degraded, then unavailable
    priority = {"healthy": 0, "degraded": 1, "unavailable": 2}
    candidates.sort(key=lambda p: priority.get(p.get("health_status", "unavailable"), 2))
    return candidates[0] if candidates else None


def semantic_mode_available(store: MemoryStore) -> dict[str, Any]:
    """Check if semantic mode is available (providers configured and healthy)."""
    config = store.load_semantic_config()
    mode = config.get("mode", "deterministic")
    if mode == "deterministic":
        return {
            "available": False,
            "mode": mode,
            "reason": "mode is deterministic",
        }

    providers = store.load_provider_registry()
    if not providers:
        return {
            "available": False,
            "mode": mode,
            "reason": "no providers registered",
        }

    # Check required roles
    required_roles = {"synthesis", "verification"}
    available_roles: set[str] = set()
    for p in providers:
        if p.get("health_status") in ("healthy", "degraded"):
            available_roles.update(p.get("roles", []))

    missing_roles = required_roles - available_roles
    if missing_roles:
        fallback = config.get("fallback_policy", "fallback_to_deterministic")
        return {
            "available": False,
            "mode": mode,
            "reason": f"missing provider roles: {', '.join(sorted(missing_roles))}",
            "fallback_policy": fallback,
        }

    return {
        "available": True,
        "mode": mode,
        "healthy_providers": sum(1 for p in providers if p.get("health_status") == "healthy"),
        "available_roles": sorted(available_roles),
    }


def load_semantic_config(store: MemoryStore) -> dict[str, Any]:
    """Load semantic dream configuration with defaults."""
    return store.load_semantic_config()


def save_semantic_config(store: MemoryStore, config: dict[str, Any]) -> None:
    """Save semantic dream configuration."""
    store.save_semantic_config(config)


def validate_structured_output(output: Any, expected_type: str) -> dict[str, Any]:
    """Validate structured output from a provider.

    Returns validation result with status and any issues.
    """
    issues: list[str] = []

    if output is None:
        issues.append("output is None")
        return {"valid": False, "issues": issues}

    if not isinstance(output, dict):
        issues.append(f"expected dict, got {type(output).__name__}")
        return {"valid": False, "issues": issues}

    if expected_type == "anticipation":
        if "query_families" not in output:
            issues.append("missing query_families field")
        elif not isinstance(output["query_families"], list):
            issues.append("query_families must be a list")

    elif expected_type == "synthesis":
        if "proposals" not in output:
            issues.append("missing proposals field")
        elif not isinstance(output["proposals"], list):
            issues.append("proposals must be a list")

    elif expected_type == "verification":
        if "verdict" not in output:
            issues.append("missing verdict field")
        elif output["verdict"] not in ("approve", "reject", "review_required"):
            issues.append(f"invalid verdict: {output['verdict']}")

    return {"valid": len(issues) == 0, "issues": issues}
