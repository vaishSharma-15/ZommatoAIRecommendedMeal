# Detailed Edge Cases — ZomotoAIRecommendation

This document enumerates edge cases to handle across the end-to-end workflow described in:
- `docs/ProblemStatement.md`
- `docs/PhaseWiseArchitecture.md`

Each section lists **what can go wrong**, plus the **expected behavior** (and typical handling strategy).

---

## Phase 0 — Foundations (repo + contracts)

### Domain models & contracts
- **Schema mismatch between modules**
  - Example: ingestion outputs `costForTwo` but retrieval expects `cost_for_two`
  - **Expected behavior**: fail fast at boundaries with a clear message; do not proceed with silent field drops.
  - **Handling**: shared typed models/schemas; contract tests validating produced artifacts match expected schema.
- **Optional vs required fields unclear**
  - **Expected behavior**: every field is explicitly required/optional, and nullability is handled consistently across phases.
  - **Handling**: define “minimum viable restaurant row” and “minimum viable recommendation” contracts.
- **Inconsistent normalization rules**
  - Examples: cuisines title-cased in one place, lower-cased elsewhere
  - **Expected behavior**: one canonical normalization policy used by ingestion + preference parsing + retrieval.
  - **Handling**: central normalization utilities and golden tests.

### Configuration & environment
- **Missing or invalid environment variables**
  - Examples: LLM API key missing, model name invalid, dataset path not found
  - **Expected behavior**: clear startup error with the exact missing setting; do not fail later mid-run.
  - **Handling**: config validation at boot with helpful defaults where safe.
- **Misconfigured limits**
  - Examples: `TOP_N` too high, prompt token cap too low, retries set to 0 or extremely high
  - **Expected behavior**: clamp to safe ranges and warn; avoid runaway cost/latency.
  - **Handling**: configuration bounds + sensible defaults.

### LLM provider abstraction
- **Provider-specific response differences**
  - **Expected behavior**: all providers conform to one internal response contract.
  - **Handling**: adapter layer per provider; unit tests for parsing/formatting.
- **Model capability mismatch**
  - Example: model doesn’t support JSON mode/function calling (if you rely on it)
  - **Expected behavior**: degrade gracefully (use strict prompt + validator) or fail with a clear message.

### Identifiers & reproducibility
- **Unstable restaurant ids across builds**
  - **Expected behavior**: ids remain stable for the same normalized restaurant entry, otherwise caches/tests break.
  - **Handling**: deterministic id generation (hash of normalized fields) + collision strategy.
- **Prompt/version drift breaks caches**
  - **Expected behavior**: caches include prompt version/model version so changes don’t mix old/new behaviors.
  - **Handling**: versioned prompt templates and cache keys.

---

## Phase 1 — Data ingestion & preprocessing (offline build step)

### Dataset access & integrity
- **Dataset download fails (network/provider outage)**
  - **Expected behavior**: fail fast with a clear error and retry guidance; do not produce partial artifacts.
  - **Handling**: retries with backoff; allow using cached dataset if present and validated.
- **Partial/corrupted local cache**
  - **Expected behavior**: detect corruption and re-download; never silently continue with incomplete rows.
  - **Handling**: checksum/row-count validation; atomic writes for processed artifacts.
- **Schema drift in dataset**
  - **Expected behavior**: fail with a message naming missing/changed columns; do not build an incorrect index.
  - **Handling**: schema validation layer; mapping/compat for known alternate column names.

### Field-level parsing & normalization
- **Missing critical fields (name/location/cuisine/cost/rating)**
  - **Expected behavior**: either drop record (if unusable) or set to `null` and ensure downstream can render `N/A`.
  - **Handling**: define “minimum viable restaurant row” contract; log counts of dropped/kept rows.
- **Non-parseable rating**
  - Examples: `"NEW"`, `"--"`, `"3.8/5"`, empty strings
  - **Expected behavior**: rating becomes `null` (or a safe default) and is treated consistently in filtering/sorting.
  - **Handling**: robust parser + normalization to 0–5; log parse failures.
- **Non-parseable cost**
  - Examples: `"₹1,200 for two"`, `"Rs. 500"`, `"unknown"`
  - **Expected behavior**: cost becomes `null` and does not crash numeric comparisons.
  - **Handling**: currency stripping, comma removal, extracting first number; log parse failures.
