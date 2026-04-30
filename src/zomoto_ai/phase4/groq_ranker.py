from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Set

from openai import OpenAI

from zomoto_ai.phase0.domain.models import CandidateSet, RecommendationResult
from zomoto_ai.phase0.llm.client import LLMClient
from zomoto_ai.phase4.parsing import extract_first_json_object
from zomoto_ai.phase4.prompting import build_correction_prompt, build_rank_prompt
from zomoto_ai.phase4.validation import validate_llm_output


@dataclass(frozen=True)
class GroqConfig:
    model: str = "llama-3.3-70b-versatile"
    timeout_s: float = 30.0
    max_retries: int = 1  # one correction attempt
    base_url: str = "https://api.groq.com/openai/v1"


class GroqLLMClient(LLMClient):
    def __init__(self, *, api_key: Optional[str] = None, config: GroqConfig = GroqConfig()):
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self._api_key:
            raise ValueError("Missing GROQ_API_KEY. Set it in your environment to use GroqLLMClient.")
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=config.base_url
        )
        self._config = config

    def rank_and_explain(self, candidate_set: CandidateSet) -> RecommendationResult:
        top_k = min(10, len(candidate_set.candidates)) or 0
        if top_k == 0:
            return RecommendationResult(user_preference=candidate_set.user_preference, items=[], summary="No candidates.")

        valid_ids: Set[str] = {r.id for r in candidate_set.candidates}

        prompt = build_rank_prompt(candidate_set, top_k=top_k)
        raw = self._chat(prompt)

        obj, err = extract_first_json_object(raw)
        if obj is None:
            # retry once with correction prompt using valid ids
            corr = build_correction_prompt(previous_output=raw, valid_ids=sorted(valid_ids), top_k=top_k)
            raw2 = self._chat(corr)
            obj, err = extract_first_json_object(raw2)
            if obj is None:
                raise ValueError(f"Unable to parse LLM JSON output: {err}")
            raw = raw2

        outcome = validate_llm_output(
            obj=obj,
            user_preference=candidate_set.user_preference,
            valid_ids=valid_ids,
            top_k=top_k,
        )
        if outcome.ok and outcome.result:
            return outcome.result

        # correction attempt
        corr2 = build_correction_prompt(previous_output=raw, valid_ids=sorted(valid_ids), top_k=top_k)
        raw3 = self._chat(corr2)
        obj3, err3 = extract_first_json_object(raw3)
        if obj3 is None:
            raise ValueError(f"Unable to parse corrected LLM JSON output: {err3}")

        outcome2 = validate_llm_output(
            obj=obj3,
            user_preference=candidate_set.user_preference,
            valid_ids=valid_ids,
            top_k=top_k,
        )
        if outcome2.ok and outcome2.result:
            return outcome2.result

        raise ValueError(f"LLM output validation failed: {outcome2.error or outcome.error}")

    def _chat(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()

