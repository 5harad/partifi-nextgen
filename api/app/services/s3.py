from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


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


def presigned_get_url(key: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    client = get_presign_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
