"""Display-only formatting for part names."""

from __future__ import annotations

import unicodedata


def display_part_name(value: str) -> str:
    """Capitalize an initial lowercase Latin letter without changing the raw tag."""
    if not value:
        return value
    first = value[0]
    if unicodedata.category(first) == "Ll" and "LATIN" in unicodedata.name(first, ""):
        return first.upper() + value[1:]
    return value
