## ZomotoAIRecommendation

AI-powered restaurant recommendations (Zomato-style) built phase-wise.

### Phase 0 (implemented)
- **Domain models/contracts**: `Restaurant`, `UserPreference`, `CandidateSet`, `RecommendationResult`
- **Config**: single validated settings object (dataset path, provider/model, limits)
- **LLM abstraction**: `LLMClient` interface + a stub implementation
- **Runnable entrypoint**: prints a wiring check

### Phase 1 (implemented)
- **Ingestion + preprocessing**: downloads dataset, cleans/normalizes, writes processed artifact (`parquet`/`csv`)
- **Command**: `python -m zomoto_ai.phase1.build_index --limit 500 --output data/restaurants_processed.parquet`

### Phase 2 (implemented)
- **Web UI (input source)**: preference form that returns validated `UserPreference` JSON
- **Run**: `python -m zomoto_ai.phase2.web_ui` then open `http://127.0.0.1:8000`

### Phase 3 (implemented)
- **Retrieval/filtering + relaxation + reducer**: structured candidate generation from `data/restaurants_processed.parquet`
- **Usage (Python)**:
  - Load restaurants: `load_restaurants_from_parquet("data/restaurants_processed.parquet")`
  - Retrieve: `retrieve_with_relaxation(restaurants, pref, top_n=50)`

### Phase 4 (implemented)
- **Groq LLM ranking + grounded explanations**: ranks Phase 3 candidates and returns `RecommendationResult`
- **Env**: set `GROQ_API_KEY`
- **Usage (Python)**:
  - `from zomoto_ai.phase4.groq_ranker import GroqLLMClient`
  - `result = GroqLLMClient().rank_and_explain(candidate_set)`

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m zomoto_ai
```

### Configuration

Set environment variables (optional):
- `ZOMOTO_DATASET_PATH` (default: `data/restaurants_processed.parquet`)
- `ZOMOTO_LLM_PROVIDER` (default: `stub`)
- `ZOMOTO_LLM_MODEL` (default: `gpt-4o-mini`)
- `ZOMOTO_TOP_N` (default: `50`)

