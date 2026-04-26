from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .data import MovieData


def _join_tokens(values: List[str]) -> str:
    return " ".join([str(v).strip().replace(" ", "_") for v in values if str(v).strip()])


def _build_content_corpus(movies: pd.DataFrame) -> pd.Series:
    # Explainable, non-black-box representation: a bag of human-readable tokens.
    # No KG. Just content features.
    parts = []
    for _, r in movies.iterrows():
        tokens = []
        tokens.append(_join_tokens(r.get("genres") or []))
        tokens.append(_join_tokens((r.get("cast") or [])[:20]))
        tokens.append(_join_tokens((r.get("directors") or [])[:5]))
        tokens.append(_join_tokens((r.get("writers") or [])[:5]))
        tagline = str(r.get("tagline") or "").strip()
        if tagline:
            tokens.append(tagline)
        parts.append(" ".join([t for t in tokens if t]))
    return pd.Series(parts, index=movies.index)


@dataclass
class ContentBasedModel:
    vectorizer: TfidfVectorizer
    tfidf: Any  # scipy sparse
    feature_names: np.ndarray


def fit_content_model(data: MovieData) -> ContentBasedModel:
    corpus = _build_content_corpus(data.movies)
    vec = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_features=20_000,
    )
    tfidf = vec.fit_transform(corpus.tolist())
    return ContentBasedModel(vectorizer=vec, tfidf=tfidf, feature_names=np.array(vec.get_feature_names_out()))


def _top_overlap_terms(model: ContentBasedModel, a_idx: int, b_idx: int, k: int = 6) -> List[str]:
    # Explainability: show top TF-IDF terms that overlap between seed and recommendation.
    a = model.tfidf[a_idx]
    b = model.tfidf[b_idx]
    overlap = a.minimum(b)
    if overlap.nnz == 0:
        return []
    # get top indices by weight
    top = np.argsort(overlap.data)[::-1][:k]
    feat_idx = overlap.indices[top]
    terms = model.feature_names[feat_idx].tolist()
    # Make tokens nicer
    return [t.replace("_", " ") for t in terms]


def recommend_content(
    data: MovieData,
    model: ContentBasedModel,
    seed_movie_id: int,
    n: int = 12,
) -> List[Dict[str, Any]]:
    movies = data.movies
    seed_pos = movies.index[movies["movieId"].eq(seed_movie_id)]
    if len(seed_pos) == 0:
        return []
    seed_i = int(seed_pos[0])

    sims = cosine_similarity(model.tfidf[seed_i], model.tfidf).ravel()
    order = np.argsort(sims)[::-1]
    recs = []
    for j in order:
        if j == seed_i:
            continue
        recs.append(
            {
                "movieId": int(movies.iloc[j]["movieId"]),
                "score": float(sims[j]),
                "explanation": {
                    "type": "content",
                    "why": "Similar content features (genres/cast/crew/tagline).",
                    "top_terms": _top_overlap_terms(model, seed_i, int(j), k=6),
                },
            }
        )
        if len(recs) >= n:
            break
    return recs


def recommend_content_coldstart(
    data: MovieData,
    model: ContentBasedModel,
    preferred_genres: List[str],
    liked_movie_ids: Optional[List[int]] = None,
    n: int = 12,
) -> List[Dict[str, Any]]:
    # Build a pseudo "user document" from preferred genres + liked movies' content.
    liked_movie_ids = liked_movie_ids or []
    docs = []
    docs.append(_join_tokens(preferred_genres))
    if liked_movie_ids:
        subset = data.movies[data.movies["movieId"].isin(liked_movie_ids)]
        if not subset.empty:
            docs.extend(_build_content_corpus(subset).tolist())
    user_doc = " ".join([d for d in docs if d]).strip()
    if not user_doc:
        return []

    u = model.vectorizer.transform([user_doc])
    sims = cosine_similarity(u, model.tfidf).ravel()
    order = np.argsort(sims)[::-1]
    recs = []
    for j in order:
        mid = int(data.movies.iloc[j]["movieId"])
        if mid in set(liked_movie_ids):
            continue
        recs.append(
            {
                "movieId": mid,
                "score": float(sims[j]),
                "explanation": {
                    "type": "content",
                    "why": "Matches your stated preferences (content profile).",
                    "top_terms": [],
                },
            }
        )
        if len(recs) >= n:
            break
    return recs


@dataclass
class CollaborativeModel:
    item_sim: np.ndarray  # (items, items) cosine similarity
    movie_ids: np.ndarray  # aligned to rows/cols
    synthetic_users: int


