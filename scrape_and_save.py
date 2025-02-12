import os
import requests
import time
from pymongo import MongoClient

# Environment variables
gitHub_token = os.getenv("GETHUB_TOKEN")
mongodb_url = os.getenv("MONGO_URL")

# GitHub API configurations
TOKEN = gitHub_token
HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.github.com/search/users"

# MongoDB Connection
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["getHub_email"]
collection = db["gethub_developers"]

BASE_URL = "https://api.github.com/search/users"

def fetch_users_by_filters(location, year, followers_range, per_page=100, max_pages=10):
    """Fetch users by location, year, and follower range."""
    all_users = []
    for page in range(1, max_pages + 1):
        query = f"location:{location} created:{year}-01-01..{year}-12-31 followers:{followers_range}"
        params = {"q": query, "per_page": per_page, "page": page}
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            users = data.get("items", [])
            all_users.extend(users)
            if len(users) < per_page:  # Stop pagination if fewer results than expected
                break
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break
    return all_users

def fetch_commits(owner, repo):
    """Fetch commits from a repository and extract emails."""
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    response = requests.get(commits_url, headers=HEADERS)
    if response.status_code == 200:
        commits = response.json()
        emails = [
            commit.get("commit", {}).get("author", {}).get("email")
            for commit in commits if commit.get("commit", {}).get("author", {}).get("email")
        ]
        return [email for email in emails if "noreply" not in email]
    else:
        return []

def fetch_developer_data(users, location):
    """Extract repositories and emails for each developer."""
    dev_data = []
    for user in users:
        dev_emails = []
        username = user["login"]
        repos_url = f"https://api.github.com/users/{username}/repos"
        repos_response = requests.get(repos_url, headers=HEADERS)
        if repos_response.status_code == 200:
            repos = repos_response.json()
            for repo in repos:
                owner = repo["owner"]["login"]
                repo_name = repo["name"]
                emails = fetch_commits(owner, repo_name)
                dev_emails.extend([email for email in emails if email not in dev_emails])
        if dev_emails:
            dev_data.append({
                "location": location,
                "username": username,
                "repos_url": repos_url,
                "emails": dev_emails,
            })
    return dev_data
def save_data(data):
    try:
        result = collection.insert_many(data)
        return {"message": "Data saved", "ids": [str(_id) for _id in result.inserted_ids]}
    except Exception as e:
        print(f"Error saving data: {str(e)}")
        return {"error": str(e)}
def main():
    countries = ["Mexico", "Argentina", "Chile", "Puerto Rico", "Peru", "Colombia", "Belize", "Costa Rica", "Dominican Republic", "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Panama", "Bolivia", "Ecuador", "Paraguay", "Uruguay", "Venezuela"]  # Add more countries as needed
    years = list(range(2014, 2016))
    followers_ranges = ["<10", "10..50"]

    all_developers = []
    all_emails = []

    for country in countries:
        print(f"Processing country: {country}")
        country_users = []
        sleep_time = 0
        for year in years:
            for followers_range in followers_ranges:
                sleep_time += 1
                print(f"Fetching users in {country}, Year: {year}, Followers: {followers_range}")
                users = fetch_users_by_filters(country, year, followers_range)
                country_users.extend(users)
                if sleep_time == 3:
                    print("Sleep Time ...")
                    time.sleep(180)
                    sleep_time = 0
        print(f"Total users found in {country}: {len(country_users)}")
        
        dev_data = fetch_developer_data(country_users, country)
        all_developers.extend(dev_data)
        for dev in dev_data:
            all_emails.extend(dev["emails"])

        print(f"Emails extracted from {country}: {len(all_emails)}")

        

    print(f"Total Developers: {len(all_developers)}")
    print(f"Total Emails: {len(all_emails)}")

    # Save final results
    save_data(all_developers)

if __name__ == "__main__":
    main()
