from pipeline.imslp_ids import normalize_imslp_id


def test_normalize_plain_digits() -> None:
    assert normalize_imslp_id("282358") == "282358"
    assert normalize_imslp_id("#67890") == "67890"


def test_normalize_imagefromindex_url() -> None:
    assert (
        normalize_imslp_id("https://imslp.org/wiki/Special:ImagefromIndex/282358/neo")
        == "282358"
    )


def test_normalize_reverse_lookup_url() -> None:
    assert (
        normalize_imslp_id("https://imslp.org/wiki/Special:ReverseLookup/413014")
        == "413014"
    )


def test_normalize_file_fragment() -> None:
    assert (
        normalize_imslp_id("https://imslp.org/wiki/File:Example.pdf#IMSLP123")
        == "123"
    )


def test_normalize_bare_slug_suffix() -> None:
    assert normalize_imslp_id("282358/neo") == "282358"


def test_normalize_wiki_title_is_none() -> None:
    assert (
        normalize_imslp_id(
            "https://imslp.org/wiki/Bach,_BWV_227_(Bach,_Johann_Sebastian)"
        )
        is None
    )
