from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MovieData:
    movies: pd.DataFrame  # id, title, year, rating, genres(list), cast(list), directors(list), writers(list), tagline
    genres: List[str]


def _split_csv_list(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    s = str(value).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def load_imdb_top250(csv_path: str | Path) -> MovieData:
    """
    Loads the IMDB Top 250 CSV (this project format) using pandas only.

    Expected columns (seen in `data/IMDB Top 250 Movies.csv`):
    - name, year, rating, genre, casts, directors, writers, tagline (others may exist)
    """
    df = pd.read_csv(str(csv_path))

    required = ["name", "year", "rating", "genre", "casts", "directors", "writers"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"IMDB Top 250 file missing columns: {missing}. Found: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "movieId": np.arange(1, len(df) + 1, dtype=int),
            "title": df["name"].astype(str).str.strip(),
            "year": pd.to_numeric(df["year"], errors="coerce").astype("Int64"),
            "rating": pd.to_numeric(df["rating"], errors="coerce"),
            "genres": df["genre"].apply(_split_csv_list),
            "cast": df["casts"].apply(_split_csv_list),
            "directors": df["directors"].apply(_split_csv_list),
            "writers": df["writers"].apply(_split_csv_list),
            "tagline": df["tagline"].fillna("").astype(str) if "tagline" in df.columns else "",
            "certificate": df["certificate"].fillna("").astype(str) if "certificate" in df.columns else "",
            "run_time": df["run_time"].fillna("").astype(str) if "run_time" in df.columns else "",
        }
    )

    out = out[out["title"].ne("")].reset_index(drop=True)
    out["movieId"] = np.arange(1, len(out) + 1, dtype=int)

    # Genre vocabulary
    genre_set = set()
    for gs in out["genres"].tolist():
        for g in gs:
            genre_set.add(g)
    genres = sorted(genre_set)

    return MovieData(movies=out, genres=genres)


def movie_to_card(movie_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal, frontend-friendly structure.
    Poster is a deterministic placeholder token (frontend renders image).
    """
    title = str(movie_row.get("title") or "")
    mid = int(movie_row.get("movieId"))
    year = movie_row.get("year")
    rating = movie_row.get("rating")
    genres = movie_row.get("genres") or []

    # deterministic hue token
    hue = (mid * 47) % 360

    return {
        "movieId": mid,
        "title": title,
        "year": int(year) if pd.notna(year) else None,
        "rating": float(rating) if pd.notna(rating) else None,
        "genres": list(genres),
        "tagline": str(movie_row.get("tagline") or ""),
        "poster": {"kind": "placeholder", "hue": hue},
    }

