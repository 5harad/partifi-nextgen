import pytest
from pipeline.part_filenames import (
    MAX_COMBINED_PARTS,
    combined_tag_to_filename,
    part_tag_to_filename,
    resolve_part_filename,
    validate_combined_tag,
)


def test_combined_tag_to_filename_is_short_and_stable() -> None:
    tag = "1 + 2 + 3 + 4 + 5"
    first = combined_tag_to_filename(tag)
    second = combined_tag_to_filename(tag)
    assert first == second
    assert first.startswith("combined-")
    assert first.endswith(".pdf")
    assert len(first) < 32


def test_combined_tag_to_filename_differs_by_tag() -> None:
    assert combined_tag_to_filename("A + B") != combined_tag_to_filename("A + C")


def test_validate_combined_tag_rejects_too_many() -> None:
    tag = " + ".join(str(i) for i in range(1, MAX_COMBINED_PARTS + 2))
    with pytest.raises(ValueError, match=str(MAX_COMBINED_PARTS)):
        validate_combined_tag(tag)


def test_validate_combined_tag_rejects_single_part() -> None:
    with pytest.raises(ValueError, match="at least two"):
        validate_combined_tag("violin")


def test_resolve_part_filename_uses_combined_hash_for_long_combined_tag() -> None:
    long_name = "x" * 220 + ".pdf"
    resolved = resolve_part_filename(long_name, "1 + 2 + 3", combined=True)
    assert resolved == combined_tag_to_filename("1 + 2 + 3")
    assert resolved.startswith("combined-")


def test_resolve_part_filename_uses_part_hash_for_long_single_tag() -> None:
    long_name = "x" * 220 + ".pdf"
    tag = "Contrabassoon with a very long descriptive name"
    resolved = resolve_part_filename(long_name, tag, combined=False)
    assert resolved == part_tag_to_filename(tag)
    assert resolved.startswith("part-")


def test_resolve_part_filename_uses_part_hash_when_not_combined_even_with_plus() -> None:
    long_name = "x" * 220 + ".pdf"
    tag = "Violin + divisi"
    resolved = resolve_part_filename(long_name, tag, combined=False)
    assert resolved == part_tag_to_filename(tag)
    assert resolved.startswith("part-")


def test_part_tag_to_filename_is_short_and_stable() -> None:
    tag = "Horn in E-flat (Waldhorn, corno, cor)"
    first = part_tag_to_filename(tag)
    second = part_tag_to_filename(tag)
    assert first == second
    assert first.startswith("part-")
    assert len(first) < 32


def test_resolve_part_filename_keeps_short_names() -> None:
    assert resolve_part_filename("violin.pdf", "violin") == "violin.pdf"
