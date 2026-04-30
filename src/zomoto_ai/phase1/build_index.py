from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from datasets import load_dataset


@dataclass(frozen=True)
class ColumnMap:
    name: str
    location: Optional[str]
    city: Optional[str]
    area: Optional[str]
    cuisines: str
    cost_for_two: Optional[str]
    rating: Optional[str]
    votes: Optional[str]


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.strip().lower())


def _pick_col(cols: List[str], *candidates: str) -> Optional[str]:
    """
    Pick a column by trying multiple candidate names (exact/normalized match),
    then fall back to substring matching on normalized keys.
    """
    if not cols:
        return None

    by_norm = {_norm_key(c): c for c in cols}
    cand_norms = [_norm_key(c) for c in candidates]

    for cn in cand_norms:
        if cn in by_norm:
            return by_norm[cn]

    # substring fallback
    for cn in cand_norms:
        for k, orig in by_norm.items():
            if cn and cn in k:
                return orig
    return None


def infer_column_map(df: pd.DataFrame) -> ColumnMap:
    cols = list(df.columns)

    name = _pick_col(
        cols,
        "Restaurant Name",
        "restaurant_name",
        "name",
        "Restaurant",
        "Title",
    )
    cuisines = _pick_col(cols, "Cuisines", "cuisines", "Cuisine", "cuisine")

    if not name or not cuisines:
        raise ValueError(
            "Could not infer required columns. "
            f"Found columns={cols}. Need at least restaurant name and cuisines."
        )

    location = _pick_col(cols, "Location", "location", "Locality", "locality", "Address", "address")
    city = _pick_col(cols, "City", "city")
    area = _pick_col(cols, "Area", "area", "Subzone", "subzone")

    cost_for_two = _pick_col(
        cols,
        "Average Cost for two",
        "Average Cost for Two",
        "cost_for_two",
        "Cost for two",
        "Cost",
        "Price for two",
        "price_for_two",
    )
    rating = _pick_col(cols, "Aggregate rating", "aggregate_rating", "Rating", "rating", "rate")
    votes = _pick_col(cols, "Votes", "votes", "Vote Count", "vote_count")

    return ColumnMap(
        name=name,
        location=location,
        city=city,
        area=area,
        cuisines=cuisines,
        cost_for_two=cost_for_two,
        rating=rating,
        votes=votes,
    )


def _clean_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, float) and pd.isna(x):
        return None
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_int(x: Any) -> Optional[int]:
    s = _clean_str(x)
    if s is None:
        return None
    # keep digits and commas, then strip commas
    m = re.search(r"(-?\d[\d,]*)", s)
    if not m:
        return None
    try:
        val = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if val < 0:
        return None
    return val


def _parse_rating(x: Any) -> Optional[float]:
    s = _clean_str(x)
    if s is None:
        return None
    # handle "3.8/5"
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    if val < 0 or val > 5:
        return None
    return val


def _split_cuisines(x: Any) -> List[str]:
    s = _clean_str(x)
    if s is None:
        return []
    parts = re.split(r"[,/|]", s)
    out: List[str] = []
    seen = set()
    for p in parts:
        p2 = _clean_str(p)
        if not p2:
            continue
        # canonicalize: title-case but keep acronyms reasonably
        token = p2.strip()
        token_norm = token.lower()
        if token_norm not in seen:
            out.append(token)
            seen.add(token_norm)
    return out


def _make_id(name: str, city: Optional[str], area: Optional[str], location: Optional[str]) -> str:
    base = "|".join(
        [
            _norm_key(name),
            _norm_key(city or ""),
            _norm_key(area or ""),
            _norm_key(location or ""),
        ]
    )
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def build_processed_dataframe(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    def col_or_none(c: Optional[str]) -> pd.Series:
        return df[c] if c and c in df.columns else pd.Series([None] * len(df))

    names = df[cmap.name].map(_clean_str)
    locations = col_or_none(cmap.location).map(_clean_str)
    cities = col_or_none(cmap.city).map(_clean_str)
    areas = col_or_none(cmap.area).map(_clean_str)
    cuisines = df[cmap.cuisines].map(_split_cuisines)

    cost = col_or_none(cmap.cost_for_two).map(_parse_int) if cmap.cost_for_two else pd.Series([None] * len(df))
    rating = col_or_none(cmap.rating).map(_parse_rating) if cmap.rating else pd.Series([None] * len(df))
    votes = col_or_none(cmap.votes).map(_parse_int) if cmap.votes else pd.Series([None] * len(df))

    out = pd.DataFrame(
        {
            "name": names,
            "location": locations,
            "city": cities,
            "area": areas,
            "cuisines": cuisines,
            "cost_for_two": cost,
            "rating": rating,
            "votes": votes,
        }
    )

    out["id"] = [
        _make_id(n or "", c, a, l)
        for n, c, a, l in zip(out["name"].tolist(), out["city"].tolist(), out["area"].tolist(), out["location"].tolist())
    ]

    # minimum viable row: must have name and at least one cuisine token
    out = out[out["name"].notna()].copy()
    out = out[out["cuisines"].map(lambda xs: isinstance(xs, list) and len(xs) > 0)].copy()

    # reorder columns
    out = out[["id", "name", "location", "city", "area", "cuisines", "cost_for_two", "rating", "votes"]]
    return out.reset_index(drop=True)


def write_artifact(df: pd.DataFrame, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    ext = os.path.splitext(output_path)[1].lower()
    if ext in {".parquet"}:
        df.to_parquet(output_path, index=False)
    elif ext in {".csv"}:
        df.to_csv(output_path, index=False)
    else:
        raise ValueError(f"Unsupported output extension {ext!r}. Use .parquet or .csv")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Phase 1: build processed restaurant index")
    parser.add_argument(
        "--dataset",
        default="ManikaSaini/zomato-restaurant-recommendation",
        help="Hugging Face dataset name",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Dataset split to use (if omitted, uses the first available split)",
    )
    parser.add_argument(
        "--output",
        default="data/restaurants_processed.parquet",
        help="Output artifact path (.parquet or .csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit (useful for quick tests)",
    )
    args = parser.parse_args(argv)

    ds = load_dataset(args.dataset)
    split_name = args.split or next(iter(ds.keys()))
    table = ds[split_name]

    if args.limit is not None:
        table = table.select(range(min(args.limit, len(table))))

    df = table.to_pandas()
    cmap = infer_column_map(df)
    processed = build_processed_dataframe(df, cmap)

    write_artifact(processed, args.output)

    stats = {
        "input_rows": int(len(df)),
        "output_rows": int(len(processed)),
        "columns": list(df.columns),
        "column_map": cmap.__dict__,
        "output_path": args.output,
    }
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

