import pandas as pd
import ast

# File paths
movies_file = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\tmdb\tmdb_5000_movies.csv"
credits_file = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\tmdb\tmdb_5000_credits.csv"
output_folder = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data"

# Load CSVs
movies_df = pd.read_csv(movies_file)
credits_df = pd.read_csv(credits_file)

# -----------------------
# 1. Movies CSV
# -----------------------
movies_out = movies_df[['id', 'title', 'original_title', 'overview', 'release_date', 'budget', 'revenue', 'runtime', 'vote_average', 'vote_count']].copy()
movies_out.rename(columns={'id':'movieId'}, inplace=True)
movies_out.to_csv(f'{output_folder}/movies.csv', index=False)

# -----------------------
# 2. Genres CSV
# -----------------------
all_genres = []
for g_list in movies_df['genres']:
    try:
        genres = ast.literal_eval(g_list)
        for g in genres:
            all_genres.append(g['name'])
    except:
        pass

genres_unique = list(set(all_genres))
pd.DataFrame({'name': genres_unique}).to_csv(f'{output_folder}/genres.csv', index=False)

# -----------------------
# 3. Persons CSV (actors + directors + writers)
# -----------------------
persons_dict = {}  # key: name, value: role list

# Actors
for cast_str in credits_df['cast']:
    try:
        cast = ast.literal_eval(cast_str)
        for c in cast:
            name = c["name"]
            if name not in persons_dict:
                persons_dict[name] = set()
            persons_dict[name].add("Actor")
    except:
        pass

# Directors & Writers
for crew_str in credits_df['crew']:
    try:
        crew = ast.literal_eval(crew_str)
        for c in crew:
            if c['job'] in ['Director', 'Writer']:
                name = c["name"]
                if name not in persons_dict:
                    persons_dict[name] = set()
                persons_dict[name].add(c["job"])
    except:
        pass

# Convert to DataFrame with unique IDs
persons_list = []
for i, (name, roles) in enumerate(persons_dict.items(), start=1):
    persons_list.append({
        "personId": i,
        "name": name,
        "role": ", ".join(list(roles))
    })

persons_df = pd.DataFrame(persons_list)
persons_df.to_csv(f'{output_folder}/persons.csv', index=False)

# -----------------------
# 4. Movie–Genre relationships
# -----------------------
movie_genre_rows = []
for idx, row in movies_df.iterrows():
    try:
        genres = ast.literal_eval(row['genres'])
        for g in genres:
            movie_genre_rows.append({'movieId': row['id'], 'genre': g['name']})
    except:
        pass

pd.DataFrame(movie_genre_rows).to_csv(f'{output_folder}/movie_genres.csv', index=False)

# -----------------------
# 5. Movie–Person relationships
# -----------------------
movie_person_rows = []

name_to_id = { row["name"]: row["personId"] for _, row in persons_df.iterrows() }

# Actors
for idx, row in credits_df.iterrows():
    try:
        cast = ast.literal_eval(row['cast'])
        for c in cast:
            name = c['name']
            movie_person_rows.append({
                'movieId': row['movie_id'],
                'personId': name_to_id.get(name),
                'role': 'Actor'
            })
    except:
        pass

# Directors & Writers
for idx, row in credits_df.iterrows():
    try:
        crew = ast.literal_eval(row['crew'])
        for c in crew:
            if c['job'] in ['Director', 'Writer']:
                name = c['name']
                movie_person_rows.append({
                    'movieId': row['movie_id'],
                    'personId': name_to_id.get(name),
                    'role': c['job']
                })
    except:
        pass

pd.DataFrame(movie_person_rows).to_csv(f'{output_folder}/movie_persons.csv', index=False)

print("All 5 CSV files generated successfully!")
