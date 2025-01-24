import os
import requests
import time
from pymongo import MongoClient

gitHub_token = os.getenv('GETHUB_TOKEN')
mongodb_url = os.getenv('MONGO_URL')

TOKEN = gitHub_token
HEADERS = {"Authorization": f"token {TOKEN}"}
BASE_URL = "https://api.github.com/search/users"
# MongoDB Connection
client = MongoClient(mongodb_url)
db = client["getHub_email"]
collection = db["gethub_developers"]



developers = []

def fetch_users_by_year(location, year, per_page=100, max_pages=10):
    all_users = []
    for page in range(1, max_pages + 1):
        params = {
            "q": f"location:{location} created:{year}-01-01..{year}-12-31",
            "per_page": per_page,
            "page": page,
        }
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            users = data.get("items", [])
            all_users.extend(users)
            if len(users) < per_page:  # If fewer results than expected, stop pagination
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
        print(f"Error: {response.status_code} - {response.text}")
        return []

def extract_devs(devs):
    developers = devs[0]['users']
    location = devs[0]['location']
    dev_data = []
    for dev in developers:
        dev_emails = []
        username = dev["login"]
        repos_url = f"https://api.github.com/users/{username}/repos"
        repos_response = requests.get(repos_url, headers=HEADERS)
        e_index=0
        if repos_response.status_code == 200:
            repos = repos_response.json()
            for repo in repos:
                owner = repo["owner"]["login"]
                repo_name = repo["name"]
                emails = fetch_commits(owner, repo_name)
                for email in emails:
                    if email not in dev_emails:
                        dev_emails.append(email)
                        e_index = e_index +1
                        #print(f"Developer: {username}, Email: {email}")
        else:
            print(f"Failed to fetch repositories for {username}")
        if e_index > 0:
            print(f"Developer: {username}, Email: {e_index}")
            dev_data.append({'location':location,'username':username ,'repos_url':repos_url , 'e_index':e_index , 'emails': dev_emails})
    return dev_data

# Fetch users for each year
years = []
for i in range(2025,2026): years.append(i)
location = "Morocco"
results_by_year = {}
sleep_time = 0

for year in years:
    sleep_time= sleep_time+1

    #print(f"Fetching users created in {year}...")
    users = fetch_users_by_year(location, year)
    results_by_year[year] = users
    developers.append({'users':users , 'location':location})
    print(f"Found {len(users)} users created in {year}.")

    if sleep_time == 3:
        print("Sleep Time ...")
        time.sleep(180)
        sleep_time = 0


# Output results
for year, users in results_by_year.items():
    print(f"Year: {year}, Users Found: {len(users)}")


devs = extract_devs(developers)


def save_data(data):
    try:
        result = collection.insert_one(data[0])
        return {"message": "Data saved", "id": str(result.inserted_id)}
    except Exception as e:
        print(str(e))

#save_data(devs)