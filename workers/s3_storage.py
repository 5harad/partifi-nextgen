from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config

from config import get_settings


@lru_cache
def get_s3_client():
    settings = get_settings()
    kwargs: dict = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key or None,
        "aws_secret_access_key": settings.s3_secret_key or None,
        "config": Config(signature_version="s3v4"),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
        kwargs["use_ssl"] = settings.s3_use_ssl
    return boto3.client(**kwargs)


def download_file(key: str, dest: Path) -> None:
    settings = get_settings()
    dest.parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(settings.s3_bucket, key, str(dest))


def upload_file(local_path: Path, key: str, content_type: str = "application/octet-stream") -> None:
    settings = get_settings()
    get_s3_client().upload_file(
        str(local_path),
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def upload_directory(local_dir: Path, prefix: str) -> None:
    for path in local_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(local_dir).as_posix()
            content_type = "image/png" if path.suffix == ".png" else "application/octet-stream"
            upload_file(path, f"{prefix}/{rel}", content_type)
