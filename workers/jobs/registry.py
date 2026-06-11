"""Job type registry — shared by the worker process and job subprocesses."""

from __future__ import annotations

from typing import Any, Callable

from jobs.gen_parts import run_gen_parts
from jobs.imslp_import import run_imslp_import
from jobs.import_pipeline import run_import_pipeline

JobHandler = Callable[[dict[str, Any]], None]

JOB_HANDLERS: dict[str, JobHandler] = {
    "import_pipeline": lambda payload: run_import_pipeline(
        payload["partset_id"], payload["score_id"], job_id=payload.get("job_id")
    ),
    "imslp_import": lambda payload: run_imslp_import(
        payload["partset_id"], payload["imslp_id"], job_id=payload.get("job_id")
    ),
    "gen_parts": lambda payload: run_gen_parts(
        payload["partset_id"], job_id=payload.get("job_id")
    ),
}


def run_job(job_type: str, payload: dict[str, Any]) -> None:
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job_type}")
    handler(payload)
