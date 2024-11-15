import duckdb
import requests
import yaml
import os
from markdown import markdown  # Import the markdown library for conversion


# Function to load the GitHub token from a secret file
def load_github_token(file_path=".github_token"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Token file not found: {file_path}")
    with open(file_path, "r") as file:
        return file.read().strip()


# Load the GitHub token
GITHUB_TOKEN = load_github_token()
conn = duckdb.connect("sources/downloads/download_data.duckdb")

# Fetch unique extensions
unique_extensions = conn.execute("SELECT DISTINCT extension FROM downloads").fetchall()


# Function to fetch GitHub stars
def fetch_github_stars(repo_url, token=None):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(repo_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("stargazers_count", 0)
    else:
        print(f"Failed to fetch data for {repo_url}: {response.status_code}")
        return None


# Initialize results
results = []

# Iterate over extensions and fetch description.yml details
for extension in unique_extensions:
    extension_name = extension[0]
    description_file_url = f"https://raw.githubusercontent.com/duckdb/community-extensions/main/extensions/{extension_name}/description.yml"

    try:
        # Fetch the description.yml file
        response = requests.get(description_file_url)
        if response.status_code == 200:
            description_data = yaml.safe_load(response.text)

            # Extract fields from description.yml
            github_repo = description_data.get("repo", {}).get("github")
            extended_description = description_data.get("docs", {}).get("extended_description")
            hello_world = description_data.get("docs", {}).get("hello_world")
            version = description_data.get("extension", {}).get("version")
            description = description_data.get("extension", {}).get("description")
            build = description_data.get("extension", {}).get("build")
            language = description_data.get("extension", {}).get("language")
            license_type = description_data.get("extension", {}).get("license")
            maintainers = ", ".join(description_data.get("extension", {}).get("maintainers", []))
            excluded_platforms_raw = description_data.get("extension", {}).get("excluded_platforms", "")
            excluded_platforms = "\n".join([f"- {platform.strip()}" for platform in excluded_platforms_raw.split(";")]) if excluded_platforms_raw else "- None"
            excluded_platforms_html = markdown(excluded_platforms) if excluded_platforms else None
            requires_toolchains = description_data.get("extension", {}).get("requires_toolchains", "")
            ref = description_data.get("repo", {}).get("ref", "")

            # Convert Markdown to HTML
            extended_description_html = markdown(extended_description) if extended_description else None
            hello_world_html = markdown(hello_world) if hello_world else None

            # Fetch GitHub star count
            star_count = None
            if github_repo:
                repo_url = f"https://api.github.com/repos/{github_repo}"
                star_count = fetch_github_stars(repo_url, token=None)

            # Append all the extracted data
            results.append((
                extension_name, github_repo, star_count, extended_description, extended_description_html,
                hello_world, hello_world_html, version, description, build, language, license_type,
                maintainers, excluded_platforms, excluded_platforms_html, requires_toolchains, ref
            ))
            print(f"Processed {extension_name}: {star_count} stars")
        else:
            print(f"Failed to fetch description.yml for {extension_name}: {response.status_code}")
    except Exception as e:
        print(f"Error processing extension {extension_name}: {e}")

# Create or update the DuckDB table
conn.execute("""
    CREATE TABLE IF NOT EXISTS extension_details (
        extension TEXT,
        repo_url TEXT,
        star_count INTEGER,
        extended_description TEXT,
        extended_description_html TEXT,
        hello_world TEXT,
        hello_world_html TEXT,
        version TEXT,
        description TEXT,
        build TEXT,
        language TEXT,
        license TEXT,
        maintainers TEXT,
        excluded_platforms TEXT,
        excluded_platforms_html TEXT,
        requires_toolchains TEXT,
        ref TEXT
    )
""")

# Insert data into the DuckDB table
conn.executemany(
    """
    INSERT INTO extension_details VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    results
)

print("All extension details have been stored in the database.")