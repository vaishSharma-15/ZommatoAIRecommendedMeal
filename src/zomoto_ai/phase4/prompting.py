from __future__ import annotations

import json
from typing import Dict, List

from zomoto_ai.phase0.domain.models import CandidateSet, Restaurant


def _candidate_compact(r: Restaurant) -> Dict:
    return {
        "id": r.id,
        "name": r.name,
        "location": r.location,
        "city": r.city,
        "area": r.area,
        "cuisines": r.cuisines,
        "cost_for_two": r.cost_for_two,
        "rating": r.rating,
        "votes": r.votes,
    }


def build_rank_prompt(candidate_set: CandidateSet, *, top_k: int) -> str:
    """
    Strictly instruct the LLM to:
    - pick ONLY from candidate ids
    - keep explanations grounded in provided fields
    - return JSON only
    """
    pref = candidate_set.user_preference.model_dump()
    candidates = [_candidate_compact(r) for r in candidate_set.candidates]

    # Build preference context for explanations
    preference_text = ""
    if pref.get("optional_constraints"):
        preference_text = f" User's selected preferences: {', '.join(pref['optional_constraints'])}. YOU MUST mention these in explanations."
    
    payload = {
        "user_preference": pref,
        "candidates": candidates,
        "top_k": top_k,
        "output_schema": {
            "items": [
                {
                    "restaurant_id": "string (must be one of candidate ids)",
                    "rank": "integer starting at 1",
                    "explanation": "MUST include: cuisine match, location match, rating satisfaction, budget fit. IF user selected preferences exist, you MUST explicitly state: 'Matches your preference for [X]' or similar phrase for each preference.",
                }
            ],
            "summary": "optional string comparing top choices",
        },
    }

    prompt = (
        "You are ranking restaurants for a user.\n"
        "Rules:\n"
        "1) You MUST select restaurants ONLY from the provided candidates (use their `id`).\n"
        "2) You MUST NOT invent any attributes. Use ONLY these fields: name, location/city/area, cuisines, cost_for_two, rating, votes.\n"
        "3) Return EXACTLY top_k items, unless there are fewer candidates.\n"
        "4) CRITICAL: Each restaurant_id must appear ONLY ONCE. No duplicates allowed.\n"
        "5) Output must be VALID JSON only. No markdown, no extra text.\n"
        "6) Prioritize restaurants that match the user's optional constraints (if any) in your ranking.\n"
        "7) CRITICAL: In EVERY explanation, you MUST mention: cuisine match, location, rating, budget. IF user has selected preferences, you MUST explicitly state how this restaurant matches each preference using phrases like 'Great for families', 'Quick service available', 'Outdoor seating', etc.\n"
        f"{preference_text}\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}\n"
    )
    return prompt


def build_correction_prompt(
    *,
    previous_output: str,
    valid_ids: List[str],
    top_k: int,
) -> str:
    return (
        "Your previous output was invalid.\n"
        "Fix it using ONLY these valid candidate ids:\n"
        f"{json.dumps(valid_ids)}\n\n"
        "Return VALID JSON ONLY with schema:\n"
        "{ items: [{restaurant_id, rank, explanation}], summary?: string }\n"
        f"Constraints:\n- ranks start at 1\n- choose at most {top_k} items\n- restaurant_id must be in the valid ids\n- explanation must use ONLY provided candidate fields\n\n"
        f"PREVIOUS_OUTPUT:\n{previous_output}\n"
    )

