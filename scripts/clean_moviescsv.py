import pandas as pd

movies = pd.read_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\movies_clean.csv")

# Show rows with nulls or empty values in key columns
bad_rows = movies[
    movies['movieId'].isnull() | movies['movieId'].eq('') |
    movies['title'].isnull() | movies['title'].eq('') |
    movies['year'].isnull() | movies['year'].eq('')
]

print(bad_rows)
movies = movies.dropna(subset=['movieId', 'title', 'year'])
movies = movies[movies['movieId'] != '']
movies = movies[movies['title'] != '']
movies = movies[movies['year'] != '']

# Ensure year is integer
movies['year'] = movies['year'].astype(int)

# Save cleaned CSV
movies.to_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\movies_clean.csv", index=False)
print("CSV cleaned and ready for Neo4j")
