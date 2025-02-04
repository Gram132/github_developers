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
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["getHub_email"]
collection = db["gethub_developers"]

BASE_URL = "https://api.github.com/search/users"

def fetch_users_by_filters(location, year, followers_range, per_page=100, max_pages=10):
    """Fetch users by location, year, and follower range with a 3-minute sleep after each year."""
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
            print(f"❌ Error: {response.status_code} - {response.text}")
            return []
    
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
    
    return []

def fetch_developer_data(users, location, year):
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
                "year": year,
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
    countries = ["Sweden"]
    years = list(range(2016, 2020))
    followers_ranges = ["<10", "10..50", "50..100", ">100"]
    
    all_developers = []
    all_emails = []

    for country in countries:
        print(f"🚀 Processing country: {country}")

        for year in years:
            year_developers = []
            print(f"🔍 Fetching users for {country}, Year: {year}")
            country_users = []

            for followers_range in followers_ranges:
                users = fetch_users_by_filters(country, year, followers_range)
                country_users.extend(users)
                print(f"✅ Users found: {len(users)}")
            
            dev_data = fetch_developer_data(country_users, country, year)
            year_developers.extend(dev_data)
            all_developers.extend(dev_data)
            for dev in dev_data:
                all_emails.extend(dev["emails"])

            print(f"📌 Developers found in {country}, Year: {year}: {len(year_developers)}")
            save_data(year_developers)
            print(f"💾 Data saved for {country}, Year {year}")
            
            print("⏳ Sleeping for 3 minutes to avoid GitHub rate limits...")
            time.sleep(180)  # Sleep for 3 minutes
    
    print(f"🚀 Total Developers: {len(all_developers)}")
    print(f"📩 Total Emails: {len(all_emails)}")

if __name__ == "__main__":
    main()
