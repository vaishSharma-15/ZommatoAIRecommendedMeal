from zomoto_ai.phase0.domain.models import Restaurant, UserPreference
from zomoto_ai.phase4.parsing import extract_first_json_object
from zomoto_ai.phase4.validation import validate_llm_output


def test_extract_first_json_object_whole_string() -> None:
    obj, err = extract_first_json_object('{"items":[{"restaurant_id":"a","rank":1,"explanation":"ok"}]}')
    assert err == ""
    assert obj and "items" in obj


def test_extract_first_json_object_embedded() -> None:
    raw = "Here you go:\n\n{ \"items\": [] }\nThanks!"
    obj, err = extract_first_json_object(raw)
    assert err == ""
    assert obj == {"items": []}


def test_validate_blocks_hallucinated_id() -> None:
    pref = UserPreference(location="Delhi")
    valid_ids = {"1"}
    obj = {"items": [{"restaurant_id": "999", "rank": 1, "explanation": "nice"}]}
    out = validate_llm_output(obj=obj, user_preference=pref, valid_ids=valid_ids, top_k=5)
    assert not out.ok
    assert "hallucinated" in out.error


def test_validate_accepts_valid_items() -> None:
    pref = UserPreference(location="Delhi")
    valid_ids = {"1", "2"}
    obj = {
        "items": [
            {"restaurant_id": "1", "rank": 1, "explanation": "Matches Delhi."},
            {"restaurant_id": "2", "rank": 2, "explanation": "Also in Delhi."},
        ],
        "summary": "Top picks.",
    }
    out = validate_llm_output(obj=obj, user_preference=pref, valid_ids=valid_ids, top_k=10)
    assert out.ok
    assert out.result is not None
    assert len(out.result.items) == 2

