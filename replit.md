# Movify — Explainable Movie Recommender

A cinematic, single-page web app that recommends movies from the IMDB Top 250
and explains *why* each pick was made. Two recommenders run side by side so
the differences are visible:

- **Content‑based** — TF‑IDF over genres/cast/directors/writers/tagline.
- **Collaborative** — item–item cosine similarity from a simulated user matrix.

## Project layout

```
data/                              # CSVs (IMDB Top 250 + extras)
RS Project/
  movify/
    data.py                        # CSV loader → MovieData
    recommenders.py                # content + collaborative models, cold start
  webapp/
    server.py                      # stdlib HTTP server, JSON API + static files
    static/
      index.html                   # UI shell
      styles.css                   # cinematic dark theme
      app.js                       # SVG poster generator + interactions
```

## API

| Method | Path                  | Purpose                                    |
| ------ | --------------------- | ------------------------------------------ |
| GET    | `/api/health`         | Status + counts                            |
| GET    | `/api/genres`         | Genre vocabulary                           |
| GET    | `/api/movies`         | Top‑rated / search (`?q=`, `?limit=`)      |
| GET    | `/api/featured`       | Hero pick (highest rating w/ tagline)      |
| GET    | `/api/movie/<id>`     | Full details (cast, crew, runtime, cert)   |
| POST   | `/api/recommend`      | Warm or cold start; returns primary+comparison |

## Run

The app is served by a single workflow (`Start application`) that runs:

```
python "RS Project/webapp/server.py"
```

It listens on `0.0.0.0:$PORT` (default `5000`).

## Notes on posters

We don't ship real poster images (no third‑party API key is required). Posters
are generated client‑side as crisp SVG — each title gets a deterministic
genre‑themed colour palette, the IMDB rank, the IMDB rating badge, and a
hover tagline. The hero uses the same generator for the featured movie.

## Recent fixes

- Recommendations API was throwing
  `int() argument … not 'NoneType'` because `set_index("movieId")` dropped the
  movieId column before passing the row to `movie_to_card`. We now restore it.
- The data CSV path now resolves to either `RS Project/data/` or the
  repository‑root `data/` so the server runs both bundled and unpacked.
- Server now binds `0.0.0.0:$PORT` (was `127.0.0.1:8000`).
- Source files were CRLF; converted to LF.
