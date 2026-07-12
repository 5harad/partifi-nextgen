"""Run queue jobs in isolated subprocesses with a wall-clock timeout."""

from __future__ import annotations

import enum
import logging
import multiprocessing as mp
import time
from typing import Any

from config import get_settings
from gen_parts_lock import release_gen_parts_lock
from import_lock import release_import_lock
from jobs.errors import mark_partset_error, partset_has_error
from jobs.registry import run_job

logger = logging.getLogger("partifi.worker")

_shutdown_requested = False
_active_proc: mp.Process | None = None


class JobOutcome(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


def request_job_abort() -> None:
    """Stop the in-flight job subprocess (called on worker shutdown)."""
    global _shutdown_requested
    _shutdown_requested = True
    proc = _active_proc
    if proc and proc.is_alive():
        proc.terminate()


def _partset_has_error(partset_id: str) -> bool:
    return partset_has_error(partset_id)


def _release_job_locks(job_type: str, partset_id: str | None) -> None:
    if not partset_id:
        return
    if job_type in ("import_pipeline", "imslp_import", "reorient_partset", "warm_partset_pages"):
        release_import_lock(partset_id)
    elif job_type == "gen_parts":
        release_gen_parts_lock(partset_id)


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
    partset_id = payload.get("partset_id")
    job_id = payload.get("job_id")
    try:
        run_job(job_type, payload)
    except Exception as exc:
        logger.exception("Job failed in subprocess type=%s", job_type)
        if partset_id and not partset_has_error(partset_id):
            mark_partset_error(partset_id, message=str(exc), job_id=job_id)
        raise SystemExit(1) from None


def run_job_with_timeout(job: dict[str, Any]) -> JobOutcome:
    global _active_proc, _shutdown_requested

    job_type = job.get("type", "unknown")
    payload = dict(job.get("payload", {}))
    job_id = job.get("id")
    if job_id:
        payload["job_id"] = job_id
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

    outcome = JobOutcome.SUCCESS
    deadline = time.monotonic() + timeout
    try:
        while proc.is_alive():
            if _shutdown_requested:
                logger.warning(
                    "Job %s interrupted during shutdown (type=%s partset=%s)",
                    job_id,
                    job_type,
                    partset_id,
                )
                _terminate_proc(proc)
                outcome = JobOutcome.INTERRUPTED
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            proc.join(timeout=min(1.0, remaining))
    finally:
        _active_proc = None

    if outcome is JobOutcome.INTERRUPTED:
        _release_job_locks(job_type, partset_id)
        return JobOutcome.INTERRUPTED

    if proc.is_alive():
        logger.error(
            "Job %s timed out after %ss (type=%s partset=%s)",
            job_id,
            timeout,
            job_type,
            partset_id,
        )
        _terminate_proc(proc)
        if partset_id:
            mark_partset_error(
                partset_id,
                message=f"Job timed out after {timeout}s",
                job_id=job_id,
            )
        _release_job_locks(job_type, partset_id)
        return JobOutcome.FAILED

    if proc.exitcode not in (0, None):
        logger.error(
            "Job %s exited with code %s (type=%s partset=%s)",
            job_id,
            proc.exitcode,
            job_type,
            partset_id,
        )
        if partset_id and not _partset_has_error(partset_id):
            mark_partset_error(
                partset_id,
                message=f"Job exited with code {proc.exitcode}",
                job_id=job_id,
            )
        _release_job_locks(job_type, partset_id)
        return JobOutcome.FAILED

    if partset_id and _partset_has_error(partset_id):
        logger.error(
            "Job %s exited 0 but partset %s has error set (type=%s)",
            job_id,
            partset_id,
            job_type,
        )
        _release_job_locks(job_type, partset_id)
        return JobOutcome.FAILED

    return JobOutcome.SUCCESS
