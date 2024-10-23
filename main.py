import duckdb
import pandas as pd
import requests

# Fetch data from the DuckDB community extensions source
response = requests.get('https://community-extensions.duckdb.org/downloads-last-week.json')
response.raise_for_status()
with open('downloads-last-week.json', 'wb') as file:
    file.write(response.content)

# Load the data into DuckDB
con = duckdb.connect()
df = con.execute("""
    UNPIVOT (
        SELECT 'community' AS repository, *
            FROM 'downloads-last-week.json'
    ) ON COLUMNS(* EXCLUDE (_last_update, repository))
    INTO NAME extension VALUE downloads_last_week
    ORDER BY downloads_last_week DESC;
""").fetchdf()

# Append to the existing CSV file
df['_last_update'] = pd.to_datetime(df['_last_update'])
df.to_csv('downloads_history.csv', mode='a', header=not pd.read_csv('downloads_history.csv').empty, index=False)
