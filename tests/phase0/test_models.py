from zomoto_ai.phase0.domain.models import Budget, CandidateSet, Restaurant, UserPreference


def test_user_preference_min_rating_default() -> None:
    pref = UserPreference(location="Delhi")
    assert pref.min_rating == 0


def test_budget_bucket() -> None:
    b = Budget(kind="bucket", bucket="low")
    assert b.kind == "bucket"
    assert b.bucket == "low"


def test_candidate_set_round_trip() -> None:
    pref = UserPreference(location="Bangalore", cuisine="Italian")
    cs = CandidateSet(
        user_preference=pref,
        candidates=[Restaurant(id="r1", name="A", cuisines=["Italian"])],
    )
    dumped = cs.model_dump()
    assert dumped["user_preference"]["location"] == "Bangalore"
    assert dumped["candidates"][0]["id"] == "r1"

