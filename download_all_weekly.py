import requests
import pandas as pd
from datetime import datetime, timedelta


# Define the start and end dates
start_date = datetime(2024, 10, 1)
end_date = datetime.now()

# Initialize an empty DataFrame to store the compiled data
compiled_data = pd.DataFrame()

conn = duckdb.connect("sources/download_data.duckdb")
# Iterate over each week in the date range
current_date = start_date
while current_date <= end_date:
    # Calculate the ISO year and week number
    iso_year, iso_week, _ = current_date.isocalendar()
    # Construct the URL for the current week's data
    url = f'https://community-extensions.duckdb.org/download-stats-weekly/{iso_year}/{iso_week:02}.json'
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

            # Debug: Print the data fetched for verification
            print(f"Data fetched for week {iso_year}-W{iso_week}:", weekly_data.head())

            # Append the weekly data to the compiled DataFrame
            compiled_data = pd.concat([compiled_data, weekly_data], ignore_index=True)
    except (requests.HTTPError, ValueError) as e:
        # Print the error if data for the current week is not available or parsing fails
        print(f"Error for {iso_year}-W{iso_week}: {e}")

    # Move to the next week
    current_date += timedelta(weeks=1)

# Save the compiled data to a CSV file
if not compiled_data.empty:
    compiled_data.to_csv('compiled_download_metrics.csv', index=False)
    print("Data saved to 'compiled_download_metrics.csv'")
else:
    print("No data available for the specified date range.")