- **Out-of-range numerics**
  - Examples: rating < 0 or > 5, negative cost/votes
  - **Expected behavior**: clamp or nullify and log; do not propagate obviously invalid values.
- **Cuisines are messy**
  - Examples: `"North Indian,Chinese"` (no space), duplicates, casing variants, trailing separators
  - **Expected behavior**: produce clean `cuisines[]` tokens; remove empties/dupes.
  - **Handling**: split on commas/slashes, trim, title-case/lower-case canonicalization.
- **Locations are messy**
  - Examples: aliases (`Bengaluru` vs `Bangalore`), combined city+area, inconsistent punctuation
  - **Expected behavior**: normalized location strings and (if available) split into `city` and `area`.
  - **Handling**: alias map, whitespace normalization, optional vocab-based canonicalization.

### Duplicates & identifiers
- **Duplicate rows for the same restaurant**
  - **Expected behavior**: stable `id` generation; duplicates do not appear multiple times in final candidate list.
  - **Handling**: dedupe key (e.g., normalized `name+area+city`), or keep best row by votes/recency if available.
- **Non-unique/unstable ids**
  - **Expected behavior**: every restaurant row used online must have a stable id across builds (within reasonable constraints).
  - **Handling**: deterministic hashing of normalized fields + collision handling.

### Artifact creation
- **Processed artifact unreadable by runtime**
  - **Expected behavior**: build step validates it can be loaded by the app before marking success.
  - **Handling**: read-after-write validation; atomic rename on success.

---

## Phase 2 — User preference collection (CLI/UI)

### Input validation
- **Empty or whitespace inputs**
  - **Expected behavior**: prompt again (CLI) or show validation errors (UI); do not proceed with invalid preferences.
- **Invalid min rating**
  - Examples: `"six"`, `-1`, `7`
  - **Expected behavior**: reject or coerce into [0,5] with explicit messaging.
- **Invalid budget**
  - Examples: non-numeric range, min > max, negative values, mixed currency formatting
  - **Expected behavior**: reject or normalize to numeric; clarify units (“for two”).
- **Unknown cuisine/location**
  - **Expected behavior**: attempt best-effort normalization (case-insensitive, alias/fuzzy); if still unknown, proceed with warning or treat as “no filter”.
  - **Handling**: vocab match + suggestion list (“Did you mean …?”) when possible.

### Ambiguity & expressiveness
- **Ambiguous location granularity**
  - Examples: area-only input (“MG Road”), city-only input (“Delhi”), mixed forms
  - **Expected behavior**: interpret consistently (prefer city match first, then area); record what was assumed.
- **Multi-cuisine request**
  - Examples: “Italian or Mexican”
  - **Expected behavior**: either support list input, or clearly state only one cuisine is supported and pick primary.
- **Optional constraints not present in data**
  - Examples: “family-friendly”, “outdoor seating”, “quick service”
  - **Expected behavior**: treat as **soft constraints** that influence LLM wording only; do not hard-filter on unknown attributes.
  - **Handling**: maintain a list of “supported structured constraints” vs “LLM-only preferences”.

---

## Phase 3 — Retrieval / filtering / relaxation (structured layer)

### Zero-match scenarios
- **No restaurants in the requested location**
  - **Expected behavior**: relax from area → city → nearby/any (configurable), or return a clear “no matches” explanation.
- **Cuisine not available in that location**
  - **Expected behavior**: relax cuisine match (exact → partial → any) in a controlled sequence and record steps.
- **Budget too tight**
  - **Expected behavior**: widen budget range gradually; if still none, explain that budget constraint is too strict.
- **Min rating too strict**
  - **Expected behavior**: lower min rating gradually; report the final applied minimum.

### Relaxation pitfalls
- **Relaxation order conflicts with user intent**
  - **Expected behavior**: use a consistent order and report it (e.g., relax location granularity before lowering rating).
- **Over-relaxation creates irrelevant results**
  - **Expected behavior**: stop after a max relax depth; return “no good matches” rather than misleading recommendations.

### Too-many-match scenarios
- **Huge candidate set for broad preferences**
  - **Expected behavior**: reduce deterministically to a compact `CandidateSet` suitable for the LLM.
  - **Handling**: `top-N` by rating/votes + diversity sampling (cuisine/area/price buckets).
- **Bias toward low-vote high-rating items**
  - **Expected behavior**: ranking should consider votes (or confidence) to avoid fragile results.
  - **Handling**: weighted score using rating + log(votes+1) when votes exist; sensible fallback when votes missing.
