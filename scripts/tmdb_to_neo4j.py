import pandas as pd
import ast

# Paths to the original CSVs
movies_file = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\tmdb\tmdb_5000_movies.csv"
credits_file = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\tmdb\tmdb_5000_credits.csv"

# Load CSVs
movies_df = pd.read_csv(movies_file)
credits_df = pd.read_csv(credits_file)

# Preview first 3 rows to confirm load
print(movies_df.head(3))
print(credits_df.head(3))
