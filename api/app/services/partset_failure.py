"""Clear partset failure metadata when retrying or restarting work."""

from __future__ import annotations

from app.models import Partset


def clear_partset_failure(partset: Partset) -> None:
    partset.error = None
    partset.error_message = None
    partset.error_ts = None
    partset.last_job_id = None
