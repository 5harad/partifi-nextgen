from sqlalchemy import create_engine, text

from config import get_settings

_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True)


def execute(query: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def fetchone(query: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(query), params or {}).fetchone()


def fetchall(query: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(query), params or {}).fetchall()
