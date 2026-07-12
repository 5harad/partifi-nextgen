from datetime import UTC, datetime
from unittest.mock import patch

from app.models import Partset
from app.services.preview import partgen_progress_payload


def test_partgen_progress_zero_when_parts_not_ready_and_job_finished() -> None:
    now = datetime.now(UTC)
    partset = Partset(
        id="pub1",
        private_id="priv1",
        parts_ready=False,
        status="paste",
        paste_start=now,
        paste_complete=now,
        paste_progress=100.0,
        cut_start=now,
        cut_complete=now,
        cut_progress=100.0,
    )

    payload = partgen_progress_payload(partset)

    assert payload["is_complete"] is False
    assert payload["in_progress"] is False
    assert payload["total_progress"] == 0.0
    assert payload["progress"] == 0.0


def test_partgen_progress_shows_paste_while_running() -> None:
    now = datetime.now(UTC)
    partset = Partset(
        id="pub1",
        private_id="priv1",
        parts_ready=False,
        status="paste",
        paste_start=now,
        paste_complete=None,
        paste_progress=50.0,
        cut_start=now,
        cut_complete=now,
    )

    payload = partgen_progress_payload(partset)

    assert payload["is_complete"] is False
    assert payload["in_progress"] is True
    assert payload["total_progress"] > 0.0


@patch("app.services.preview.gen_parts_lock_held", return_value=True)
def test_partgen_progress_queued_job_shows_in_progress(mock_lock: object) -> None:
    partset = Partset(
        id="pub1",
        private_id="priv1",
        parts_ready=False,
        status="analysis",
    )

    payload = partgen_progress_payload(partset)

    assert payload["is_complete"] is False
    assert payload["in_progress"] is True
    assert payload["total_progress"] == 1.0
