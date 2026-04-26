import pandas as pd

persons = pd.read_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\persons.csv")

# Create personId as a unique identifier (can be index + 1)
persons['personId'] = persons.index + 1

# Reorder columns so personId is first
persons = persons[['personId', 'name']]

# Save back
persons.to_csv(r"C:\Users\RC\Desktop\Movie Knowldege Graph Project\data\persons.csv", index=False)
