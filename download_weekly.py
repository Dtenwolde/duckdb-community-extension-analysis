import requests
import pandas as pd
from datetime import datetime
import os
import duckdb 

conn = duckdb.connect("sources/download_data.duckdb")
# Fetch this week's download data
current_date = datetime.now()
iso_year, iso_week, _ = current_date.isocalendar()
url = f'https://community-extensions.duckdb.org/download-stats-weekly/{iso_year}/{iso_week:02}.json'
response = requests.get(url)
response.raise_for_status()

# Process data if available
data = response.json()
weekly_data = pd.DataFrame([(k, v) for k, v in data.items() if k != '_last_update'],
                           columns=['extension', 'downloads_last_week'])

# Format the date to include only the date part
weekly_data['_last_update'] = current_date.strftime('%Y-%m-%d')
weekly_data['week_number'] = iso_week
weekly_data['year'] = iso_year

# Append to existing CSV
file_path = 'compiled_download_metrics.csv'
if os.path.exists(file_path):
    weekly_data.to_csv(file_path, mode='a', header=False, index=False)
else:
    weekly_data.to_csv(file_path, mode='w', header=True, index=False)