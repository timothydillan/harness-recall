from __future__ import annotations

from harness_recall.parsers.base import BaseParser

_REGISTRY: dict[str, BaseParser] = {}


def register_parser(parser: BaseParser) -> None:
    _REGISTRY[parser.name] = parser


def get_parser(name: str) -> BaseParser:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown parser: {name}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def get_all_parsers() -> dict[str, BaseParser]:
    return dict(_REGISTRY)


def _auto_register() -> None:
    """Import parser modules to trigger registration."""
    try:
        from harness_recall.parsers import codex  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.parsers import claude_code  # noqa: F401
    except ImportError:
        pass


_auto_register()
