from __future__ import annotations

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "webapp" / "static"

# The IMDB CSV may live inside the project (RS Project/data) or at the
# repository root (data/). Pick whichever exists so the server is portable
# across the bundled zip and the unpacked workspace.
def _resolve_data_path() -> Path:
    candidates = [
        PROJECT_ROOT / "data" / "IMDB Top 250 Movies.csv",
        PROJECT_ROOT.parent / "data" / "IMDB Top 250 Movies.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

DATA_PATH = _resolve_data_path()

# Allow importing project modules (no extra dependencies)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from movify.data import load_imdb_top250, movie_to_card  # noqa: E402
from movify.recommenders import (  # noqa: E402
    fit_collaborative_model,
    fit_content_model,
    recommend_collaborative,
    recommend_collaborative_coldstart,
    recommend_content,
    recommend_content_coldstart,
)


class AppState:
    data = None
    content_model = None
    collab_model = None


def get_state():
    if AppState.data is None:
        AppState.data = load_imdb_top250(str(DATA_PATH))
        AppState.content_model = fit_content_model(AppState.data)
        AppState.collab_model = fit_collaborative_model(AppState.data, synthetic_users=500, seed=4053)
    return AppState.data, AppState.content_model, AppState.collab_model


def _json_response(handler: BaseHTTPRequestHandler, payload, status: int = 200):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Movify-Version", "2")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _bad_request(handler: BaseHTTPRequestHandler, message: str):
    _json_response(handler, {"error": message}, status=400)


def _not_found(handler: BaseHTTPRequestHandler):
    _json_response(handler, {"error": "Not found"}, status=404)


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):  # noqa: N802
        # Helps browsers/clients in stricter environments; harmless for same-origin.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query or "")

        if path == "/":
            return self._serve_file(STATIC_DIR / "index.html")

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            return self._serve_file(STATIC_DIR / rel)

        if path == "/api/health":
            data, _, collab = get_state()
            return _json_response(
                self,
                {
                    "status": "ok",
                    "movies": int(data.movies.shape[0]),
                    "genres": int(len(data.genres)),
                    "collaborative": {"synthetic_users": int(collab.synthetic_users)},
                },
            )

        if path == "/api/genres":
            data, _, _ = get_state()
            return _json_response(self, {"genres": data.genres})

        if path == "/api/movies":
            data, _, _ = get_state()
            q = (qs.get("q") or [""])[0].strip().lower()
            limit = int((qs.get("limit") or ["60"])[0])
            df = data.movies.copy()
            if q:
                df = df[df["title"].astype(str).str.lower().str.contains(q, regex=False)]
            df = df.sort_values(["rating", "year"], ascending=[False, False]).head(limit)
            cards = [movie_to_card(r) for r in df.to_dict(orient="records")]
            return _json_response(self, {"results": cards})

        if path == "/api/featured":
            data, _, _ = get_state()
            # featured = top-rated with a tagline if available; else top-rated
            df = data.movies.copy()
            df["tagline_len"] = df["tagline"].astype(str).str.len()
            df = df.sort_values(["rating", "tagline_len", "year"], ascending=[False, False, False]).head(1)
            card = movie_to_card(df.iloc[0].to_dict()) if not df.empty else None
            return _json_response(self, {"featured": card})

        if path.startswith("/api/movie/"):
            try:
                mid = int(path[len("/api/movie/"):])
            except ValueError:
                return _bad_request(self, "Invalid movie id")
            data, _, _ = get_state()
            row = data.movies[data.movies["movieId"].eq(mid)]
            if row.empty:
                return _not_found(self)
            r = row.iloc[0].to_dict()
            card = movie_to_card(r)
            card["cast"] = list(r.get("cast") or [])[:12]
            card["directors"] = list(r.get("directors") or [])[:5]
            card["writers"] = list(r.get("writers") or [])[:5]
            card["certificate"] = str(r.get("certificate") or "")
            card["run_time"] = str(r.get("run_time") or "")
            return _json_response(self, {"movie": card})

        return _not_found(self)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            # Be tolerant: browsers may send UTF-8; some clients may include BOM.
            text = raw.decode("utf-8", errors="replace").lstrip("\ufeff").strip() or "{}"
            body = json.loads(text)
        except Exception as e:
            # Surface details to help debug "Failed to fetch"
            return _bad_request(self, f"Invalid JSON body. {type(e).__name__}: {e}")

        if path == "/api/recommend":
            try:
                data, content_model, collab_model = get_state()
                method = str(body.get("method") or "content").strip().lower()
                seed_movie_id = body.get("seed_movieId")
                preferred_genres = body.get("preferred_genres") or []
                liked_movie_ids = body.get("liked_movieIds") or []
                n = int(body.get("n") or 12)

                if seed_movie_id is not None:
                    seed_movie_id = int(seed_movie_id)

                by_id = data.movies.set_index("movieId")

                def hydrate(recs):
                    out = []
                    for r in recs:
                        mid = int(r["movieId"])
                        if mid in by_id.index:
                            row = by_id.loc[mid].to_dict()
                            row["movieId"] = mid  # set_index dropped this column
                            card = movie_to_card(row)
                            out.append({**card, "score": r.get("score"), "explanation": r.get("explanation")})
                    return out

                if seed_movie_id is None:
                    # Cold start flow
                    if method == "collaborative":
                        primary = hydrate(recommend_collaborative_coldstart(data, collab_model, preferred_genres, n=n))
                        comparison = hydrate(recommend_content_coldstart(data, content_model, preferred_genres, liked_movie_ids, n=n))
                    else:
                        primary = hydrate(recommend_content_coldstart(data, content_model, preferred_genres, liked_movie_ids, n=n))
                        comparison = hydrate(recommend_collaborative_coldstart(data, collab_model, preferred_genres, n=n))
                else:
                    if method == "collaborative":
                        primary = hydrate(recommend_collaborative(data, collab_model, seed_movie_id, n=n))
                        comparison = hydrate(recommend_content(data, content_model, seed_movie_id, n=n))
                    else:
                        primary = hydrate(recommend_content(data, content_model, seed_movie_id, n=n))
                        comparison = hydrate(recommend_collaborative(data, collab_model, seed_movie_id, n=n))

                return _json_response(
                    self,
                    {
                        "method": method,
                        "seed_movieId": seed_movie_id,
                        "primary": primary,
                        "comparison": comparison,
                    },
                )
            except Exception as e:
                traceback.print_exc()
                return _json_response(self, {"error": f"Server error: {type(e).__name__}: {e}"}, status=500)

        return _not_found(self)

    def _serve_file(self, path: Path):
        try:
            p = path.resolve()
            if not str(p).startswith(str(STATIC_DIR.resolve())):
                self.send_response(403)
                self.end_headers()
                return
            if not p.exists() or not p.is_file():
                self.send_response(404)
                self.end_headers()
                return

            content = p.read_bytes()
            ctype, _ = mimetypes.guess_type(str(p))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, fmt, *args):  # quieter console
        return


def main():
    import os
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "5000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Web app running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()

