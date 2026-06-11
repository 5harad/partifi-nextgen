"""Local read-through cache for score pages, preview cuts, and part PDFs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal

ScoreKind = Literal["lowres", "highres", "thumbs"]
SCORE_KINDS: tuple[ScoreKind, ...] = ("lowres", "highres", "thumbs")


class LocalCache:
    FINGERPRINT_NAME = ".fingerprint"

    def __init__(self, root: Path, download: Callable[[str, Path], None]) -> None:
        self.root = root
        self.download = download

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    # --- scores ---

    def score_root(self, score_id: str) -> Path:
        return self.root / "scores" / score_id

    def score_kind_dir(self, score_id: str, kind: ScoreKind) -> Path:
        return self.score_root(score_id) / kind

    def score_page_path(self, score_id: str, kind: ScoreKind, page: int) -> Path:
        return self.score_kind_dir(score_id, kind) / f"page-{page}.png"

    def score_page_s3_key(self, score_id: str, kind: ScoreKind, page: int) -> str:
        return f"scores/{score_id}/{kind}/page-{page}.png"

    def score_pdf_path(self, score_id: str) -> Path:
        return self.score_root(score_id) / "score.pdf"

    def score_pdf_s3_key(self, score_id: str) -> str:
        return f"scores/{score_id}_score.pdf"

    def ensure_score_pdf(self, score_id: str) -> Path:
        path = self.score_pdf_path(score_id)
        if path.is_file():
            self._touch(path)
            return path

        key = self.score_pdf_s3_key(score_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._temp_path(path)
        try:
            self.download(key, tmp)
            self._install_file(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            if path.is_file():
                self._touch(path)
                return path
            raise
        self._touch(path)
        return path

    def score_has_kind(self, score_id: str, kind: ScoreKind) -> bool:
        directory = self.score_kind_dir(score_id, kind)
        return directory.is_dir() and any(directory.glob("page-*.png"))

    def score_has_pages(self, score_id: str) -> bool:
        return self.score_has_kind(score_id, "lowres")

    def ensure_score_page(self, score_id: str, kind: ScoreKind, page: int) -> Path:
        path = self.score_page_path(score_id, kind, page)
        if path.is_file():
            self._touch(path)
            return path

        key = self.score_page_s3_key(score_id, kind, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._temp_path(path)
        try:
            self.download(key, tmp)
            self._install_file(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            if path.is_file():
                self._touch(path)
                return path
            raise
        self._touch(path)
        return path

    def copy_pages_tree(self, score_id: str, pages_dir: Path) -> None:
        """Copy convert output (lowres/, highres/, thumbs/) into cache."""
        for kind in SCORE_KINDS:
            src = pages_dir / kind
            if not src.is_dir():
                continue
            target = self.score_kind_dir(score_id, kind)
            target.mkdir(parents=True, exist_ok=True)
            for png in src.glob("*.png"):
                dest = target / png.name
                if dest.is_file():
                    continue
                tmp = self._temp_path(dest)
                try:
                    shutil.copy2(png, tmp)
                    self._install_file(tmp, dest)
                except Exception:
                    tmp.unlink(missing_ok=True)
                    if not dest.is_file():
                        raise

    def invalidate_score(self, score_id: str) -> None:
        shutil.rmtree(self.score_root(score_id), ignore_errors=True)

    # --- preview ---

    def preview_dir(self, partset_id: str) -> Path:
        return self.root / "preview" / partset_id

    def preview_segment_path(self, partset_id: str, ndx: int) -> Path:
        return self.preview_dir(partset_id) / f"s{ndx}.png"

    @staticmethod
    def preview_fingerprint(
        segment_rows: list[dict[str, Any]],
        breaks: dict[str, list[int]],
        spacings: dict[str, float],
        combined_part_names: list[str],
    ) -> str:
        payload = {
            "segments": segment_rows,
            "breaks": {tag: sorted(values) for tag, values in sorted(breaks.items())},
            "spacings": {tag: spacings[tag] for tag in sorted(spacings)},
            "combined": sorted(combined_part_names),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def preview_is_valid(self, partset_id: str, fingerprint: str, num_segments: int) -> bool:
        preview_dir = self.preview_dir(partset_id)
        fp_file = preview_dir / self.FINGERPRINT_NAME
        if not fp_file.is_file() or fp_file.read_text().strip() != fingerprint:
            return False
        for ndx in range(num_segments):
            if not self.preview_segment_path(partset_id, ndx).is_file():
                return False
        return True

    def write_preview(self, partset_id: str, fingerprint: str, segments_dir: Path) -> None:
        """Publish preview PNGs in place so readers never see an empty directory."""
        preview_dir = self.preview_dir(partset_id)
        preview_dir.mkdir(parents=True, exist_ok=True)

        expected = {png.name for png in segments_dir.glob("s*.png")}
        for png in sorted(segments_dir.glob("s*.png")):
            dest = preview_dir / png.name
            tmp = self._temp_path(dest)
            try:
                shutil.copy2(png, tmp)
                self._replace_file(tmp, dest)
            except Exception:
                tmp.unlink(missing_ok=True)
                if not dest.is_file():
                    raise

        for existing in preview_dir.glob("s*.png"):
            if existing.name not in expected:
                existing.unlink(missing_ok=True)

        fp = preview_dir / self.FINGERPRINT_NAME
        fp_tmp = self._temp_path(fp)
        fp_tmp.write_text(fingerprint)
        self._replace_file(fp_tmp, fp)

    def invalidate_preview(self, partset_id: str) -> None:
        parent = self.root / "preview"
        shutil.rmtree(self.preview_dir(partset_id), ignore_errors=True)
        if parent.is_dir():
            for path in parent.glob(f"{partset_id}.staging.*"):
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)

    # --- parts ---

    def parts_dir(self, partset_id: str) -> Path:
        return self.root / "parts" / partset_id

    def part_path(self, partset_id: str, filename: str) -> Path:
        return self.parts_dir(partset_id) / filename

    def part_is_cached(self, partset_id: str, filename: str) -> bool:
        return self.part_path(partset_id, filename).is_file()

    def store_part_file(self, partset_id: str, src: Path) -> Path:
        dest = self.part_path(partset_id, src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._temp_path(dest)
        try:
            shutil.copy2(src, tmp)
            self._install_file(tmp, dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            if not dest.is_file():
                raise
        self._touch(dest)
        return dest

    def ensure_part_file(self, partset_id: str, filename: str) -> Path | None:
        path = self.part_path(partset_id, filename)
        if path.is_file():
            self._touch(path)
            return path

        key = f"parts/{partset_id}/{filename}"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._temp_path(path)
        try:
            self.download(key, tmp)
        except Exception:
            tmp.unlink(missing_ok=True)
            if path.is_file():
                self._touch(path)
                return path
            return None

        if not tmp.is_file() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            return path if path.is_file() else None

        self._install_file(tmp, path)
        if not path.is_file():
            return None
        self._touch(path)
        return path

    def invalidate_parts(self, partset_id: str) -> None:
        shutil.rmtree(self.parts_dir(partset_id), ignore_errors=True)

    # --- maintenance ---

    def disk_usage_bytes(self) -> int:
        if not self.root.is_dir():
            return 0
        total = 0
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for name in filenames:
                total += (Path(dirpath) / name).stat().st_size
        return total

    def iter_cache_dirs(self) -> Iterator[tuple[str, Path, float]]:
        """Yield (category, path, mtime) for evictable cache directories."""
        for category, base in (
            ("preview", self.root / "preview"),
            ("parts", self.root / "parts"),
            ("scores", self.root / "scores"),
        ):
            if not base.is_dir():
                continue
            for path in base.iterdir():
                if not path.is_dir():
                    continue
                name = path.name
                if category == "preview" and ".staging." in name:
                    continue
                if name.startswith("."):
                    continue
                yield category, path, path.stat().st_mtime

    @staticmethod
    def clean_stale_scratch(scratch_root: Path, *, max_age_hours: float = 24) -> int:
        """Remove job workdirs older than max_age_hours. Returns count removed."""
        if not scratch_root.is_dir():
            return 0
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for path in scratch_root.iterdir():
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        return removed

    @staticmethod
    def _token() -> str:
        return f"{os.getpid()}.{os.urandom(4).hex()}"

    @classmethod
    def _temp_path(cls, dest: Path) -> Path:
        return dest.with_name(f"{dest.stem}.{cls._token()}{dest.suffix}.part")

    @staticmethod
    def _install_file(tmp: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            tmp.unlink(missing_ok=True)
            LocalCache._touch(dest)
            return
        LocalCache._replace_file(tmp, dest)

    @staticmethod
    def _replace_file(tmp: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)

    @staticmethod
    def _publish_dir(staging: Path, final: Path) -> None:
        final.parent.mkdir(parents=True, exist_ok=True)
        if not staging.is_dir():
            raise FileNotFoundError(staging)

        if final.exists():
            trash = final.with_name(f"{final.name}.trash.{LocalCache._token()}")
            final.rename(trash)
            try:
                staging.rename(final)
            except OSError:
                shutil.rmtree(staging, ignore_errors=True)
                if trash.exists() and not final.exists():
                    trash.rename(final)
                if final.is_dir():
                    shutil.rmtree(trash, ignore_errors=True)
                    return
                raise
            shutil.rmtree(trash, ignore_errors=True)
            return

        try:
            staging.rename(final)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
            if final.is_dir():
                return
            raise

    @staticmethod
    def _touch(path: Path) -> None:
        try:
            os.utime(path, None)
        except OSError:
            pass
