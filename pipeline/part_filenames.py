"""Stable, filesystem-safe filenames for generated part PDFs."""

from __future__ import annotations

import hashlib
import re

from anyascii import anyascii

MAX_COMBINED_PARTS = 10
# Leave room for "{partset_id}_a4_" prefix on temp/cache paths (NAME_MAX = 255).
MAX_PART_FILENAME_LEN = 200
MAX_CANONICAL_STEM_LEN = 80
CANONICAL_HASH_LEN = 12


def combined_part_tags(tag: str) -> list[str]:
    return [part.strip() for part in tag.split(" + ") if part.strip()]


def validate_combined_tag(tag: str, *, max_parts: int = MAX_COMBINED_PARTS) -> None:
    names = combined_part_tags(tag)
    if len(names) < 2:
        raise ValueError("Combined part must include at least two parts")
    if len(names) > max_parts:
        raise ValueError(f"Cannot combine more than {max_parts} parts")


def _hashed_filename(tag: str, prefix: str) -> str:
    digest = hashlib.sha256(tag.encode()).hexdigest()[:8]
    return f"{prefix}-{digest}.pdf"


def canonical_part_filename(partset_id: str, tag: str) -> str:
    """Return the stable filename minted when a partset's PDFs are generated."""
    stem = re.sub(r"[^a-z0-9]+", "-", anyascii(tag).lower()).strip("-")
    stem = stem[:MAX_CANONICAL_STEM_LEN].rstrip("-") or "part"
    identity = f"{partset_id}\0{tag}".encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()[:CANONICAL_HASH_LEN]
    return f"{stem}-{digest}.pdf"


def combined_tag_to_filename(tag: str) -> str:
    """Short hashed name for combined parts; display tag stays in the parts row."""
    return _hashed_filename(tag, "combined")


def part_tag_to_filename(tag: str) -> str:
    """Short hashed name for a single part when the tag-derived name is too long."""
    return _hashed_filename(tag, "part")


def resolve_part_filename(file_name: str, tag: str, *, combined: bool = False) -> str:
    """Use stored file_name unless it is too long for the filesystem."""
    if file_name and len(file_name) <= MAX_PART_FILENAME_LEN:
        return file_name
    if combined:
        return combined_tag_to_filename(tag)
    return part_tag_to_filename(tag)
