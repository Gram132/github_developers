import os
import requests
import time
import json
from pymongo import MongoClient

# Store multiple GitHub tokens in a list
GITHUB_TOKENS = [
    os.getenv("GETHUB_TOKEN_1"),
    os.getenv("GITHUB_TOKEN_2"),
    os.getenv("GITHUB_TOKEN_3"),
    os.getenv("GITHUB_TOKEN_4"),
    os.getenv("GITHUB_TOKEN_5"),
    os.getenv("GITHUB_TOKEN_6"),
    os.getenv("GITHUB_TOKEN_7"),
    os.getenv("GITHUB_TOKEN_8"),
    os.getenv("GITHUB_TOKEN_9"),
    os.getenv("GITHUB_TOKEN_10"),
]  # Add more tokens as needed

# Initialize token index
TOKEN_INDEX = 0

def get_headers():
    """Returns the current authorization headers with a rotating token."""
    global TOKEN_INDEX
    return {"Authorization": f"token {GITHUB_TOKENS[TOKEN_INDEX]}"}

def switch_token():
    """Switches to the next token in the list when rate limits are hit."""
    global TOKEN_INDEX
    TOKEN_INDEX = (TOKEN_INDEX + 1) % len(GITHUB_TOKENS)  # Rotate tokens
    print(f"⚠️ Switching to GitHub Token {TOKEN_INDEX + 1}")

# MongoDB Connection
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["getHub_email"]
collection = db["gethub_developers"]

BASE_URL = "https://api.github.com/search/users"

def fetch_users_by_filters(location, year, followers_range, per_page=100, max_pages=10):
    """Fetch users by location, year, and follower range with token rotation."""
    all_users = []
    
    for page in range(1, max_pages + 1):
        query = f"location:{location} created:{year}-01-01..{year}-12-31 followers:{followers_range}"
        params = {"q": query, "per_page": per_page, "page": page}
        
        while True:  # Keep retrying until a valid response is received
            response = requests.get(BASE_URL, headers=get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                users = data.get("items", [])
                all_users.extend(users)
                if len(users) < per_page:  # Stop pagination if fewer results than expected
                    break
                break  # Exit retry loop
            
            elif response.status_code == 403:  # Rate limit exceeded
                print("⚠️ Rate limit exceeded! Switching tokens...")
                switch_token()
                time.sleep(10)  # Wait a bit before retrying
            
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return []
    
    return all_users


def fetch_commits(owner, repo):
    """Fetch commits from a repository and extract emails."""
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    while True:
        response = requests.get(commits_url, headers=get_headers())
        
        if response.status_code == 200:
            commits = response.json()
            emails = [
                commit.get("commit", {}).get("author", {}).get("email")
                for commit in commits if commit.get("commit", {}).get("author", {}).get("email")
            ]
            return [email for email in emails if "noreply" not in email]
        
        elif response.status_code == 403:
            print("⚠️ Rate limit hit while fetching commits. Switching tokens...")
            switch_token()
            time.sleep(10)
        
        else:
            return []


def fetch_developer_data(users, location):
    """Extract repositories and emails for each developer."""
    dev_data = []
    
    for user in users:
        dev_emails = []
        username = user["login"]
        repos_url = f"https://api.github.com/users/{username}/repos"

        while True:
            repos_response = requests.get(repos_url, headers=get_headers())
            
            if repos_response.status_code == 200:
                repos = repos_response.json()
                for repo in repos:
                    owner = repo["owner"]["login"]
                    repo_name = repo["name"]
                    emails = fetch_commits(owner, repo_name)
                    dev_emails.extend([email for email in emails if email not in dev_emails])
                break
            
            elif repos_response.status_code == 403:
                print("⚠️ Rate limit hit while fetching repos. Switching tokens...")
                switch_token()
                time.sleep(10)
            
            else:
                break

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
        result = collection.insert_many(data)
        return {"message": "Data saved", "ids": [str(_id) for _id in result.inserted_ids]}
    except Exception as e:
        print(f"❌ Error saving data: {str(e)}")
        return {"error": str(e)}


def main():
    # Set up output directory
    repo_root = os.getenv("GITHUB_WORKSPACE", os.getcwd())  # Works locally & in GitHub Actions
    output_dir = os.path.join(repo_root, "countries")
    os.makedirs(output_dir, exist_ok=True)
    
    countries = ["France"]  # Add more countries
    years = list(range(2022, 2023))
    followers_ranges = ["<10", "10..50", "50..100", ">100"]

    all_developers = []
    all_emails = []

    for country in countries:
        print(f"🚀 Processing country: {country}")
        country_users = []
        sleep_time = 0

        for year in years:
            year_developers = []
            switch_token()
            time.sleep(10)
            for followers_range in followers_ranges:
                sleep_time += 1
                print(f"🔍 Fetching users in {country}, Year: {year}, Followers: {followers_range}")
                users = fetch_users_by_filters(country, year, followers_range)
                country_users.extend(users)
                print(f"✅ Total users found: {len(users)}")
                
                if sleep_time == 3:
                    print("⏳ Sleeping to avoid rate limits...")
                    time.sleep(180)
                    sleep_time = 0
            
            # Fetch repositories and emails
            dev_data = fetch_developer_data(country_users, country)
            year_developers.extend(dev_data)
            all_developers.extend(dev_data)
            for dev in dev_data:
                all_emails.extend(dev["emails"])

            print(f"📌 Developers found in {country}, Year: {year}: {len(year_developers)}")
            
            # Save to MongoDB
            save_data(year_developers)
            print(f"💾 Data saved for {country}, Year {year}")

        print(f"✅ Total users in {country}: {len(country_users)}")
        print(f"📧 Emails extracted from {country}: {len(all_emails)}")

    print(f"🚀 Total Developers: {len(all_developers)}")
    print(f"📩 Total Emails: {len(all_emails)}")


if __name__ == "__main__":
    main()
