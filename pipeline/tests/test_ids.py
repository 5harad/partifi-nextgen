from pipeline.ids import (
    LEGACY_PARTIFI_ID_PATTERN,
    PARTIFI_ID_PATTERN,
    is_partifi_id,
    rand_partifi_id,
)


def test_rand_partifi_id_format() -> None:
    for _ in range(50):
        value = rand_partifi_id()
        assert PARTIFI_ID_PATTERN.match(value)
        assert value[5] == "-"
        assert len(value) == 11


def test_is_partifi_id_accepts_legacy_and_new() -> None:
    assert is_partifi_id("abc12")
    assert is_partifi_id("03mrA")
    assert is_partifi_id("abcde-fghij")
    assert not is_partifi_id("abcde-ghij")  # 4+5
    assert not is_partifi_id("ABCDE-FGHIJ")  # uppercase
    assert not is_partifi_id("")
    assert not is_partifi_id(None)


def test_legacy_pattern_case_sensitive_length() -> None:
    assert LEGACY_PARTIFI_ID_PATTERN.match("abc12")
    assert not LEGACY_PARTIFI_ID_PATTERN.match("abc123")
