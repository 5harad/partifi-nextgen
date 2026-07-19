from pipeline.part_names import display_part_name


def test_display_part_name_capitalizes_initial_lowercase_latin_letter() -> None:
    assert display_part_name("violin") == "Violin"
    assert display_part_name("épinette") == "Épinette"


def test_display_part_name_capitalizes_each_combined_part() -> None:
    assert display_part_name("violin + cello") == "Violin + Cello"
    assert (
        display_part_name("oboe d’amore + bass clarinet")
        == "Oboe d’amore + Bass clarinet"
    )
    assert display_part_name("глас + китара") == "глас + китара"


def test_display_part_name_preserves_other_names() -> None:
    assert display_part_name("Violin II") == "Violin II"
    assert display_part_name("SATB") == "SATB"
    assert display_part_name("3rd flute") == "3rd flute"
    assert display_part_name("глас") == "глас"
    assert display_part_name("声部") == "声部"
