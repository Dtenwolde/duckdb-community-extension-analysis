import requests
import pandas as pd
import duckdb
from datetime import datetime, timedelta

# Define the start and end dates
start_date = datetime(2024, 10, 1)
end_date = datetime.now()

# Connect to the DuckDB database
conn = duckdb.connect("sources/downloads/download_data.duckdb")

# Ensure the `downloads` table exists with the updated schema
conn.execute("""
    CREATE TABLE IF NOT EXISTS duckdb_downloads (
        extension VARCHAR,
        downloads_last_week BIGINT,
        _last_update DATE,
        week_number BIGINT,
        year BIGINT,
        type VARCHAR,
        PRIMARY KEY (extension, week_number, year)
    )
""")

# Iterate over each week in the date range
current_date = start_date
while current_date <= end_date:
    # Calculate the ISO year and week number
    iso_year, iso_week, _ = current_date.isocalendar()

    # Construct the URL for the current week's data
    url = f'https://extensions.duckdb.org/download-stats-weekly/{iso_year}/{iso_week}.json'
    try:
        # Attempt to fetch the data
        response = requests.get(url)
        response.raise_for_status()

        # Debug: Print status and URL
        print(f"Fetching data for {iso_year}-W{iso_week}: {url}")

        # Load JSON data directly from response
        data = response.json()

        # Convert the dictionary to a DataFrame and filter out `_last_update` rows
        if data:
            weekly_data = pd.DataFrame(
                [(k, v) for k, v in data.items() if k != '_last_update'],
                columns=['extension', 'downloads_last_week']
            )
            # Add columns for the week and last update timestamp
            weekly_data['_last_update'] = current_date
            weekly_data['week_number'] = iso_week
            weekly_data['year'] = iso_year
            weekly_data['type'] = 'DuckDB'

            # Debug: Print the data fetched for verification
            print(f"Data fetched for week {iso_year}-W{iso_week}:", weekly_data.head())
            if not weekly_data.empty:
                # Use INSERT OR REPLACE to update or insert data into the `downloads` table
                conn.executemany("""
                    INSERT OR REPLACE INTO downloads VALUES (?, ?, ?, ?, ?)
                """, weekly_data.values.tolist())
    except (requests.HTTPError, ValueError) as e:
        # Print the error if data for the current week is not available or parsing fails
        print(f"Error for {iso_year}-W{iso_week}: {e}")

    # Move to the next week
    current_date += timedelta(weeks=1)

print("Data has been successfully written to the `duckdb_downloads` table in the DuckDB database.")