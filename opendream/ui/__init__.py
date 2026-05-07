from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalUIContract:
    runtime: str = "public"
    static_assets: str = "packaged"
    service_routes: str = "optional"


LOCAL_UI_CONTRACT = LocalUIContract()


__all__ = ["LOCAL_UI_CONTRACT", "LocalUIContract"]
