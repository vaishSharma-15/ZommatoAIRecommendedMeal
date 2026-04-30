from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse

from zomoto_ai.phase0.domain.models import Budget, UserPreference


app = FastAPI(title="ZomotoAIRecommendation — Phase 2")


def _split_optional_constraints(raw: str) -> List[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    # comma-separated; keep only non-empty trimmed items
    return [p.strip() for p in raw.split(",") if p.strip()]


def _budget_from_form(kind: str, bucket: str, min_cost: Optional[int], max_cost: Optional[int]) -> Optional[Budget]:
    kind = (kind or "").strip().lower()
    if kind == "none" or kind == "":
        return None

    if kind == "bucket":
        b = (bucket or "").strip().lower()
        if b not in {"low", "medium", "high"}:
            b = "medium"
        return Budget(kind="bucket", bucket=b)  # type: ignore[arg-type]

    if kind == "range":
        if min_cost is None and max_cost is None:
            return None
        return Budget(kind="range", min_cost_for_two=min_cost, max_cost_for_two=max_cost)

    # unknown -> no budget filter
    return None


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    # Minimal UI; Phase 0/2 goal is establishing the contract and validation.
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ZomotoAIRecommendation — Phase 2</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; max-width: 820px; }
      h1 { margin: 0 0 8px; }
      p { color: #444; }
      form { margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      label { display: block; font-size: 13px; color: #333; margin-bottom: 6px; }
      input, select { width: 100%; padding: 10px 12px; border: 1px solid #ccc; border-radius: 10px; }
      .full { grid-column: 1 / -1; }
      button { padding: 12px 14px; border: 0; border-radius: 12px; background: #111; color: #fff; cursor: pointer; }
      .hint { font-size: 12px; color: #666; margin-top: 6px; }
      code { background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }
    </style>
  </head>
  <body>
    <h1>Restaurant preferences</h1>
    <p>Phase 2 collects preferences and returns a validated <code>UserPreference</code> payload.</p>

    <form method="post" action="/preferences">
      <div class="full">
        <label>Location (required)</label>
        <input name="location" placeholder="e.g., Delhi, Bangalore" required />
      </div>

      <div>
        <label>Cuisine (optional)</label>
        <input name="cuisine" placeholder="e.g., Italian" />
      </div>

      <div>
        <label>Minimum rating (0–5)</label>
        <input name="min_rating" type="number" min="0" max="5" step="0.1" value="0" />
      </div>

      <div>
        <label>Budget type</label>
        <select name="budget_kind">
          <option value="none" selected>None</option>
          <option value="bucket">Bucket (low/medium/high)</option>
          <option value="range">Range (min/max cost for two)</option>
        </select>
        <div class="hint">Pick bucket or provide a numeric range.</div>
      </div>

      <div>
        <label>Budget bucket</label>
        <select name="budget_bucket">
          <option value="low">low</option>
          <option value="medium" selected>medium</option>
          <option value="high">high</option>
        </select>
      </div>

      <div>
        <label>Min cost for two (range)</label>
        <input name="min_cost_for_two" type="number" min="0" step="50" />
      </div>
      <div>
        <label>Max cost for two (range)</label>
        <input name="max_cost_for_two" type="number" min="0" step="50" />
      </div>

      <div class="full">
        <label>Optional constraints (comma-separated)</label>
        <input name="optional_constraints" placeholder="e.g., family-friendly, outdoor seating" />
      </div>

      <div class="full">
        <button type="submit">Create preference JSON</button>
      </div>
    </form>
  </body>
</html>
""".strip()


@app.post("/preferences")
def create_preferences(
    location: str = Form(...),
    cuisine: str = Form(""),
    min_rating: float = Form(0),
    budget_kind: str = Form("none"),
    budget_bucket: str = Form("medium"),
    min_cost_for_two: Optional[int] = Form(None),
    max_cost_for_two: Optional[int] = Form(None),
    optional_constraints: str = Form(""),
) -> JSONResponse:
    budget = _budget_from_form(budget_kind, budget_bucket, min_cost_for_two, max_cost_for_two)

    pref = UserPreference(
        location=location,
        budget=budget,
        cuisine=(cuisine.strip() or None),
        min_rating=min_rating,
        optional_constraints=_split_optional_constraints(optional_constraints),
    )

    return JSONResponse(pref.model_dump())


def main() -> None:
    import uvicorn

    uvicorn.run("zomoto_ai.phase2.web_ui:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()

