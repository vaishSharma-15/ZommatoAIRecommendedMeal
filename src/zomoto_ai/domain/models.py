"""
Compatibility wrapper.

Canonical Phase 0 contracts live in `zomoto_ai.phase0.domain.models`.
"""

from zomoto_ai.phase0.domain.models import (  # noqa: F401
    Budget,
    CandidateSet,
    RecommendationItem,
    RecommendationResult,
    Restaurant,
    UserPreference,
)

__all__ = [
    "Budget",
    "CandidateSet",
    "RecommendationItem",
    "RecommendationResult",
    "Restaurant",
    "UserPreference",
]

