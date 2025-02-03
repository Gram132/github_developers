import os
import requests
import time
import json
from pymongo import MongoClient

# Environment variables
gitHub_token = os.getenv("GETHUB_TOKEN")
mongodb_url = os.getenv("MONGO_URL")

# GitHub API configurations
TOKEN = gitHub_token
HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.github.com/search/users"

# MongoDB Connection
client = MongoClient(mongodb_url)
db = client["getHub_email"]
collection = db["gethub_developers"]

def fetch_users_by_filters(location, year, followers_range, per_page=100, max_pages=10):
    """Fetch users by location, year, and follower range."""
    all_users = []
    for page in range(1, max_pages + 1):
        query = f"location:{location} created:{year}-01-01..{year}-12-31 followers:{followers_range}"
        params = {"q": query, "per_page": per_page, "page": page}
        for _ in range(3):  # Retry logic
            try:
                response = requests.get(BASE_URL, headers=HEADERS, params=params)
                response.raise_for_status()
                data = response.json()
                users = data.get("items", [])
                all_users.extend(users)
                if len(users) < per_page:  # Stop if fewer results than expected
                    return all_users
                break  # Exit retry loop if successful
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}. Retrying...")
                time.sleep(5)  # Wait before retrying
        else:
            print(f"Failed to fetch users for query: {query}")
    return all_users

def fetch_commits(owner, repo):
    """Fetch commits from a repository and extract emails."""
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    for _ in range(3):  # Retry logic
        try:
            response = requests.get(commits_url, headers=HEADERS)
            response.raise_for_status()
            commits = response.json()
            emails = [
                commit.get("commit", {}).get("author", {}).get("email")
                for commit in commits if commit.get("commit", {}).get("author", {}).get("email")
            ]
            return [email for email in emails if "noreply" not in email]
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch commits for {owner}/{repo}: {e}")
            time.sleep(5)
    return []

def fetch_developer_data(users, location):
    """Extract repositories and emails for each developer."""
    dev_data = []
    for user in users:
        dev_emails = []
        username = user["login"]
        repos_url = f"https://api.github.com/users/{username}/repos"
        for _ in range(3):  # Retry logic
            try:
                repos_response = requests.get(repos_url, headers=HEADERS)
                repos_response.raise_for_status()
                repos = repos_response.json()
                for repo in repos:
                    owner = repo["owner"]["login"]
                    repo_name = repo["name"]
                    emails = fetch_commits(owner, repo_name)
                    dev_emails.extend([email for email in emails if email not in dev_emails])
                break
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch repos for {username}: {e}")
                time.sleep(5)
        if dev_emails:
            dev_data.append({
                "location": location,
                "username": username,
                "repos_url": repos_url,
                "emails": dev_emails,
            })
    return dev_data

def save_data(data):
    """Save data to MongoDB."""
    try:
        result = collection.insert_many(data, ordered=False)
        return {"message": "Data saved", "ids": [str(_id) for _id in result.inserted_ids]}
    except Exception as e:
        print(f"Error saving data: {str(e)}")
        return {"error": str(e)}

def main():
    countries = ["France"]  # Add more countries as needed
    years = list(range(2020, 2026))
    followers_ranges = ["<10", "10..50", "50..100", ">100"]

    all_emails = []

    for country in countries:
        print(f"Processing country: {country}")
        for year in years:
            for followers_range in followers_ranges:
                print(f"Fetching users in {country}, Year: {year}, Followers: {followers_range}")
                users = fetch_users_by_filters(country, year, followers_range)
                if users:
                    dev_data = fetch_developer_data(users, country)
                    if dev_data:
                        save_data(dev_data)  # Save each batch to MongoDB
                        all_emails.extend([email for dev in dev_data for email in dev["emails"]])
                    print(f"Saved data for {len(dev_data)} developers from {country}")
                time.sleep(2)  # To avoid hitting rate limits

        # Save intermediate results to a JSON file
        os.makedirs("output", exist_ok=True)
        with open(f"output/{country}_developers.json", "w") as f:
            json.dump(all_emails, f)
        print(f"Emails saved for {country}: {len(all_emails)}")

    print("Script completed successfully!")

if __name__ == "__main__":
    main()
