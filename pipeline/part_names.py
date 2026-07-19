"""Display-only formatting for part names."""

from __future__ import annotations

import unicodedata


def _display_single_part_name(value: str) -> str:
    if not value:
        return value
    first = value[0]
    if unicodedata.category(first) == "Ll" and "LATIN" in unicodedata.name(first, ""):
        return first.upper() + value[1:]
    return value


def display_part_name(value: str) -> str:
    """Capitalize each combined part's initial Latin letter for display only."""
    return " + ".join(_display_single_part_name(part) for part in value.split(" + "))
