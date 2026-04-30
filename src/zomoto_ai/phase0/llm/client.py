from __future__ import annotations

from abc import ABC, abstractmethod

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult


class LLMClient(ABC):
    """
    Provider-agnostic interface for Phase 4.
    In Phase 0, we only define the contract.
    """

    @abstractmethod
    def rank_and_explain(self, candidate_set: CandidateSet) -> RecommendationResult:
        raise NotImplementedError

