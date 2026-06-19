from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret: str = "change-me"
    cors_origins: str = "http://localhost:5173"

    google_client_id: str = ""
    google_client_secret: str = ""
    # GIS popup code exchange: defaults to empty; frontend sends window.location.origin.
    google_oauth_redirect_uri: str = ""

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "partifi"
    mysql_user: str = "partifi"
    mysql_password: str = "partifi_dev_password"

    redis_url: str = "redis://localhost:6379/0"
    job_timeout_seconds: int = 2700

    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_bucket: str = "cdn.partifi.org"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = True

    partifi_cache_root: str = "/data/partifi"
    partifi_cache_max_gb: float = 25.0
    partifi_cache_preview_ttl_days: int = 7
    partifi_cache_parts_ttl_days: int = 7
    partifi_cache_score_ttl_days: int = 7
    partifi_max_score_mb: int = 250

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def validate_settings() -> None:
    settings = get_settings()
    if settings.app_env != "production":
        return
    insecure_secrets = {"change-me", "change-me-to-a-long-random-string"}
    if settings.app_secret in insecure_secrets or len(settings.app_secret) < 16:
        raise RuntimeError(
            "APP_SECRET must be set to a strong random value when APP_ENV=production"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
