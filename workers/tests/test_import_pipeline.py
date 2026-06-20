from pathlib import Path
from unittest.mock import MagicMock, patch

from jobs import import_pipeline


def test_run_convert_uses_ensure_valid_score_pdf() -> None:
    workdir = Path("/tmp/partifi/test/import-job1")
    with (
        patch.object(import_pipeline, "download_file"),
        patch.object(import_pipeline, "ensure_valid_score_pdf") as ensure,
        patch.object(import_pipeline, "convert_score"),
        patch.object(import_pipeline, "get_local_cache") as cache,
        patch.object(import_pipeline, "glob") as glob_mock,
        patch.object(import_pipeline.db_conn, "execute"),
    ):
        glob_mock.glob.return_value = [str(workdir / "pages" / "lowres" / "1.png")]
        cache.return_value.copy_pages_tree = MagicMock()
        import_pipeline._run_convert("part01", "abc12", workdir)

    ensure.assert_called_once()
