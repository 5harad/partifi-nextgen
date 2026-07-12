from functools import lru_cache
from pathlib import Path

from config import get_settings
from pipeline.local_cache import LocalCache
from s3_storage import download_file


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
    from score_page_cache import build_score_page_cache

    build_score_page_cache(score_id)
    return sorted(lowres_dir.glob("page-*.png"))


def ensure_partset_lowres_files(partset_id: str) -> list[Path]:
    cache = get_local_cache()
    lowres_dir = cache.partset_kind_dir(partset_id, "lowres")
    return sorted(lowres_dir.glob("page-*.png"))
