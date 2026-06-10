"""Run queue jobs in isolated subprocesses with a wall-clock timeout."""

from __future__ import annotations

import logging
import multiprocessing as mp
from typing import Any

import db_conn
from config import get_settings
from jobs.errors import mark_partset_error
from jobs.registry import run_job

logger = logging.getLogger("partifi.worker")


def _partset_has_error(partset_id: str) -> bool:
    row = db_conn.fetchone(
        "SELECT error FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    return bool(row and row.error)


def _child_entry(job_type: str, payload: dict[str, Any]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_job(job_type, payload)
    except Exception:
        logger.exception("Job failed in subprocess type=%s", job_type)
        partset_id = payload.get("partset_id")
        if partset_id:
            mark_partset_error(partset_id)
        raise SystemExit(1) from None


def run_job_with_timeout(job: dict[str, Any]) -> None:
    job_type = job.get("type", "unknown")
    payload = job.get("payload", {})
    partset_id = payload.get("partset_id")
    timeout = get_settings().job_timeout_seconds

    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_child_entry,
        args=(job_type, payload),
        name=f"partifi-job-{job.get('id', '?')}-{job_type}",
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        logger.error(
            "Job %s timed out after %ss (type=%s partset=%s)",
            job.get("id"),
            timeout,
            job_type,
            partset_id,
        )
        proc.terminate()
        proc.join(10)
        if proc.is_alive():
            proc.kill()
            proc.join()
        if partset_id:
            mark_partset_error(partset_id)
        return

    if proc.exitcode not in (0, None):
        logger.error(
            "Job %s exited with code %s (type=%s partset=%s)",
            job.get("id"),
            proc.exitcode,
            job_type,
            partset_id,
        )
        if partset_id and not _partset_has_error(partset_id):
            mark_partset_error(partset_id)
