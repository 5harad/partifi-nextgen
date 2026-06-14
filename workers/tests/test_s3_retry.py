from botocore.exceptions import ClientError

from s3_retry import is_retryable_s3_error


def test_retryable_client_error_codes() -> None:
    exc = ClientError({"Error": {"Code": "SlowDown"}, "ResponseMetadata": {"HTTPStatusCode": 503}}, "PutObject")
    assert is_retryable_s3_error(exc)


def test_non_retryable_client_error() -> None:
    exc = ClientError({"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
    assert not is_retryable_s3_error(exc)
