from zomoto_ai.phase0.domain.models import Budget, Restaurant, UserPreference
from zomoto_ai.phase3.retrieval import filter_candidates, reduce_candidates, retrieve_with_relaxation


def _restaurants():
    return [
        Restaurant(
            id="1",
            name="A Italian",
            city="Delhi",
            cuisines=["Italian"],
            cost_for_two=1200,
            rating=4.2,
            votes=200,
        ),
        Restaurant(
            id="2",
            name="B Chinese",
            city="Delhi",
            cuisines=["Chinese"],
            cost_for_two=700,
            rating=4.0,
            votes=500,
        ),
        Restaurant(
            id="3",
            name="C Pizza",
            city="Delhi",
            cuisines=["Italian", "Pizza"],
            cost_for_two=400,
            rating=3.0,
            votes=5,
        ),
        Restaurant(
            id="4",
            name="D Italian Far",
            city="Bangalore",
            cuisines=["Italian"],
            cost_for_two=800,
            rating=4.8,
            votes=50,
        ),
    ]


def test_filter_by_location_and_cuisine_exact() -> None:
    pref = UserPreference(location="Delhi", cuisine="Italian", min_rating=0)
    got = filter_candidates(_restaurants(), pref, cuisine_mode="exact")
    assert {r.id for r in got} == {"1", "3"}


def test_filter_by_budget_range() -> None:
    pref = UserPreference(
        location="Delhi",
        cuisine=None,
        min_rating=0,
        budget=Budget(kind="range", min_cost_for_two=600, max_cost_for_two=900),
    )
    got = filter_candidates(_restaurants(), pref, cuisine_mode="any")
    assert {r.id for r in got} == {"2"}


def test_retrieve_relaxes_constraints_when_no_match() -> None:
    pref = UserPreference(location="Delhi", cuisine="Mexican", min_rating=4.5)
    res = retrieve_with_relaxation(_restaurants(), pref, top_n=10)
    # Should eventually drop cuisine and/or lower rating to get something in Delhi
    assert res.candidate_set.candidates
    assert any(s.action.startswith("relax_cuisine") for s in res.relax_steps)


def test_reduce_candidates_is_deterministic_and_limits() -> None:
    # create many candidates in same city/cuisine; reducer should still return exactly top_n
    many = [
        Restaurant(id=str(i), name=f"R{i}", city="Delhi", cuisines=["Italian"], rating=4.0, votes=i)
        for i in range(30)
    ]
    reduced = reduce_candidates(many, top_n=10)
    assert len(reduced) == 10
    # should be stable sorted by score (votes tie-breaker influences)
    assert reduced[0].id == "29"

