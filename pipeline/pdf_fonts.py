"""ReportLab header fonts for part PDFs (Latin, CJK, and other scripts)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ASSETS_FONTS = Path(__file__).resolve().parent / "assets" / "fonts"

TIMES_ROMAN = "Times-Roman"
PARTIFI_NOTO_CJK = "PartifiNotoCJK"
PARTIFI_NOTO_SANS = "PartifiNotoSans"

# Characters Times-Roman can render (PDF WinAnsi / Latin-1). Extended Latin
# (e.g. Czech ř, č) needs Noto Sans — Times shows missing-glyph boxes for those.
_TIMES_ROMAN_RANGES: tuple[tuple[int, int], ...] = (
    (0x0020, 0x007E),  # printable ASCII
    (0x00A0, 0x00FF),  # Latin-1 supplement (Café, Antonín, etc.)
    (0x2000, 0x206F),  # general punctuation
    (0x2070, 0x209F),  # superscripts/subscripts (e.g. No²)
)

_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3040, 0x30FF),  # hiragana + katakana
    (0x3400, 0x4DBF),  # CJK extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xAC00, 0xD7AF),  # hangul syllables
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFF00, 0xFFEF),  # halfwidth/fullwidth forms
)

NOTO_SANS_CANDIDATES = (
    ASSETS_FONTS / "NotoSans-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/google-noto/NotoSans-Regular.ttf"),
)

# ReportLab only supports TrueType outlines. Debian's Noto CJK .ttc files use
# PostScript outlines and fail to load; wqy-zenhei works for CJK header text.
CJK_FONT_CANDIDATES = (
    ASSETS_FONTS / "NotoSansCJK-Regular.ttf",
    ASSETS_FONTS / "wqy-zenhei.ttc",
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
)

# Backwards-compatible alias for tests.
NOTO_CJK_CANDIDATES = CJK_FONT_CANDIDATES


def _in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def _is_latin_char(ch: str) -> bool:
    if not ch:
        return True
    if ch.isspace():
        return True
    codepoint = ord(ch)
    if codepoint in (0x266D, 0x266E, 0x266F):  # ♭ ♮ ♯
        return True
    return _in_ranges(codepoint, _TIMES_ROMAN_RANGES)


def is_latin_only(text: str) -> bool:
    if not text:
        return True
    return all(_is_latin_char(ch) for ch in text)


def has_cjk(text: str) -> bool:
    return any(_in_ranges(ord(ch), _CJK_RANGES) for ch in text)


def _find_font(candidates: tuple[Path, ...]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _ttfont_kwargs(path: Path) -> dict:
    if path.suffix.lower() == ".ttc":
        return {"subfontIndex": 0}
    return {}


@lru_cache
def _ensure_fonts_registered() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if PARTIFI_NOTO_SANS not in registered:
        sans_path = _find_font(NOTO_SANS_CANDIDATES)
        if sans_path is None:
            raise RuntimeError(
                "Noto Sans not found for PDF headers; install fonts-noto-core "
                "or add NotoSans-Regular.ttf under pipeline/assets/fonts/"
            )
        pdfmetrics.registerFont(TTFont(PARTIFI_NOTO_SANS, str(sans_path)))

    if PARTIFI_NOTO_CJK not in registered:
        cjk_path = _find_font(CJK_FONT_CANDIDATES)
        if cjk_path is None:
            raise RuntimeError(
                "CJK font not found for PDF headers; install fonts-wqy-zenhei "
                "or add a TrueType CJK font under pipeline/assets/fonts/"
            )
        pdfmetrics.registerFont(
            TTFont(PARTIFI_NOTO_CJK, str(cjk_path), **_ttfont_kwargs(cjk_path))
        )


def header_font_name(text: str) -> str:
    if is_latin_only(text):
        return TIMES_ROMAN
    _ensure_fonts_registered()
    if has_cjk(text):
        return PARTIFI_NOTO_CJK
    return PARTIFI_NOTO_SANS


def set_header_font(canvas, text: str, size: int = 11) -> str:
    font = header_font_name(text)
    canvas.setFont(font, size)
    return font
