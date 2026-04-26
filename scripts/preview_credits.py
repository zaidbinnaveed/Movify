import pandas as pd

# Path to your CSV
file_path = r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\tmdb\tmdb_5000_credits.csv"

# Read CSV
df = pd.read_csv(file_path)

# Show only the first 3 rows and just the headers + first 2 columns to keep it small
print(df.head(3).iloc[:, :3])
