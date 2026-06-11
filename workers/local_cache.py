from functools import lru_cache
from pathlib import Path

from config import get_settings
from pipeline.local_cache import LocalCache
from s3_storage import download_file, download_prefix


def _download(key: str, dest: Path) -> None:
    download_file(key, dest)


@lru_cache
def get_local_cache() -> LocalCache:
    settings = get_settings()
    cache = LocalCache(Path(settings.partifi_cache_root), download=_download)
    cache.ensure_root()
    return cache


def ensure_lowres_files(score_id: str) -> list[Path]:
    cache = get_local_cache()
    lowres_dir = cache.score_kind_dir(score_id, "lowres")
    existing = sorted(lowres_dir.glob("page-*.png"))
    if existing:
        return existing
    lowres_dir.mkdir(parents=True, exist_ok=True)
    download_prefix(f"scores/{score_id}/lowres/", lowres_dir)
    return sorted(lowres_dir.glob("page-*.png"))