- **Random sampling breaks reproducibility**
  - **Expected behavior**: stable results for the same preference input (especially for demos/tests).
  - **Handling**: deterministic sampling or seeded randomness; log seed.

### Boundary conditions
- **Budget/rating boundary equality**
  - **Expected behavior**: define inclusive vs exclusive comparisons and keep consistent (typically inclusive).
- **Null cost/rating rows**
  - **Expected behavior**: define whether nulls are excluded by default or allowed when filters are not strict; never crash.

### Prompt size control
- **Candidate JSON exceeds token budget**
  - **Expected behavior**: shrink candidate list and/or fields; prefer fewer candidates over truncating critical fields.
  - **Handling**: max candidates; compact schema; truncate long text fields; include only required attributes.

---

## Phase 4 — LLM ranking & explanation (grounded output)

### Output validity & grounding
- **LLM returns restaurants not in candidates**
  - **Expected behavior**: reject/repair output; never present hallucinated restaurants.
  - **Handling**: require candidate `id` usage; validator checks ids; re-ask with stricter prompt on failure.
- **LLM mutates facts**
  - Examples: changes rating/cost/location in explanations
  - **Expected behavior**: explanations must match candidate attributes; otherwise corrected or removed.
  - **Handling**: post-validation against candidate data; re-ask or template-based regeneration.
- **LLM invents unsupported attributes**
  - Examples: “outdoor seating”, “kid-friendly” when not in dataset
  - **Expected behavior**: forbid claims not present in candidate fields; frame optional constraints as “may suit” only if supported.

### Formatting & parsing
- **Malformed JSON / missing fields**
  - **Expected behavior**: parser fails gracefully, retries once with a stricter format instruction, then falls back.
- **Duplicate entries / ties**
  - **Expected behavior**: enforce uniqueness; if fewer than requested remain, return fewer with explanation.

### Provider/runtime failures
- **Timeouts / rate limits**
  - **Expected behavior**: retry with backoff; optionally reduce candidate count; return structured-only ranking if LLM unavailable.
- **Model refusal**
  - **Expected behavior**: provide a deterministic non-LLM ranking and a short explanation that the LLM step was unavailable.
- **Cost blow-ups due to retries**
  - **Expected behavior**: cap retries; log and return best-effort results.

---

## Phase 5 — Presentation (CLI and/or API/UI)

### Result rendering
- **Fewer than top-K results**
  - **Expected behavior**: show available results without errors; explain why count is lower (few candidates / validation drop).
- **Missing display fields**
  - **Expected behavior**: render `N/A` consistently (cost/rating/votes missing) without breaking formatting.
- **Long strings & formatting**
  - **Expected behavior**: wrap or truncate cleanly; preserve readability in CLI.

### Consistency & trust
- **UI re-sorts results**
  - **Expected behavior**: preserve backend rank order; do not accidentally sort by rating again.
- **Generic explanations**
  - **Expected behavior**: explanations must cite at least 2 grounded attributes (e.g., cuisine + rating/cost + location).

---

## Phase 6 — Reliability, evaluation, and ops

### Caching & versioning
- **Cache key too weak (stale answers)**
  - **Expected behavior**: cache must vary by both user preference and candidate set/version.
  - **Handling**: key by `preference_hash + candidate_ids_hash + prompt_version + model_version`.
- **Stale index**
  - **Expected behavior**: runtime can detect index version/build timestamp and warn if outdated.

### Reproducibility & regression prevention
- **Non-deterministic pipeline**
  - **Expected behavior**: build and retrieval steps should be repeatable; LLM variability should be bounded.
  - **Handling**: deterministic reducer; store prompt templates with versioning; golden tests for grounding.

### Observability & diagnostics
- **Silent “no matches” due to vocab mismatch**
  - **Expected behavior**: logs should indicate whether zero matches came from location/cuisine/budget/rating.
  - **Handling**: counters for top unknown locations/cuisines; track relax-step frequency.

---

## Minimal acceptance-focused edge cases (must pass)

- **No matches** → system either relaxes constraints in a recorded order **or** returns a clear explanation.
- **Too many matches** → system reduces candidates deterministically before calling the LLM.
- **LLM hallucination** → validator blocks it; only candidates can be returned.
- **Missing fields** → output still renders with `N/A` and does not crash.

