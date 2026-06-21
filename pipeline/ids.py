"""Partifi id generation (public/private partset ids and score ids)."""

from __future__ import annotations

import re
import secrets
import string

_SEGMENT_LEN = 5
_ALPHABET = string.ascii_lowercase

# New ids: five lowercase letters, hyphen, five lowercase letters.
PARTIFI_ID_PATTERN = re.compile(rf"^[a-z]{{{_SEGMENT_LEN}}}-[a-z]{{{_SEGMENT_LEN}}}$")
# Legacy ids from before the xxxxx-xxxxx format.
LEGACY_PARTIFI_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{5}$")


def rand_partifi_id() -> str:
    """Return a new xxxxx-xxxxx id using a cryptographically strong RNG."""
    left = "".join(secrets.choice(_ALPHABET) for _ in range(_SEGMENT_LEN))
    right = "".join(secrets.choice(_ALPHABET) for _ in range(_SEGMENT_LEN))
    return f"{left}-{right}"


def is_partifi_id(value: str | None) -> bool:
    """True for legacy 5-char ids or new xxxxx-xxxxx ids."""
    if not value:
        return False
    return bool(PARTIFI_ID_PATTERN.match(value) or LEGACY_PARTIFI_ID_PATTERN.match(value))
