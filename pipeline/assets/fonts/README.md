# PDF header fonts (optional local fallback)

Workers normally use Debian packages `fonts-noto-core` (Latin/Cyrillic/etc.) and
`fonts-wqy-zenhei` (CJK). ReportLab cannot load Debian's Noto CJK `.ttc` files.

For local dev without those packages, you may place:

- `NotoSans-Regular.ttf`
- `wqy-zenhei.ttc` or a TrueType `NotoSansCJK-Regular.ttf`

in this directory. They are not committed to git (large binaries).
