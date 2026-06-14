"""Reliable Redis job queue: processing list + stale-job reaper (no auto re-run)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis

from config import get_settings
from jobs.errors import mark_partset_error

logger = logging.getLogger("partifi.worker")

QUEUE_KEY = "partifi:jobs"
PROCESSING_KEY = "partifi:jobs:processing"

# Grace after job timeout before reaper marks a processing job as lost.
REAPER_GRACE_SECONDS = 120


def _partset_id_from_job(job: dict[str, Any]) -> str | None:
    payload = job.get("payload") or {}
    partset_id = payload.get("partset_id")
    return str(partset_id) if partset_id else None


def _job_started_at(job: dict[str, Any]) -> float | None:
    started = job.get("started_at")
    if started is not None:
        return float(started)
    enqueued = job.get("enqueued_at")
    if enqueued is not None:
        return float(enqueued)
    return None


def _is_stale(job: dict[str, Any], *, stale_after_seconds: float) -> bool:
    started = _job_started_at(job)
    if started is None:
        return True
    return (time.time() - started) > stale_after_seconds


def claim_next_job(client: redis.Redis, *, timeout: int = 5) -> str | None:
    """Atomically move the next job to the processing list and stamp started_at."""
    raw = client.brpoplpush(QUEUE_KEY, PROCESSING_KEY, timeout=timeout)
    if raw is None:
        return None
    job = json.loads(raw)
    job["started_at"] = int(time.time())
    updated = json.dumps(job, separators=(",", ":"))
    pipe = client.pipeline()
    pipe.lrem(PROCESSING_KEY, 1, raw)
    pipe.rpush(PROCESSING_KEY, updated)
    pipe.execute()
    return updated


def ack_job(client: redis.Redis, raw: str) -> None:
    client.lrem(PROCESSING_KEY, 1, raw)


def requeue_job(client: redis.Redis, raw: str) -> None:
    """Return an interrupted job to the main queue (deploy shutdown)."""
    job = json.loads(raw)
    job.pop("started_at", None)
    ack_job(client, raw)
    client.lpush(QUEUE_KEY, json.dumps(job, separators=(",", ":")))


def _fail_stale_job(client: redis.Redis, raw: str, job: dict[str, Any]) -> None:
    job_id = job.get("id")
    partset_id = _partset_id_from_job(job)
    logger.error(
        "Stale job %s type=%s partset=%s removed from processing (worker likely crashed)",
        job_id,
        job.get("type"),
        partset_id,
    )
    if partset_id:
        mark_partset_error(
            partset_id,
            message="Job lost in processing queue (worker likely crashed)",
            job_id=job_id,
        )
    ack_job(client, raw)


def reap_stale_jobs(client: redis.Redis) -> int:
    """Mark stale processing jobs as failed; does not re-enqueue."""
    settings = get_settings()
    stale_after = settings.job_timeout_seconds + REAPER_GRACE_SECONDS
    reaped = 0
    for raw in client.lrange(PROCESSING_KEY, 0, -1):
        try:
            job = json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("Invalid job in processing list: %s", raw)
            ack_job(client, raw)
            reaped += 1
            continue
        if _is_stale(job, stale_after_seconds=stale_after):
            _fail_stale_job(client, raw, job)
            reaped += 1
    if reaped:
        logger.warning("Reaped %d stale job(s) from processing list", reaped)
    return reaped
