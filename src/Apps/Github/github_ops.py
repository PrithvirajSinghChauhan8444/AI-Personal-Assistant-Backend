import os
import requests
from dotenv import load_dotenv

# Load env variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(BASE_DIR, "config", ".env")
load_dotenv(config_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

def get_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Personal-Assistant"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def get_github_profile(username: str = None) -> dict:
    """
    Fetches basic profile information for a GitHub account.
    If a GITHUB_TOKEN is present in env, it fetches the authenticated user's profile.
    Otherwise, fetches the public profile of the given username.
    """
    headers = get_headers()
    
    # If authenticated, fetch current user info if no username is supplied
    if GITHUB_TOKEN and not username:
        url = "https://api.github.com/user"
    else:
        target_username = username or GITHUB_USERNAME
        if not target_username:
            return {"error": "No GitHub username or GITHUB_TOKEN provided. Please specify a username or configure it in .env."}
        url = f"https://api.github.com/users/{target_username}"

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {
                "login": data.get("login"),
                "name": data.get("name"),
                "bio": data.get("bio"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "company": data.get("company"),
                "location": data.get("location"),
                "blog": data.get("blog"),
                "html_url": data.get("html_url"),
                "created_at": data.get("created_at")
            }
        else:
            return {"error": f"Failed to fetch profile: GitHub API returned status {response.status_code} - {response.text}"}
    except Exception as e:
        return {"error": f"Error fetching GitHub profile: {str(e)}"}

def list_github_repos(username: str = None, sort: str = "updated", count: int = 5) -> list:
    """
    Lists repositories for a GitHub user.
    """
    headers = get_headers()
    
    if GITHUB_TOKEN and not username:
        url = f"https://api.github.com/user/repos?sort={sort}&per_page={count}"
    else:
        target_username = username or GITHUB_USERNAME
        if not target_username:
            return [{"error": "No GitHub username or GITHUB_TOKEN provided."}]
        url = f"https://api.github.com/users/{target_username}/repos?sort={sort}&per_page={count}"
        
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            repos = response.json()
            result = []
            for r in repos:
                result.append({
                    "name": r.get("name"),
                    "description": r.get("description"),
                    "html_url": r.get("html_url"),
                    "stars": r.get("stargazers_count"),
                    "language": r.get("language"),
                    "forks": r.get("forks_count"),
                    "updated_at": r.get("updated_at")
                })
            return result
        else:
            return [{"error": f"Failed to fetch repositories: Status {response.status_code}"}]
    except Exception as e:
        return [{"error": f"Error listing repositories: {str(e)}"}]

def get_github_recent_activity(username: str = None, count: int = 5) -> list:
    """
    Retrieves recent activity events for a GitHub user.
    """
    headers = get_headers()
    target_username = username or GITHUB_USERNAME
    if not target_username:
        # If token is present, we can get current user first
        if GITHUB_TOKEN:
            profile = get_github_profile()
            target_username = profile.get("login")
            
    if not target_username:
        return [{"error": "No GitHub username or GITHUB_TOKEN provided."}]
        
    url = f"https://api.github.com/users/{target_username}/events/public?per_page={count}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            events = response.json()
            result = []
            for e in events:
                event_type = e.get("type")
                repo_name = e.get("repo", {}).get("name")
                created_at = e.get("created_at")
                
                # Extract summary based on event type
                summary = ""
                payload = e.get("payload", {})
                if event_type == "PushEvent":
                    commits = payload.get("commits", [])
                    commit_msg = commits[0].get("message") if commits else "No message"
                    summary = f"Pushed {len(commits)} commit(s): '{commit_msg}'"
                elif event_type == "IssuesEvent":
                    summary = f"{payload.get('action').capitalize()} issue #{payload.get('issue', {}).get('number')}: '{payload.get('issue', {}).get('title')}'"
                elif event_type == "PullRequestEvent":
                    summary = f"{payload.get('action').capitalize()} PR #{payload.get('number')}: '{payload.get('pull_request', {}).get('title')}'"
                elif event_type == "CreateEvent":
                    summary = f"Created {payload.get('ref_type')} '{payload.get('ref') or repo_name}'"
                elif event_type == "WatchEvent":
                    summary = f"Starred repository {repo_name}"
                else:
                    summary = f"Performed {event_type}"
                    
                result.append({
                    "event_type": event_type,
                    "repo": repo_name,
                    "summary": summary,
                    "created_at": created_at
                })
            return result
        else:
            return [{"error": f"Failed to fetch activity: Status {response.status_code}"}]
    except Exception as e:
        return [{"error": f"Error fetching GitHub activity: {str(e)}"}]

def list_github_commits(repo_name: str, username: str = None, branch: str = None, count: int = 5) -> list:
    """
    Lists recent commits for a given repository.
    """
    headers = get_headers()
    owner = username or GITHUB_USERNAME
    if not owner:
        if GITHUB_TOKEN:
            profile = get_github_profile()
            owner = profile.get("login")
            
    if not owner:
        return [{"error": "No GitHub username/owner or GITHUB_TOKEN provided."}]
        
    url = f"https://api.github.com/repos/{owner}/{repo_name}/commits?per_page={count}"
    if branch:
        url += f"&sha={branch}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            commits = response.json()
            result = []
            for c in commits:
                commit_info = c.get("commit", {})
                result.append({
                    "sha": c.get("sha")[:7],
                    "author": commit_info.get("author", {}).get("name"),
                    "date": commit_info.get("author", {}).get("date"),
                    "message": commit_info.get("message"),
                    "html_url": c.get("html_url")
                })
            return result
        else:
            return [{"error": f"Failed to fetch commits: Status {response.status_code} - {response.text}"}]
    except Exception as e:
        return [{"error": f"Error fetching commits: {str(e)}"}]
