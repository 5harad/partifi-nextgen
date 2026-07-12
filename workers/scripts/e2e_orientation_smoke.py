"""Integration smoke test: pdfinfo probe + real par_pdf2png for portrait and landscape."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

WORKERS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKERS_ROOT.parent
for root in (WORKERS_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from pipeline.orientation_probe import infer_orientation_from_pdf
from pdf2png import par_pdf2png


def make_pdf(path: Path, pagesize) -> None:
    c = canvas.Canvas(str(path), pagesize=pagesize)
    for i in range(2):
        c.drawString(72, 720, f"page {i+1}")
        c.showPage()
    c.save()


def main() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="partifi-e2e-"))
    try:
        cases = [
            ("portrait", letter, (600, 776), (2550, 3300)),
            ("landscape", landscape(letter), (776, 600), (3300, 2550)),
        ]
        for label, pagesize, expected_lowres, expected_highres in cases:
            pdf = tmpdir / f"{label}.pdf"
            out = tmpdir / f"{label}-pages"
            make_pdf(pdf, pagesize)

            inferred = infer_orientation_from_pdf(pdf)
            if inferred != label:
                raise SystemExit(f"probe: expected {label}, got {inferred}")

            returned = par_pdf2png(str(pdf), str(out), None, orientation=inferred)
            if returned != label:
                raise SystemExit(f"convert returned {returned}, expected {label}")

            lowres = out / "lowres" / "page-1.png"
            if not lowres.is_file():
                raise SystemExit(f"missing {lowres}")

            with Image.open(lowres) as im:
                if im.size != expected_lowres:
                    raise SystemExit(f"{label} lowres: {im.size} != {expected_lowres}")

            highres = out / "highres" / "page-1.png"
            with Image.open(highres) as im:
                if im.size != expected_highres:
                    raise SystemExit(f"{label} highres: {im.size} != {expected_highres}")

            print(f"OK {label}: probe={inferred} lowres={expected_lowres} highres={expected_highres}")

        print("E2E convert smoke test passed")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
