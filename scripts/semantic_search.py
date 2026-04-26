"""
semantic_search.py

In-memory semantic search + reasoning for a Movie Knowledge Graph.

NOTE (course constraint):
- This module intentionally uses ONLY: pandas, numpy, scikit-learn (not required here), and stdlib.
- No Neo4j, Streamlit, spaCy, requests, pyvis, or any other external packages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pathlib import Path

GENRE_KEYWORDS = [
    "action", "comedy", "drama", "thriller", "horror",
    "romance", "animation", "fantasy", "sci-fi", "science fiction",
    "mystery", "crime", "adventure", "family", "western", "documentary"
]

@dataclass(frozen=True)
class KG:
    movies: pd.DataFrame
    genres: pd.DataFrame
    persons: pd.DataFrame
    movie_genres: pd.DataFrame
    movie_persons: pd.DataFrame


def _split_list_field(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    s = str(value).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def load_imdb_top250_dataset(csv_path: str) -> KG:
    """
    Loads IMDB Top 250 dataset and builds an in-memory KG.

    Nodes:
    - Movie: title, year, rating
    - Genre: name
    - Person: name (roles are stored on edges in movie_persons)

    Edges:
    - movie_genres: (movieId, genre)
    - movie_persons: (movieId, personId, role) where role in {Actor, Director, Writer}
    """
    df = pd.read_csv(csv_path)

    # Minimal schema normalization for the IMDB Top 250 CSV in this workspace.
    # Required columns (observed): name, year, rating, genre, casts, directors, writers
    col_map = {
        "name": "title",
        "year": "year",
        "rating": "rating",
        "genre": "genre",
        "casts": "casts",
        "directors": "directors",
        "writers": "writers",
    }
    missing = [c for c in col_map.keys() if c not in df.columns]
    if missing:
        raise ValueError(f"IMDB dataset missing expected columns: {missing}. Found: {list(df.columns)}")

    movies = df[[*col_map.keys()]].rename(columns=col_map).copy()
    movies["year"] = pd.to_numeric(movies["year"], errors="coerce").astype("Int64")
    movies["rating"] = pd.to_numeric(movies["rating"], errors="coerce")
    movies = movies.dropna(subset=["title"]).copy()
    movies["title"] = movies["title"].astype(str).str.strip()
    movies = movies[movies["title"].ne("")].copy()
    movies = movies.reset_index(drop=True)
    movies.insert(0, "movieId", movies.index + 1)

    # Genres
    movie_genre_rows: List[Dict[str, Any]] = []
    for _, r in movies[["movieId", "genre"]].iterrows():
        for g in _split_list_field(r["genre"]):
            movie_genre_rows.append({"movieId": int(r["movieId"]), "genre": g})
    movie_genres = pd.DataFrame(movie_genre_rows)
    genres = pd.DataFrame({"name": sorted(movie_genres["genre"].dropna().unique().tolist())}) if not movie_genres.empty else pd.DataFrame({"name": []})

    # Persons (actors/directors/writers) + edge list
    name_to_id: Dict[str, int] = {}
    persons_rows: List[Dict[str, Any]] = []
    movie_person_rows: List[Dict[str, Any]] = []

    def get_person_id(name: str) -> int:
        name = str(name).strip()
        if name not in name_to_id:
            name_to_id[name] = len(name_to_id) + 1
            persons_rows.append({"personId": name_to_id[name], "name": name})
        return name_to_id[name]

    for _, r in movies[["movieId", "casts", "directors", "writers"]].iterrows():
        mid = int(r["movieId"])
        for a in _split_list_field(r["casts"]):
            pid = get_person_id(a)
            movie_person_rows.append({"movieId": mid, "personId": pid, "role": "Actor"})
        for d in _split_list_field(r["directors"]):
            pid = get_person_id(d)
            movie_person_rows.append({"movieId": mid, "personId": pid, "role": "Director"})
        for w in _split_list_field(r["writers"]):
            pid = get_person_id(w)
            movie_person_rows.append({"movieId": mid, "personId": pid, "role": "Writer"})

    persons = pd.DataFrame(persons_rows) if persons_rows else pd.DataFrame({"personId": [], "name": []})
    movie_persons = pd.DataFrame(movie_person_rows) if movie_person_rows else pd.DataFrame({"movieId": [], "personId": [], "role": []})
    movie_persons = movie_persons.dropna(subset=["personId"]).copy()
    movie_persons["personId"] = movie_persons["personId"].astype(int)
    movie_persons["movieId"] = movie_persons["movieId"].astype(int)

    return KG(
        movies=movies[["movieId", "title", "year", "rating"]],
        genres=genres,
        persons=persons,
        movie_genres=movie_genres,
        movie_persons=movie_persons,
    )


def get_actor_pagerank(limit=30):
    """
    Degree-based centrality inference for actors.
    """
    raise RuntimeError("get_actor_pagerank requires an in-memory KG instance. Use get_actor_pagerank_from_kg(kg, limit).")


def get_actor_pagerank_from_kg(kg: KG, limit: int = 30) -> List[Dict[str, Any]]:
    mp = kg.movie_persons
    persons = kg.persons

    actors = mp[mp["role"].eq("Actor")][["movieId", "personId"]].drop_duplicates()
    if actors.empty:
        return []

    # movieCount per actor
    movie_counts = actors.groupby("personId")["movieId"].nunique().rename("movieCount")

    # co-actor count per actor (distinct co-actors across movies)
    merged = actors.merge(actors, on="movieId", suffixes=("", "_co"))
    merged = merged[merged["personId"].ne(merged["personId_co"])]
    co_counts = merged.groupby("personId")["personId_co"].nunique().rename("coActorCount")

    scores = (
        pd.concat([movie_counts, co_counts], axis=1)
        .fillna(0.0)
        .assign(score=lambda d: d["movieCount"] * 1.0 + d["coActorCount"] * 0.5)
        .sort_values("score", ascending=False)
        .head(int(limit))
    )

    out = (
        scores.reset_index()
        .merge(persons, on="personId", how="left")
        .rename(columns={"name": "actor"})[["actor", "score"]]
    )
    return out.to_dict(orient="records")


def get_actor_influence_map():
    """
    Returns { actor_name : influence_score }
    """
    raise RuntimeError("get_actor_influence_map requires an in-memory KG instance. Use get_actor_influence_map_from_kg(kg).")


def get_actor_influence_map_from_kg(kg: KG) -> Dict[str, float]:
    rows = get_actor_pagerank_from_kg(kg, limit=10_000)
    return {r["actor"]: float(r["score"]) for r in rows if r.get("actor")}



def parse_with_heuristics(user_input: str) -> Dict[str, Any]:
    """
    Minimal parser using regex + keyword heuristics (stdlib-only).
    Output schema matches the original UI logic.
    """
    filters = {"genres": [], "actors": [], "directors": [], "keywords": [],
               "min_year": None, "max_year": None, "min_rating": None}

    lower = user_input.lower()
    for g in GENRE_KEYWORDS:
        if re.search(r"\b" + re.escape(g) + r"\b", lower):
            filters["genres"].append(g.capitalize() if g != "sci-fi" else "Sci-Fi")

    # year constraints
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", user_input)]
    if years:
        # keep original behavior: treat "after/from/since" as min_year else first year as min_year
        if re.search(r"\b(after|from|since)\s+(19\d{2}|20\d{2})\b", lower):
            filters["min_year"] = years[0]
        else:
            filters["min_year"] = years[0]

    if re.search(r"\b(highly rated|top rated|best rated|popular)\b", lower):
        filters["min_rating"] = 7.5

    # director phrase
    directed_phrases = re.findall(r"(?:directed by|director|dir\.)\s+([A-Z][a-zA-Z .'-]+)", user_input)
    directed_phrases = [d.strip() for d in directed_phrases]

    # crude PERSON extraction: sequences of Capitalized words (2-4 tokens)
    candidates = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", user_input)
    for p in candidates:
        if any(p in d for d in directed_phrases) or re.search(r"directed by\s+" + re.escape(p).lower(), lower):
            filters["directors"].append(p)
        else:
            filters["actors"].append(p)

    # multiple actor detection
    with_match = re.search(r"(?:with|starring|featuring)\s+(.+)", lower)
    if with_match:
        after_with = re.split(r"\b(after|in|from|directed|directed by)\b", with_match.group(1))[0]
        pieces = re.split(r",| and |\s+&\s+", after_with)
        for piece in pieces:
            name = piece.strip()
            if name:
                candidate = " ".join([w.capitalize() for w in name.split()])
                if candidate and candidate not in filters["actors"] and len(candidate.split()) <= 4:
                    filters["actors"].append(candidate)

    # keywords (simple)
    kw = re.findall(r"\b[a-zA-Z]{4,}\b", lower)
    for k in kw:
        if k not in set(GENRE_KEYWORDS) and k not in filters["keywords"] and len(filters["keywords"]) < 5:
            filters["keywords"].append(k)

    filters["actors"] = list(dict.fromkeys(filters["actors"]))
    filters["directors"] = list(dict.fromkeys(filters["directors"]))
    filters["genres"] = list(dict.fromkeys(filters["genres"]))
    filters["keywords"] = list(dict.fromkeys(filters["keywords"]))

    return filters

def extract_filters(user_input: str, use_gpt: bool = False) -> Dict[str, Any]:
    # GPT and spaCy are intentionally not used to comply with allowed packages.
    _ = use_gpt
    return parse_with_heuristics(user_input)

def _movie_person_names(kg: KG, movie_ids: Sequence[int], role: str) -> pd.Series:
    mp = kg.movie_persons
    persons = kg.persons
    sub = mp[mp["movieId"].isin(movie_ids) & mp["role"].eq(role)][["movieId", "personId"]].drop_duplicates()
    if sub.empty:
        return pd.Series([[] for _ in movie_ids], index=pd.Index(movie_ids, name="movieId"))
    joined = sub.merge(persons, on="personId", how="left")
    grouped = joined.groupby("movieId")["name"].apply(lambda s: sorted([x for x in s.dropna().astype(str).tolist()]))
    return grouped.reindex(pd.Index(movie_ids, name="movieId"), fill_value=[])

def search_movies(kg: KG, user_input: str, use_gpt: bool = False) -> pd.DataFrame:
    filters = extract_filters(user_input, use_gpt=use_gpt)
    movies = kg.movies.copy()

    # Genres filter (Match ALL, consistent with prior aggregate_genres behavior)
    genres = filters.get("genres") or []
    if genres:
        mg = kg.movie_genres.copy()
        have = mg[mg["genre"].isin(genres)].groupby("movieId")["genre"].nunique()
        need = len(set(genres))
        ok_ids = have[have.eq(need)].index.astype(int)
        movies = movies[movies["movieId"].isin(ok_ids)].copy()

    # Actors/directors filters (ANY match)
    actors = filters.get("actors") or []
    if actors:
        mp = kg.movie_persons.merge(kg.persons, on="personId", how="left")
        ok_ids = mp[(mp["role"].eq("Actor")) & (mp["name"].isin(actors))]["movieId"].dropna().unique().tolist()
        movies = movies[movies["movieId"].isin(ok_ids)].copy()

    directors = filters.get("directors") or []
    if directors:
        mp = kg.movie_persons.merge(kg.persons, on="personId", how="left")
        ok_ids = mp[(mp["role"].eq("Director")) & (mp["name"].isin(directors))]["movieId"].dropna().unique().tolist()
        movies = movies[movies["movieId"].isin(ok_ids)].copy()

    min_year = filters.get("min_year")
    if min_year is not None:
        movies = movies[movies["year"].fillna(-1).astype(int) >= int(min_year)].copy()

    max_year = filters.get("max_year")
    if max_year is not None:
        movies = movies[movies["year"].fillna(10_000).astype(int) <= int(max_year)].copy()

    min_rating = filters.get("min_rating")
    if min_rating is not None:
        movies = movies[movies["rating"].fillna(0.0) >= float(min_rating)].copy()

    movies = movies.sort_values(["year", "rating"], ascending=[False, False]).head(50).copy()
    mids = movies["movieId"].astype(int).tolist()

    # Attach actors/directors lists (similar to prior RETURN cols)
    actors_list = _movie_person_names(kg, mids, role="Actor")
    directors_list = _movie_person_names(kg, mids, role="Director")

    out = movies.rename(columns={"title": "title", "year": "year", "rating": "rating"}).copy()
    out = out.assign(
        actors=[actors_list.loc[mid][:10] for mid in mids],
        directors=[directors_list.loc[mid][:2] for mid in mids],
    )[
        ["title", "year", "rating", "actors", "directors"]
    ]
    return out.reset_index(drop=True)

def _lookup_movie_candidates(kg: KG, title_query: str, limit: int = 100) -> List[Dict[str, Any]]:
    q = title_query.strip().lower()
    if not q:
        return []
    m = kg.movies.copy()
    mask = m["title"].astype(str).str.lower().str.contains(re.escape(q), regex=True)
    out = m[mask].sort_values("year", ascending=False).head(int(limit))[["title", "year"]]
    return out.to_dict(orient="records")


def compute_similar_movies(
    kg: KG,
    title_query: str,
    genre_weight: float = 2.0,
    actor_weight: float = 1.0,
    director_weight: float = 3.0,
    limit: int = 20,
) -> pd.DataFrame:
    """
    Re-implements the prior Cypher-based similarity computation using in-memory KG edges.
    Returns the same columns used by the original UI/explanation blocks.
    """
    candidates = _lookup_movie_candidates(kg, title_query, limit=200)
    if not candidates:
        return pd.DataFrame()
    # pick the best candidate: exact title match preferred, else newest year match
    exact = [c for c in candidates if c["title"].strip().lower() == title_query.strip().lower()]
    chosen_title = (exact[0]["title"] if exact else candidates[0]["title"])

    movies = kg.movies
    row = movies[movies["title"].astype(str).str.lower().eq(chosen_title.lower())]
    if row.empty:
        return pd.DataFrame()
    m1_id = int(row.iloc[0]["movieId"])

    mg = kg.movie_genres
    mp = kg.movie_persons.merge(kg.persons, on="personId", how="left")

    m1_genres = set(mg[mg["movieId"].eq(m1_id)]["genre"].dropna().astype(str).tolist())
    m1_actors = set(mp[(mp["movieId"].eq(m1_id)) & (mp["role"].eq("Actor"))]["name"].dropna().astype(str).tolist())
    m1_directors = set(mp[(mp["movieId"].eq(m1_id)) & (mp["role"].eq("Director"))]["name"].dropna().astype(str).tolist())

    # Precompute per-movie sets
    by_movie_genres = mg.groupby("movieId")["genre"].apply(lambda s: set(s.dropna().astype(str).tolist()))
    by_movie_actors = mp[mp["role"].eq("Actor")].groupby("movieId")["name"].apply(lambda s: set(s.dropna().astype(str).tolist()))
    by_movie_directors = mp[mp["role"].eq("Director")].groupby("movieId")["name"].apply(lambda s: set(s.dropna().astype(str).tolist()))

    out_rows: List[Dict[str, Any]] = []
    for mid, title, year in kg.movies[["movieId", "title", "year"]].itertuples(index=False, name=None):
        mid = int(mid)
        if mid == m1_id:
            continue
        shared_genres = sorted(list(m1_genres.intersection(by_movie_genres.get(mid, set()))))
        shared_actors = sorted(list(m1_actors.intersection(by_movie_actors.get(mid, set()))))
        shared_directors = sorted(list(m1_directors.intersection(by_movie_directors.get(mid, set()))))
        genres_overlap = len(shared_genres)
        shared_actors_count = len(shared_actors)
        shared_directors_count = len(shared_directors)
        score = (genre_weight * genres_overlap) + (actor_weight * shared_actors_count) + (director_weight * shared_directors_count)
        if score <= 0:
            continue
        out_rows.append(
            {
                "title": title,
                "year": int(year) if pd.notna(year) else None,
                "genresOverlap": genres_overlap,
                "sharedActors": shared_actors_count,
                "sharedDirectors": shared_directors_count,
                "sharedGenreNames": shared_genres,
                "sharedActorNames": shared_actors,
                "sharedDirectorNames": shared_directors,
                "score": float(score),
            }
        )

    df = pd.DataFrame(out_rows)
    if df.empty:
        return df
    return df.sort_values(["score", "genresOverlap", "sharedActors"], ascending=[False, False, False]).head(int(limit)).reset_index(drop=True)


def get_actor_genre_specialization(kg: KG, actor_name_query: str, limit: int = 20) -> pd.DataFrame:
    mp = kg.movie_persons.merge(kg.persons, on="personId", how="left")
    actors = mp[(mp["role"].eq("Actor")) & (mp["name"].astype(str).str.lower().str.contains(actor_name_query.strip().lower(), regex=False))]
    if actors.empty:
        return pd.DataFrame()
    # pick best match (first alphabetically for stability)
    chosen = sorted(actors["name"].dropna().astype(str).unique().tolist())[0]
    mids = actors[actors["name"].eq(chosen)]["movieId"].dropna().astype(int).unique().tolist()
    mg = kg.movie_genres[kg.movie_genres["movieId"].isin(mids)]
    out = mg.groupby("genre").size().rename("appearances").sort_values(ascending=False).head(int(limit)).reset_index()
    out.insert(0, "actor", chosen)
    return out


def multihop_director_actor_genre(kg: KG, director_query: str, genre: str, limit: int = 500) -> pd.DataFrame:
    mp = kg.movie_persons.merge(kg.persons, on="personId", how="left")
    mg = kg.movie_genres

    # director movies
    dir_rows = mp[(mp["role"].eq("Director")) & (mp["name"].astype(str).str.lower().str.contains(director_query.strip().lower(), regex=False))]
    if dir_rows.empty:
        return pd.DataFrame()
    chosen_dir = sorted(dir_rows["name"].dropna().astype(str).unique().tolist())[0]
    dir_movie_ids = dir_rows[dir_rows["name"].eq(chosen_dir)]["movieId"].dropna().astype(int).unique().tolist()

    # actors in director movies
    actors_in_dir = mp[(mp["role"].eq("Actor")) & (mp["movieId"].isin(dir_movie_ids))][["personId", "name", "movieId"]].drop_duplicates()
    if actors_in_dir.empty:
        return pd.DataFrame()

    # movies in target genre
    genre_movie_ids = mg[mg["genre"].astype(str).str.lower().eq(str(genre).strip().lower())]["movieId"].dropna().astype(int).unique().tolist()
    if not genre_movie_ids:
        return pd.DataFrame()

    # actors that also acted in target genre movies
    actors_in_genre = mp[(mp["role"].eq("Actor")) & (mp["movieId"].isin(genre_movie_ids))][["personId", "movieId"]].drop_duplicates()
    both = actors_in_dir.merge(actors_in_genre, on="personId", suffixes=("_dir", "_genre"))

    # Build title lists for explanation-like output
    movie_titles = kg.movies.set_index("movieId")["title"].to_dict()

    def top_titles(movie_ids: Iterable[int], k: int) -> List[str]:
        out = []
        for mid in list(dict.fromkeys([int(x) for x in movie_ids if pd.notna(x)]))[:k]:
            t = movie_titles.get(mid)
            if t:
                out.append(str(t))
        return out

    grouped = both.groupby("name").agg(
        with_director_in=("movieId_dir", lambda s: top_titles(s.tolist(), 5)),
        in_genre_movies=("movieId_genre", lambda s: top_titles(s.tolist(), 5)),
    ).reset_index().rename(columns={"name": "actor"})

    return grouped.sort_values("actor").head(int(limit)).reset_index(drop=True)


def main():
    project_root = Path(__file__).resolve().parents[1]
    kg = load_imdb_top250_dataset(str(project_root / "data" / "IMDB Top 250 Movies.csv"))

    # Demo: search
    print("=== Search demo ===")
    df = search_movies(kg, "thriller movie with Leonardo DiCaprio after 2010")
    print(df.head(10).to_string(index=False))

    # Demo: similarity + explanation columns
    print("\n=== Similarity demo ===")
    sim = compute_similar_movies(kg, "Inception", limit=10)
    print(sim[["title", "year", "genresOverlap", "sharedActors", "sharedDirectors", "score"]].to_string(index=False))

    # Demo: actor specialization
    print("\n=== Actor specialization demo ===")
    spec = get_actor_genre_specialization(kg, "Leonardo DiCaprio")
    print(spec.head(10).to_string(index=False))

    # Demo: multi-hop reasoning
    print("\n=== Multi-hop demo ===")
    mh = multihop_director_actor_genre(kg, "Christopher Nolan", "Sci-Fi")
    print(mh.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

