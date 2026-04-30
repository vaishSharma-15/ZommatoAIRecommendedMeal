from zomoto_ai.phase2.web_ui import _split_optional_constraints


def test_split_optional_constraints() -> None:
    assert _split_optional_constraints("") == []
    assert _split_optional_constraints("  family-friendly , outdoor seating ") == [
        "family-friendly",
        "outdoor seating",
    ]

