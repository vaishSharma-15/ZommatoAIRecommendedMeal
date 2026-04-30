from __future__ import annotations

from zomoto_ai.phase0.config import Settings
from zomoto_ai.phase0.domain.models import Budget, CandidateSet, Restaurant, UserPreference
from zomoto_ai.phase0.llm.stub import StubLLMClient


def main() -> None:
    settings = Settings.load_from_env()

    # Phase 0 deliverable: prove contracts wire up end-to-end.
    pref = UserPreference(
        location="Delhi",
        budget=Budget(kind="bucket", bucket="medium"),
        cuisine="Italian",
        min_rating=3.5,
        optional_constraints=["family-friendly"],
    )

    candidates = [
        Restaurant(
            id="demo-1",
            name="Demo Ristorante",
            city="Delhi",
            cuisines=["Italian"],
            cost_for_two=1200,
            rating=4.2,
            votes=250,
        ),
        Restaurant(
            id="demo-2",
            name="Demo Pizza Place",
            city="Delhi",
            cuisines=["Italian"],
            cost_for_two=800,
            rating=4.0,
            votes=120,
        ),
    ]

    candidate_set = CandidateSet(user_preference=pref, candidates=candidates[: settings.top_n])

    llm: StubLLMClient = StubLLMClient()
    result = llm.rank_and_explain(candidate_set)

    print("wiring OK")
    print(
        {
            "dataset_path": settings.dataset_path,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "top_n": settings.top_n,
            "recommendations": [item.model_dump() for item in result.items],
        }
    )


if __name__ == "__main__":
    main()

