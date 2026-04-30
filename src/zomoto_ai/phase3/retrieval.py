from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from zomoto_ai.phase0.domain.models import Budget, CandidateSet, Restaurant, UserPreference
from zomoto_ai.phase3.models import RelaxStep, RetrievalResult, StructuredFiltersApplied


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _contains(haystack: Optional[str], needle: str) -> bool:
    if not haystack:
        return False
    return _norm(needle) in _norm(haystack)


def load_restaurants_from_parquet(path: str) -> List[Restaurant]:
    df = pd.read_parquet(path)
    # Expected columns from Phase 1:
    # id, name, location, city, area, cuisines, cost_for_two, rating, votes
    restaurants: List[Restaurant] = []
    for row in df.to_dict(orient="records"):
        restaurants.append(
            Restaurant(
                id=str(row.get("id")),
                name=str(row.get("name")),
                location=row.get("location"),
                city=row.get("city"),
                area=row.get("area"),
                cuisines=list(row.get("cuisines", [])),
                cost_for_two=row.get("cost_for_two") if not pd.isna(row.get("cost_for_two")) else None,
                rating=row.get("rating") if not pd.isna(row.get("rating")) else None,
                votes=row.get("votes") if not pd.isna(row.get("votes")) else None,
            )
        )
    return restaurants


@dataclass(frozen=True)
class BudgetRanges:
    low_max: int = 500
    med_max: int = 1500


def budget_to_range(budget: Budget, ranges: BudgetRanges = BudgetRanges()) -> Tuple[Optional[int], Optional[int], str]:
    if budget.kind == "range":
        return budget.min_cost_for_two, budget.max_cost_for_two, "range"
    # bucket
    b = (budget.bucket or "medium").lower()
    if b == "low":
        return 0, ranges.low_max, "bucket:low"
    if b == "high":
        return ranges.med_max + 1, None, "bucket:high"
    return ranges.low_max + 1, ranges.med_max, "bucket:medium"


def _cuisine_exact_match(r: Restaurant, cuisine: str) -> bool:
    cq = _norm(cuisine)
    return any(_norm(c) == cq for c in (r.cuisines or []))


def _cuisine_partial_match(r: Restaurant, cuisine: str) -> bool:
    cq = _norm(cuisine)
    # More strict partial match: only match if the cuisine word appears as a separate word
    # This prevents "Thai" from matching "Mithai" or other unrelated cuisines
    for c in (r.cuisines or []):
        c_norm = _norm(c)
        # Check if cq is a separate word in c_norm (word boundary)
        words = c_norm.split()
        if cq in words:
            return True
        # Also check if c_norm is a separate word in cq
        words_cq = cq.split()
        if any(w in words_cq for w in words):
            return True
    return False


def _location_match(r: Restaurant, location: str) -> bool:
    # Try exact match first on area (most specific), then location, then city
    loc_norm = _norm(location)
    
    # Exact match on area (most specific)
    if r.area and _norm(r.area) == loc_norm:
        return True
    
    # Exact match on location
    if r.location and _norm(r.location) == loc_norm:
        return True
    
    # Exact match on city (least specific)
    if r.city and _norm(r.city) == loc_norm:
        return True
    
    # If no exact match, try contains as fallback but only on area/location (not city)
    # This allows for "Indiranagar" to match "Indiranagar 5th Block" but not "Bangalore"
    if r.area and loc_norm in _norm(r.area):
        return True
    if r.location and loc_norm in _norm(r.location):
        return True
    
    return False


def filter_candidates(
    restaurants: Sequence[Restaurant],
    pref: UserPreference,
    *,
    cuisine_mode: str = "exact",  # exact | partial | any
    min_rating: Optional[float] = None,
    budget: Optional[Budget] = None,
) -> List[Restaurant]:
    cuisine_mode = cuisine_mode.lower()
    min_rating_val = pref.min_rating if min_rating is None else min_rating
    budget_val = pref.budget if budget is None else budget

    out: List[Restaurant] = []
    for r in restaurants:
        if not _location_match(r, pref.location):
            continue

        if pref.cuisine:
            if cuisine_mode == "exact" and not _cuisine_exact_match(r, pref.cuisine):
                continue
            if cuisine_mode == "partial" and not _cuisine_partial_match(r, pref.cuisine):
                continue
            if cuisine_mode == "any":
                pass

        if r.rating is not None and r.rating < float(min_rating_val):
            continue
        if r.rating is None and float(min_rating_val) > 0:
            continue

        if budget_val is not None:
            min_c, max_c, _ = budget_to_range(budget_val)
            if r.cost_for_two is None:
                continue
            if min_c is not None and r.cost_for_two < min_c:
                continue
            if max_c is not None and r.cost_for_two > max_c:
                continue

        # Filter by optional constraints (preferences)
        # Use heuristics to score restaurants based on preferences since we don't have explicit attributes
        # Don't filter out, just score for ranking - this ensures we always have results
        if pref.optional_constraints:
            preference_score = 0
            for constraint in pref.optional_constraints:
                constraint_lower = constraint.lower()
                
                # Heuristic: Quick service - lower cost, certain cuisines
                if "quick" in constraint_lower:
                    if r.cost_for_two and r.cost_for_two <= 800:
                        preference_score += 2
                    if any(c.lower() in ["cafe", "fast food", "biryani", "rolls"] for c in r.cuisines):
                        preference_score += 1
                
                # Heuristic: Family-friendly - moderate pricing, popular cuisines
                if "family" in constraint_lower:
                    if r.cost_for_two and 500 <= r.cost_for_two <= 1500:
                        preference_score += 2
                    if any(c.lower() in ["north indian", "chinese", "italian", "continental"] for c in r.cuisines):
                        preference_score += 1
                
                # Heuristic: Outdoor Seating - higher rated, popular places (correlation)
                if "outdoor" in constraint_lower:
                    if r.rating and r.rating >= 4.5:
                        preference_score += 1
                    if r.votes and r.votes >= 1000:
                        preference_score += 1
                
                # Heuristic: Pet-friendly - cafes, outdoor-style places
                if "pet" in constraint_lower:
                    if any(c.lower() in ["cafe", "continental", "italian"] for c in r.cuisines):
                        preference_score += 2
                
                # Heuristic: Live Music - higher rated, more expensive places
                if "live music" in constraint_lower or "music" in constraint_lower:
                    if r.cost_for_two and r.cost_for_two >= 1000:
                        preference_score += 2
                    if r.rating and r.rating >= 4.5:
                        preference_score += 1
            
            # Store preference score for ranking (don't filter out)
            r._preference_score = preference_score

        out.append(r)
    return out


