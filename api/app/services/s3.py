from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings

def score_pdf_s3_key(score_id: str) -> str:
    return f"scores/{score_id}_score.pdf"


def presigned_score_pdf_url(score_id: str, *, download_name: str | None = None) -> str:
    return presigned_get_url(
        score_pdf_s3_key(score_id),
        download_name=download_name or f"{score_id}_score.pdf",
    )


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


def ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    settings = get_settings()
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


@lru_cache
def get_presign_s3_client():
    """Client used only for browser-facing presigned URLs."""
    settings = get_settings()
    endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
    kwargs: dict = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key or None,
        "aws_secret_access_key": settings.s3_secret_key or None,
        "config": Config(signature_version="s3v4"),
    }
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["use_ssl"] = settings.s3_use_ssl
    return boto3.client(**kwargs)


def presigned_get_url(
    key: str,
    expires_in: int = 3600,
    download_name: str | None = None,
) -> str:
    settings = get_settings()
    client = get_presign_s3_client()
    params: dict = {"Bucket": settings.s3_bucket, "Key": key}
    if download_name:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def delete_prefix(prefix: str) -> None:
    settings = get_settings()
    client = get_s3_client()
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
        objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if objects:
            client.delete_objects(
                Bucket=settings.s3_bucket,
                Delete={"Objects": objects},
            )
