from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    dataset_path: str
    llm_provider: str
    llm_model: str
    top_n: int

    @staticmethod
    def load_from_env() -> "Settings":
        dataset_path = os.getenv("ZOMOTO_DATASET_PATH", "data/restaurants_processed.parquet")
        llm_provider = os.getenv("ZOMOTO_LLM_PROVIDER", "stub")
        llm_model = os.getenv("ZOMOTO_LLM_MODEL", "gpt-4o-mini")

        top_n_raw = os.getenv("ZOMOTO_TOP_N", "50")
        try:
            top_n = int(top_n_raw)
        except ValueError as e:
            raise ValueError(f"Invalid ZOMOTO_TOP_N={top_n_raw!r}. Must be an integer.") from e

        if top_n < 1 or top_n > 500:
            raise ValueError(f"Invalid ZOMOTO_TOP_N={top_n}. Must be between 1 and 500.")

        return Settings(
            dataset_path=dataset_path,
            llm_provider=llm_provider,
            llm_model=llm_model,
            top_n=top_n,
        )

