from datetime import datetime

from app.models import Partset
from app.services.partsets import import_progress_payload
from pipeline.imslp_ids import UNIMPORTABLE_IMSLP_MESSAGE


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


def test_import_progress_payload_surfaces_unimportable_imslp_without_db_error() -> None:
    wiki_url = (
        "http://imslp.org/wiki/Sinfonietta,_Op.75_(Lorenzo,_Leonardo_de)"
    )
    partset = Partset(
        id="0ltPh",
        private_id="xTEFL",
        title="Test",
        composer="Composer",
        copyright="PD",
        create_ts=datetime.utcnow(),
        imslp_id=wiki_url,
        error=None,
        status="import",
        import_progress=0.0,
    )
    payload = import_progress_payload(partset)
    assert payload["error"] == "import"
    assert payload["error_message"] == UNIMPORTABLE_IMSLP_MESSAGE
    assert payload["is_complete"] is False
