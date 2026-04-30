from zomoto_ai.phase1.build_index import _parse_int, _parse_rating, _split_cuisines


def test_parse_int_handles_commas_and_currency() -> None:
    assert _parse_int("₹1,200 for two") == 1200
    assert _parse_int("unknown") is None


def test_parse_rating_handles_fraction() -> None:
    assert _parse_rating("3.8/5") == 3.8
    assert _parse_rating("NEW") is None


def test_split_cuisines() -> None:
    assert _split_cuisines("North Indian,Chinese") == ["North Indian", "Chinese"]

