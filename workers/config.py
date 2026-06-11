from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "partifi"
    mysql_user: str = "partifi"
    mysql_password: str = "partifi_dev_password"

    redis_url: str = "redis://localhost:6379/0"
    worker_concurrency: int = 1
    job_timeout_seconds: int = 2700  # 45 minutes
    partgen_pool_size: int = 0  # 0 = auto (half of CPU cores)

    s3_endpoint_url: str | None = None
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
    partifi_cache_scratch_max_age_hours: float = 24.0

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
