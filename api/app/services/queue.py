import json
from functools import lru_cache
from typing import Any

import redis

from app.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


QUEUE_KEY = "partifi:jobs"


def enqueue_job(job_type: str, payload: dict[str, Any]) -> str:
    client = get_redis()
    job_id = client.incr("partifi:job_id")
    job = {"id": str(job_id), "type": job_type, "payload": payload}
    client.lpush(QUEUE_KEY, json.dumps(job))
    return str(job_id)
