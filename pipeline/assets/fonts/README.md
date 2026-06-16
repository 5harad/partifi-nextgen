# PDF header fonts (optional local fallback)

Workers normally use Debian packages `fonts-dejavu-core` (sans headers: Cyrillic,
extended Latin, ♭♮♯), `fonts-wqy-zenhei` (CJK), and optionally `fonts-noto-core`.
ReportLab cannot load Debian's Noto CJK `.ttc` files. Noto Sans lacks ♭.

For local dev without those packages, you may place:

- `DejaVuSans.ttf` (preferred sans fallback)
- `wqy-zenhei.ttc` or a TrueType `NotoSansCJK-Regular.ttf`

in this directory. They are not committed to git (large binaries).
