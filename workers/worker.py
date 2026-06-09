"""Background worker — pulls jobs from Redis and dispatches to handlers."""

from __future__ import annotations

import json
import logging
import signal
import sys

import redis

from config import get_settings
from jobs.gen_parts import run_gen_parts
from jobs.import_pipeline import run_import_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("partifi.worker")

QUEUE_KEY = "partifi:jobs"
RUNNING = True

JOB_HANDLERS = {
    "import_pipeline": lambda payload: run_import_pipeline(
        payload["partset_id"], payload["score_id"]
    ),
    "gen_parts": lambda payload: run_gen_parts(payload["partset_id"]),
}


def _handle_signal(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False
    logger.info("Shutdown requested")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def process_job(job: dict) -> None:
    job_type = job.get("type", "unknown")
    payload = job.get("payload", {})
    logger.info("Processing job %s type=%s", job.get("id"), job_type)

    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        logger.error("Unknown job type: %s", job_type)
        return

    handler(payload)


def main() -> None:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Worker started (redis=%s)", settings.redis_url)

    while RUNNING:
        result = client.brpop(QUEUE_KEY, timeout=5)
        if result is None:
            continue
        _, raw = result
        try:
            job = json.loads(raw)
            process_job(job)
        except json.JSONDecodeError:
            logger.exception("Invalid job payload: %s", raw)
        except Exception:
            logger.exception("Job failed")

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
    sys.exit(0)
