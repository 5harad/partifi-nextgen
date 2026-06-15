from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config

from config import get_settings
from s3_retry import call_with_s3_retries


def score_pdf_s3_key(score_id: str) -> str:
    return f"scores/{score_id}_score.pdf"


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
    client = get_s3_client()

    def _download() -> None:
        client.download_file(settings.s3_bucket, key, str(dest))

    call_with_s3_retries(f"download {key}", _download)


def upload_file(local_path: Path, key: str, content_type: str = "application/octet-stream") -> None:
    settings = get_settings()
    client = get_s3_client()

    def _upload() -> None:
        client.upload_file(
            str(local_path),
            settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    call_with_s3_retries(f"upload {key}", _upload)


def upload_directory(local_dir: Path, prefix: str) -> None:
    for path in local_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(local_dir).as_posix()
            content_type = "image/png" if path.suffix == ".png" else "application/octet-stream"
            upload_file(path, f"{prefix}/{rel}", content_type)


