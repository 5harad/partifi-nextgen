from app.services.imslp import (
    normalize_imslp_id,
    parse_imslp_page_html,
    parse_reverse_lookup_location,
)


def test_normalize_imslp_id_numeric() -> None:
    assert normalize_imslp_id("12345") == "12345"
    assert normalize_imslp_id("#67890") == "67890"


def test_normalize_imslp_id_from_link() -> None:
    assert normalize_imslp_id("https://imslp.org/wiki/File:Example.pdf#IMSLP123") == "123"


def test_parse_reverse_lookup_location() -> None:
    parsed = parse_reverse_lookup_location("//imslp.org/wiki/File:Example.pdf#IMSLP456")
    assert parsed is not None
    assert parsed[0] == "https://imslp.org/wiki/File:Example.pdf"
    assert parsed[1] == "456"


def test_parse_imslp_page_html_extracts_metadata() -> None:
    html = """
    <html><head><title>Suite No.1 (Bach, Johann Sebastian)</title></head><body>
    >#12345<
    Publisher Info.:</dt><dd><p class="we_edition_entry">Breitkopf, 1920</p>
    Copyright:</dt><dd><p class="we_edition_entry">Public Domain</p>
    <a href="/wiki/IMSLP:File_formats" title="IMSLP:File formats">PDF</a>
    </body></html>
    """
    data = parse_imslp_page_html(html, "12345")
    assert data["title"] == "Suite No.1"
    assert data["composer"] == "Johann Sebastian Bach"
    assert "Breitkopf" in data["publisher"]
    assert data["file_type"] == "PDF"
