from __future__ import annotations

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationItem, RecommendationResult
from zomoto_ai.phase0.llm.client import LLMClient


class StubLLMClient(LLMClient):
    """
    A deterministic placeholder that returns candidates as-is.
    Useful for wiring checks before introducing a real provider.
    """

    def rank_and_explain(self, candidate_set: CandidateSet) -> RecommendationResult:
        items: list[RecommendationItem] = []
        for i, r in enumerate(candidate_set.candidates, start=1):
            expl = f"Selected from structured filters; matches location={candidate_set.user_preference.location!r}."
            items.append(RecommendationItem(restaurant_id=r.id, rank=i, explanation=expl))

        return RecommendationResult(
            user_preference=candidate_set.user_preference,
            items=items,
            summary="Stub ranking (Phase 0 wiring check).",
        )

