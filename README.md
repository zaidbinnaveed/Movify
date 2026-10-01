# Movify

An explainable movie-recommendation project that compares content-based recommendations with an item-to-item collaborative approach.

## What it demonstrates

### Content-based recommendations

Movify builds a human-readable feature corpus from genres, cast, directors, writers, and taglines. It vectorizes that corpus with TF-IDF and ranks movies using cosine similarity. Recommendation responses expose overlapping terms so a user can inspect why an item was suggested.

### Collaborative comparison

The repository also implements item-to-item cosine similarity over a generated user–item interaction matrix. Because the bundled movie data does not contain real user ratings, this matrix is **synthetic** and seeded for reproducibility. It is a teaching and comparison mechanism, not evidence of real audience behavior.

### Cold start

Users can begin with preferred genres and optional liked movies. The system builds a preference profile and returns recommendations without requiring an existing account history.

## Stack

- Python 3.11+
- pandas and NumPy
- scikit-learn
- Standard-library threaded HTTP server
- HTML, CSS, and JavaScript frontend

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python "RS Project/webapp/server.py"
```

Open [http://localhost:5055](http://localhost:5055).

## Repository layout

```text
RS Project/
├── movify/
│   ├── data.py
│   └── recommenders.py
└── webapp/
    ├── server.py
    └── static/
data/                       # bundled movie and relationship datasets
RS_Project_Report.pdf       # academic report
requirements.txt
pyproject.toml
```

## Honest scope

- The content model is based on metadata, not viewing behavior.
- Collaborative interactions are simulated and clearly marked as such in API explanations.
- Recommendation quality has not been validated through an online experiment or real-user study.
- The bundled datasets are appropriate for demonstration and coursework; review their original licenses before redistribution or commercial use.
