from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from zomoto_ai.phase0.domain.models import CandidateSet, Restaurant, UserPreference


RelaxAction = Literal[
    "normalize_location",
    "relax_cuisine_exact_to_partial",
    "relax_cuisine_partial_to_any",
    "lower_min_rating",
    "expand_budget",
]


@dataclass(frozen=True)
class RelaxStep:
    action: RelaxAction
    note: str


@dataclass(frozen=True)
class RetrievalResult:
    """
    Phase 3 output:
    - `candidate_set` is what Phase 4 consumes.
    - `relax_steps` explains what changed if constraints were relaxed.
    """

    candidate_set: CandidateSet
    relax_steps: List[RelaxStep]
    total_candidates_before_reduce: int
    reduced_to: int


@dataclass(frozen=True)
class StructuredFiltersApplied:
    location_query: str
    cuisine_query: Optional[str]
    min_rating: float
    budget_note: Optional[str]


@dataclass(frozen=True)
class CandidateSelectionDebug:
    filters: StructuredFiltersApplied
    relax_steps: List[RelaxStep]
    returned_ids: List[str]
    total_candidates_before_reduce: int
    reduced_to: int

