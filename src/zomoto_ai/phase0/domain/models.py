from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Restaurant(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr

    # Keep flexible so we can map whatever the dataset provides in Phase 1.
    location: Optional[NonEmptyStr] = None
    city: Optional[NonEmptyStr] = None
    area: Optional[NonEmptyStr] = None

    cuisines: List[NonEmptyStr] = Field(default_factory=list)
    cost_for_two: Optional[int] = Field(default=None, ge=0)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    votes: Optional[int] = Field(default=None, ge=0)


class Budget(BaseModel):
    """
    Represents either a named bucket or an explicit numeric range.
    Phase 2 can normalize user input into this structure.
    """

    kind: Literal["bucket", "range"]
    bucket: Optional[Literal["low", "medium", "high"]] = None
    min_cost_for_two: Optional[int] = Field(default=None, ge=0)
    max_cost_for_two: Optional[int] = Field(default=None, ge=0)


class UserPreference(BaseModel):
    location: NonEmptyStr
    budget: Optional[Budget] = None
    cuisine: Optional[NonEmptyStr] = None
    min_rating: float = Field(default=0, ge=0, le=5)
    optional_constraints: List[NonEmptyStr] = Field(default_factory=list)


class CandidateSet(BaseModel):
    user_preference: UserPreference
    candidates: List[Restaurant]


class RecommendationItem(BaseModel):
    restaurant_id: NonEmptyStr
    rank: int = Field(ge=1)
    explanation: NonEmptyStr


class RecommendationResult(BaseModel):
    user_preference: UserPreference
    items: List[RecommendationItem]
    summary: Optional[str] = None

