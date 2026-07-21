from unittest.mock import MagicMock, patch

from jobs import gen_parts


def test_fetch_spacings_preserves_zero() -> None:
    rows = [MagicMock(tag="bass", spacing=0), MagicMock(tag="violin", spacing=None)]
    with patch("jobs.gen_parts.fetchall", return_value=rows):
        spacings = gen_parts._fetch_spacings("part01")
    assert spacings["bass"] == 0.0
    assert spacings["violin"] == 0.1


@patch("jobs.gen_parts.finalize_part_generation", return_value=True)
@patch("jobs.gen_parts.create_parts")
@patch("jobs.gen_parts.read_segment_png_heights", return_value=[100.0])
@patch("jobs.gen_parts.apply_combined_parts")
@patch("jobs.gen_parts.fetch_score_orientation", return_value="portrait")
@patch("jobs.gen_parts.build_score_page_cache")
@patch("jobs.gen_parts.get_local_cache")
@patch(
    "jobs.gen_parts._fetch_part_files",
    return_value=[
        {
            "tag": "violin",
            "file_name": "violin.pdf",
            "spacing": 0.1,
            "combined": False,
        }
    ],
)
@patch("jobs.gen_parts._fetch_spacings", return_value={"violin": 0.1})
@patch("jobs.gen_parts._fetch_breaks", return_value={})
@patch("jobs.gen_parts._fetch_combined_tags", return_value=[])
@patch(
    "jobs.gen_parts.build_part_segment_map",
    return_value=({"violin": [0]}, [10.0], [100.0], [""]),
)
@patch("jobs.gen_parts.cut_segment_tasks")
@patch("jobs.gen_parts.fetchone")
@patch("jobs.gen_parts._fetch_segment_rows")
@patch("jobs.gen_parts.execute")
def test_gen_parts_warms_cache_when_highres_missing(
    _execute: MagicMock,
    mock_segments: MagicMock,
    mock_fetchone: MagicMock,
    _cut: MagicMock,
    _map: MagicMock,
    _combined: MagicMock,
    _breaks: MagicMock,
    _spacings: MagicMock,
    _parts: MagicMock,
    mock_cache_fn: MagicMock,
    mock_warm: MagicMock,
    _orientation: MagicMock,
    _apply_combined: MagicMock,
    _heights: MagicMock,
    _create_parts: MagicMock,
    mock_finalize: MagicMock,
    tmp_path,
) -> None:
    mock_segments.return_value = [
        {
            "page": 1,
            "rotation": 0.0,
            "left_margin": 0.0,
            "right_margin": 100.0,
            "top": 0.0,
            "bottom": 10.0,
            "tags": "violin",
            "label": "",
        }
    ]
    mock_fetchone.side_effect = [
        MagicMock(score_id="abc12", title="T", composer="C"),
        MagicMock(rotation_degrees=0, split_two_up=False),
    ]

    cache = MagicMock()
    cache.score_has_kind.return_value = False
    page_path = MagicMock()
    page_path.read_bytes.return_value = b"png"
    cache.ensure_score_page.return_value = page_path
    cache.part_is_cached.return_value = True
    mock_cache_fn.return_value = cache

    workdir = tmp_path / "work"

    gen_parts._run_gen_parts("part01", workdir, job_id="job1")

    mock_warm.assert_called_once_with("abc12", job_id="job1")
    expected_name = gen_parts.canonical_part_filename("part01", "violin")
    mock_finalize.assert_called_once_with(
        "part01",
        snapshot={("violin", False)},
        file_names={"violin": expected_name},
    )
