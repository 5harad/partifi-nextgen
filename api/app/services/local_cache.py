from functools import lru_cache
import sys
from pathlib import Path

from app.config import get_settings
from app.services.s3 import get_s3_client

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
for root in (APP_ROOT, REPO_ROOT):
    root_str = str(root)
    if root_str not in sys.path and (Path(root) / "pipeline").is_dir():
        sys.path.insert(0, root_str)

from pipeline.local_cache import LocalCache


def _download(key: str, dest: Path) -> None:
    settings = get_settings()
    dest.parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(settings.s3_bucket, key, str(dest))


@lru_cache
def get_local_cache() -> LocalCache:
    settings = get_settings()
    cache = LocalCache(Path(settings.partifi_cache_root), download=_download)
    cache.ensure_root()
    return cache