def _score(r: Restaurant) -> float:
    rating = float(r.rating or 0.0)
    votes = float(r.votes or 0.0)
    # Prefer higher rating; break ties with votes (log scaled).
    base_score = rating * 100.0 + math.log1p(votes)
    
    # Add preference score if available
    preference_score = getattr(r, '_preference_score', 0)
    return base_score + preference_score


def reduce_candidates(candidates: Sequence[Restaurant], top_n: int) -> List[Restaurant]:
    if len(candidates) <= top_n:
        return list(candidates)

    # Deterministic: sort by score then name/id.
    ranked = sorted(candidates, key=lambda r: (-_score(r), _norm(r.name), r.id))

    # Simple diversity: avoid too many from same primary cuisine + same city.
    picked: List[Restaurant] = []
    cuisine_city_counts: dict[Tuple[str, str], int] = {}
    max_per_bucket = max(2, top_n // 5)

    for r in ranked:
        if len(picked) >= top_n:
            break
        primary_cuisine = _norm((r.cuisines[0] if r.cuisines else "unknown"))
        city = _norm(r.city or r.location or "unknown")
        key = (primary_cuisine, city)
        if cuisine_city_counts.get(key, 0) >= max_per_bucket:
            continue
        picked.append(r)
        cuisine_city_counts[key] = cuisine_city_counts.get(key, 0) + 1

    # If diversity constraints were too strict, fill the remaining slots.
    if len(picked) < top_n:
        picked_ids = {p.id for p in picked}
        for r in ranked:
            if len(picked) >= top_n:
                break
            if r.id in picked_ids:
                continue
            picked.append(r)

    return picked


def retrieve_with_relaxation(
    restaurants: Sequence[Restaurant],
    pref: UserPreference,
    *,
    top_n: int,
) -> RetrievalResult:
    relax_steps: List[RelaxStep] = []

    cuisine_mode = "exact"
    min_rating = pref.min_rating
    budget = pref.budget

    candidates = filter_candidates(
        restaurants,
        pref,
        cuisine_mode=cuisine_mode,
        min_rating=min_rating,
        budget=budget,
    )

    # Relaxation sequence (recorded)
    # 1) normalize_location: implemented via contains match already; keep a step for transparency.
    relax_steps.append(
        RelaxStep(action="normalize_location", note="Location matching uses city/area/location contains normalization.")
    )

    # 2) relax cuisine exact -> partial
    if not candidates and pref.cuisine:
        cuisine_mode = "partial"
        relax_steps.append(
            RelaxStep(action="relax_cuisine_exact_to_partial", note="No matches; relaxed cuisine match to partial.")
        )
        candidates = filter_candidates(
            restaurants,
            pref,
            cuisine_mode=cuisine_mode,
            min_rating=min_rating,
            budget=budget,
        )

    # 3) DO NOT relax cuisine partial -> any - keep cuisine filter to ensure cuisine matches
    # Only relax rating and budget if needed

    # 4) lower min rating gradually
    if not candidates and min_rating > 0:
        new_min = float(min_rating)
        while new_min > 0 and not candidates:
            new_min = max(0.0, round(new_min - 0.5, 1))
            relax_steps.append(
                RelaxStep(action="lower_min_rating", note=f"No matches; lowered min_rating to {new_min}.")
            )
            candidates = filter_candidates(
                restaurants,
                pref,
                cuisine_mode=cuisine_mode,
                min_rating=new_min,
                budget=budget,
            )
        min_rating = new_min

    # 5) expand budget (drop or widen)
    if not candidates and budget is not None:
        relax_steps.append(
            RelaxStep(action="expand_budget", note="No matches; removed budget filter.")
        )
        candidates = filter_candidates(
            restaurants,
            pref,
            cuisine_mode=cuisine_mode,
            min_rating=min_rating,
            budget=None,
        )
        budget = None

    total_before = len(candidates)
    reduced = reduce_candidates(candidates, top_n=top_n)

    # CandidateSet keeps the original preference contract (Phase 4 expects it).
    # Relaxation steps are returned alongside via RetrievalResult.
    candidate_set = CandidateSet(user_preference=pref, candidates=reduced)
    return RetrievalResult(
        candidate_set=candidate_set,
        relax_steps=relax_steps,
        total_candidates_before_reduce=total_before,
        reduced_to=len(reduced),
    )


def describe_filters(pref: UserPreference) -> StructuredFiltersApplied:
    budget_note: Optional[str] = None
    if pref.budget:
        if pref.budget.kind == "bucket":
            budget_note = f"bucket:{pref.budget.bucket or 'medium'}"
        else:
            budget_note = f"range:{pref.budget.min_cost_for_two}-{pref.budget.max_cost_for_two}"
    return StructuredFiltersApplied(
        location_query=pref.location,
        cuisine_query=pref.cuisine,
        min_rating=pref.min_rating,
        budget_note=budget_note,
    )

