from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class DreamBackend(Protocol):
    name: str

    def available(self) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class BackendDescriptor:
    name: str
    module: str
    optional: bool = True


BACKENDS: Mapping[str, BackendDescriptor] = {
    "semantic": BackendDescriptor(name="semantic", module="opendream.semantic_dreamer"),
    "service": BackendDescriptor(name="service", module="opendream.service"),
}


__all__ = ["BACKENDS", "BackendDescriptor", "DreamBackend"]
