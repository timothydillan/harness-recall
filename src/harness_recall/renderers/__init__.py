from __future__ import annotations

from harness_recall.renderers.base import BaseRenderer

_REGISTRY: dict[str, BaseRenderer] = {}


def register_renderer(renderer: BaseRenderer) -> None:
    _REGISTRY[renderer.name] = renderer


def get_renderer(name: str) -> BaseRenderer:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown renderer: {name}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def _auto_register() -> None:
    try:
        from harness_recall.renderers import markdown  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.renderers import json_renderer  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.renderers import html  # noqa: F401
    except ImportError:
        pass


_auto_register()