def fit_collaborative_model(
    data: MovieData,
    synthetic_users: int = 500,
    seed: int = 4053,
) -> CollaborativeModel:
    """
    Explainable collaborative filtering using an item-item similarity matrix built from
    a simulated user-item rating matrix (since we only have IMDB Top 250).
    """
    rng = np.random.default_rng(seed)
    movies = data.movies
    movie_ids = movies["movieId"].to_numpy(dtype=int)

    # Build a synthetic user profile over genres
    genres = data.genres
    if not genres:
        # fallback: similarity based on IMDB rating only
        ratings = movies["rating"].fillna(movies["rating"].mean()).to_numpy(dtype=float)
        x = ratings[:, None]
        sim = cosine_similarity(x)
        return CollaborativeModel(item_sim=sim, movie_ids=movie_ids, synthetic_users=0)

    genre_to_idx = {g: i for i, g in enumerate(genres)}
    movie_genre_mat = np.zeros((len(movies), len(genres)), dtype=float)
    for i, gs in enumerate(movies["genres"].tolist()):
        for g in gs:
            j = genre_to_idx.get(g)
            if j is not None:
                movie_genre_mat[i, j] = 1.0

    # Synthetic user preferences (sparse-like): each user likes 2-5 genres
    user_genre = np.zeros((synthetic_users, len(genres)), dtype=float)
    for u in range(synthetic_users):
        k = int(rng.integers(2, min(6, len(genres) + 1)))
        idx = rng.choice(len(genres), size=k, replace=False)
        user_genre[u, idx] = 1.0
        # weight preferences a bit
        user_genre[u] *= rng.uniform(0.8, 1.2)

    # Base rating signal from IMDB rating (normalized)
    base = movies["rating"].fillna(movies["rating"].mean()).to_numpy(dtype=float)
    base = (base - base.min()) / (base.max() - base.min() + 1e-9)  # 0..1

    # Compute synthetic ratings: base + genre match + small noise, then clip 0..1
    match = user_genre @ movie_genre_mat.T  # (U, I)
    match = match / (match.max(axis=1, keepdims=True) + 1e-9)
    noise = rng.normal(0.0, 0.05, size=match.shape)
    ratings = 0.55 * base[None, :] + 0.45 * match + noise
    ratings = np.clip(ratings, 0.0, 1.0)

    # Item vectors are ratings across users; compute item-item cosine similarity
    item_sim = cosine_similarity(ratings.T)
    np.fill_diagonal(item_sim, 1.0)

    return CollaborativeModel(item_sim=item_sim, movie_ids=movie_ids, synthetic_users=synthetic_users)


def recommend_collaborative(
    data: MovieData,
    model: CollaborativeModel,
    seed_movie_id: int,
    n: int = 12,
) -> List[Dict[str, Any]]:
    # Item-based CF: recommend items most similar to the seed item.
    ids = model.movie_ids
    try:
        seed_idx = int(np.where(ids == int(seed_movie_id))[0][0])
    except Exception:
        return []

    sims = model.item_sim[seed_idx].copy()
    order = np.argsort(sims)[::-1]
    recs = []
    for j in order:
        if j == seed_idx:
            continue
        recs.append(
            {
                "movieId": int(ids[j]),
                "score": float(sims[j]),
                "explanation": {
                    "type": "collaborative",
                    "why": "Item-based similarity from a ratings interaction matrix (simulated).",
                    "because_of": [{"movieId": int(seed_movie_id), "strength": float(sims[j])}],
                },
            }
        )
        if len(recs) >= n:
            break
    return recs


def recommend_collaborative_coldstart(
    data: MovieData,
    model: CollaborativeModel,
    preferred_genres: List[str],
    n: int = 12,
) -> List[Dict[str, Any]]:
    # Cold start: build a pseudo seed by taking the best matching movie for the preferred genres,
    # then run item-based recommendations from it. Explanation remains collaborative + transparent.
    if not preferred_genres:
        return []
    movies = data.movies
    pref = set([g.strip() for g in preferred_genres if g.strip()])
    if not pref:
        return []
    scores = movies["genres"].apply(lambda gs: len(pref.intersection(set(gs or []))))
    if scores.max() <= 0:
        return []
    seed_movie_id = int(movies.iloc[int(scores.idxmax())]["movieId"])
    recs = recommend_collaborative(data, model, seed_movie_id=seed_movie_id, n=n)
    for r in recs:
        r["explanation"]["why"] = "Cold start: we picked a seed movie matching your genres, then used item-based similarity."
        r["explanation"]["seed_movieId"] = seed_movie_id
    return recs

