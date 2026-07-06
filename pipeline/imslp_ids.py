"""Normalize user-facing IMSLP identifiers to numeric edition ids."""

from __future__ import annotations

import re

_IMSLP_FRAGMENT_RX = re.compile(r"IMSLP(\d+)", re.I)
_PATH_PATTERNS = (
    re.compile(r"ImagefromIndex/(\d+)", re.I),
    re.compile(r"ReverseLookup/(\d+)", re.I),
    re.compile(r"IMSLPImageHandler/(\d+)", re.I),
)


def normalize_imslp_id(raw: str) -> str | None:
    """Return a numeric IMSLP edition id, or None when none can be extracted."""
    text = raw.strip()
    if not text:
        return None

    head = text.lstrip("#")
    if head.isdigit():
        return head

    for pattern in _PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)

    match = _IMSLP_FRAGMENT_RX.search(text)
    if match:
        return match.group(1)

    # Bare "282358/neo" from legacy paste.
    first = head.split("/")[0].split("?")[0]
    if first.isdigit():
        return first

    return None
