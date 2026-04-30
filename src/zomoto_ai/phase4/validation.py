from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from zomoto_ai.phase0.domain.models import RecommendationItem, RecommendationResult, UserPreference


@dataclass(frozen=True)
class ValidationOutcome:
    ok: bool
    result: Optional[RecommendationResult]
    error: str


def validate_llm_output(
    *,
    obj: Dict[str, Any],
    user_preference: UserPreference,
    valid_ids: Set[str],
    top_k: int,
) -> ValidationOutcome:
    if not isinstance(obj, dict):
        return ValidationOutcome(False, None, "output is not a JSON object")

    items = obj.get("items")
    if not isinstance(items, list):
        return ValidationOutcome(False, None, "missing or invalid 'items' list")

    # Cap to top_k (model may return more)
    items = items[:top_k]
    if not items:
        return ValidationOutcome(False, None, "no items returned")

    parsed_items: List[RecommendationItem] = []
    seen_ids: Set[str] = set()
    seen_ranks: Set[int] = set()

    for raw in items:
        if not isinstance(raw, dict):
            return ValidationOutcome(False, None, "item is not an object")
        rid = raw.get("restaurant_id")
        if not isinstance(rid, str) or not rid.strip():
            return ValidationOutcome(False, None, "item missing restaurant_id")
        if rid not in valid_ids:
            return ValidationOutcome(False, None, f"hallucinated restaurant_id={rid!r}")
        if rid in seen_ids:
            return ValidationOutcome(False, None, f"duplicate restaurant_id={rid!r} - each restaurant must appear only once")
        seen_ids.add(rid)

        try:
            item = RecommendationItem(
                restaurant_id=rid,
                rank=int(raw.get("rank")),
                explanation=str(raw.get("explanation", "")).strip(),
            )
        except (ValueError, TypeError):
            return ValidationOutcome(False, None, "invalid rank or explanation types")
        except ValidationError as e:
            return ValidationOutcome(False, None, f"item validation error: {e}")

        if item.rank in seen_ranks:
            return ValidationOutcome(False, None, f"duplicate rank={item.rank}")
        seen_ranks.add(item.rank)
        parsed_items.append(item)

    # Normalize ranks to 1..n by sorting; we keep rank values but also ensure at least rank 1 exists.
    if 1 not in seen_ranks:
        return ValidationOutcome(False, None, "rank must start at 1")

    summary = obj.get("summary")
    if summary is not None and not isinstance(summary, str):
        summary = str(summary)

    try:
        result = RecommendationResult(user_preference=user_preference, items=parsed_items, summary=summary)
    except ValidationError as e:
        return ValidationOutcome(False, None, f"result validation error: {e}")

    return ValidationOutcome(True, result, "")

