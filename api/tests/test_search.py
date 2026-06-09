from app.services.search import build_boolean_fulltext_query


def test_build_boolean_fulltext_query_prefixes_tokens() -> None:
    assert build_boolean_fulltext_query("bach suite") == "+bach* +suite*"


def test_build_boolean_fulltext_query_preserves_quoted_phrases() -> None:
    assert build_boolean_fulltext_query('"exact phrase" bach') == '"exact phrase" +bach*'


def test_build_boolean_fulltext_query_empty() -> None:
    assert build_boolean_fulltext_query("   ") == ""
