from app.services.search import build_boolean_fulltext_query


def test_build_boolean_fulltext_query_prefixes_tokens() -> None:
    assert build_boolean_fulltext_query("bach suite") == "+bach* +suite*"


def test_build_boolean_fulltext_query_strips_double_quotes_as_punctuation() -> None:
    assert build_boolean_fulltext_query('"exact phrase" bach') == "+exact* +phrase* +bach*"


def test_build_boolean_fulltext_query_empty() -> None:
    assert build_boolean_fulltext_query("   ") == ""


def test_build_boolean_fulltext_query_strips_punctuation_and_apostrophes() -> None:
    assert (
        build_boolean_fulltext_query("fairest Lord Jesus (my soul's glory)")
        == "+fairest* +Lord* +Jesus* +my* +soul* +glory*"
    )


def test_build_boolean_fulltext_query_quoted_apostrophe_same_as_unquoted() -> None:
    assert (
        build_boolean_fulltext_query('"my soul\'s glory" bach')
        == "+my* +soul* +glory* +bach*"
    )


def test_build_boolean_fulltext_query_apostrophe_split_drops_short_parts() -> None:
    assert build_boolean_fulltext_query("O'Brien") == "+Brien*"
    assert build_boolean_fulltext_query("souls choir") == "+souls* +choir*"


def test_build_boolean_fulltext_query_strips_boolean_operators_from_input() -> None:
    assert build_boolean_fulltext_query("-bach +suite") == "+bach* +suite*"


def test_build_boolean_fulltext_query_punctuation_only_returns_empty() -> None:
    assert build_boolean_fulltext_query("()'\"!!!") == ""
