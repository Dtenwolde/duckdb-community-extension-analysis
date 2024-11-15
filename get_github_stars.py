import duckdb
import requests
import yaml

# DuckDB connection
conn = duckdb.connect("sources/downloads/download_data.duckdb")

# Fetch unique extensions
unique_extensions = conn.execute("SELECT DISTINCT extension FROM downloads").fetchall()


# Function to fetch GitHub stars
def fetch_github_stars(repo_url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(repo_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("stargazers_count", 0)
    else:
        print(f"Failed to fetch data for {repo_url}: {response.status_code}")
        return None


# Iterate over extensions and fetch stars
results = []
for extension in unique_extensions:
    extension_name = extension[0]
    description_file_url = f"https://raw.githubusercontent.com/duckdb/community-extensions/main/extensions/{extension_name}/description.yml"

    try:
        # Fetch the description.yml file
        response = requests.get(description_file_url)
        if response.status_code == 200:
            description_data = yaml.safe_load(response.text)
            github_repo = description_data.get("repo", {}).get("github")

            if github_repo:
                repo_url = f"https://api.github.com/repos/{github_repo}"
                star_count = fetch_github_stars(repo_url,
                                                token=None)  # Replace `None` with your GitHub token if available

                if star_count is not None:
                    results.append((extension_name, github_repo, star_count))
                    print(f"{extension_name}: {star_count} stars")
            else:
                print(f"No GitHub repo found for extension {extension_name}")
        else:
            print(f"Failed to fetch description.yml for {extension_name}: {response.status_code}")
    except Exception as e:
        print(f"Error processing extension {extension_name}: {e}")

# Optionally, store results in DuckDB
df = conn.execute("CREATE TABLE IF NOT EXISTS github_stars (extension TEXT, repo_url TEXT, star_count INTEGER)")
conn.executemany(
    "INSERT INTO github_stars VALUES (?, ?, ?)",
    results
)
print("Star counts have been stored in the database.")
