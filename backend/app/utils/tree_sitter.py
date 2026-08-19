"""
Cartographer — Tree-sitter parser helpers.

Loads a Tree-sitter parser for a language, preferring the convenience
``tree_sitter_languages`` package and falling back to the individual
grammar wheels (``tree-sitter-python``, ``tree-sitter-javascript``,
etc.) which are what the Docker image installs.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Any

from tree_sitter import Language, Parser

# language key → (module name, language factory attribute)
_LANGUAGE_MODULES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "jsx": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "go": ("tree_sitter_go", "language"),
    "java": ("tree_sitter_java", "language"),
    "rust": ("tree_sitter_rust", "language"),
}


@lru_cache(maxsize=32)
def get_parser(language: str) -> Any | None:
    """
    Return a cached Tree-sitter ``Parser`` for ``language``.

    Returns ``None`` when no grammar is available (callers fall back to
    line-based parsing).
    """
    # Preferred: the umbrella package.
    try:
        import tree_sitter_languages  # noqa: PLC0415

        return tree_sitter_languages.get_parser(language)
    except Exception:
        pass

    # Fallback: individual grammar wheels.
    entry = _LANGUAGE_MODULES.get(language)
    if entry is None:
        return None
    module_name, factory_attr = entry
    try:
        module = importlib.import_module(module_name)
        language_obj = Language(getattr(module, factory_attr)())
        return Parser(language_obj)
    except Exception:
        return None
