from datetime import datetime

from app.models import Partset
from app.services.partsets import import_progress_payload


def test_import_progress_payload_includes_error_message() -> None:
    partset = Partset(
        id="pub01",
        private_id="priv1",
        title="Test",
        composer="Composer",
        copyright="PD",
        create_ts=datetime.utcnow(),
        error="import",
        error_message="This score PDF is corrupt or incomplete.",
        status="import",
        import_progress=0.0,
    )
    payload = import_progress_payload(partset)
    assert payload["error"] == "import"
    assert payload["error_message"] == "This score PDF is corrupt or incomplete."
    assert payload["is_complete"] is False
