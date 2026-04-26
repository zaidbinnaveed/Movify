import pandas as pd

# Load both CSVs
persons = pd.read_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\persons.csv")
movie_persons = pd.read_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\movie_persons.csv")

# Merge a few records to check
check = movie_persons.merge(persons, on='personId', how='left')
print(check.head(10))
# Check for personIds in movie_persons that don't exist in persons.csv
missing = check[check['name'].isnull()]
print(missing)
# Sample 5 random rows to manually check
print(check.sample(5))
