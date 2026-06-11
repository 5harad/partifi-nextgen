"""Run queue jobs in isolated subprocesses with a wall-clock timeout."""

from __future__ import annotations

import logging
import multiprocessing as mp
import time
from typing import Any

import db_conn
from config import get_settings
from jobs.errors import mark_partset_error
from jobs.registry import run_job

logger = logging.getLogger("partifi.worker")

_shutdown_requested = False
_active_proc: mp.Process | None = None


def request_job_abort() -> None:
    """Stop the in-flight job subprocess (called on worker shutdown)."""
    global _shutdown_requested
    _shutdown_requested = True
    proc = _active_proc
    if proc and proc.is_alive():
        proc.terminate()


def _partset_has_error(partset_id: str) -> bool:
    row = db_conn.fetchone(
        "SELECT error FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    return bool(row and row.error)


def _terminate_proc(proc: mp.Process) -> None:
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(10)
    if proc.is_alive():
        proc.kill()
        proc.join()


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
    global _active_proc, _shutdown_requested

    job_type = job.get("type", "unknown")
    payload = dict(job.get("payload", {}))
    if job.get("id"):
        payload["job_id"] = job["id"]
    partset_id = payload.get("partset_id")
    timeout = get_settings().job_timeout_seconds

    _shutdown_requested = False

    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=_child_entry,
        args=(job_type, payload),
        name=f"partifi-job-{job.get('id', '?')}-{job_type}",
    )
    _active_proc = proc
    proc.start()

    deadline = time.monotonic() + timeout
    try:
        while proc.is_alive():
            if _shutdown_requested:
                logger.warning(
                    "Job %s aborted during shutdown (type=%s partset=%s)",
                    job.get("id"),
                    job_type,
                    partset_id,
                )
                _terminate_proc(proc)
                if partset_id:
                    mark_partset_error(partset_id)
                return

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            proc.join(timeout=min(1.0, remaining))
    finally:
        _active_proc = None

    if proc.is_alive():
        logger.error(
            "Job %s timed out after %ss (type=%s partset=%s)",
            job.get("id"),
            timeout,
            job_type,
            partset_id,
        )
        _terminate_proc(proc)
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
