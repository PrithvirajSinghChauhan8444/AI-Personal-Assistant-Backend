import os
import requests
from dotenv import load_dotenv

# Load env variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
root_env_path = os.path.join(BASE_DIR, ".env")
config_path = root_env_path if os.path.exists(root_env_path) else os.path.join(BASE_DIR, "config", ".env")
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

def get_local_git_info():
    """
    Attempts to read the remote origin URL from the local git configuration
    to determine the default owner and repository name.
    """
    try:
        import subprocess
        res = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
            cwd=BASE_DIR
        )
        url = res.stdout.strip()
        if not url:
            return None, None
            
        owner, repo = None, None
        if "github.com" in url:
            if url.startswith("git@"):
                path = url.split("github.com:")[-1]
            else:
                path = url.split("github.com/")[-1]
                
            path = path.replace(".git", "")
            parts = path.split("/")
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1]
        return owner, repo
    except Exception:
        return None, None

def get_local_commits(branch: str = None, count: int = 5) -> list:
    """
    Queries local git log to get commit history from the filesystem repository.
    """
    try:
        import subprocess
        target_branch = branch or "HEAD"
        res = subprocess.run(
            ["git", "log", target_branch, f"-n", str(count), "--format=%H|%an|%ad|%s"],
            capture_output=True,
            text=True,
            check=True,
            cwd=BASE_DIR
        )
        lines = res.stdout.strip().split("\n")
        result = []
        for line in lines:
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                sha, author, date, message = parts
                result.append({
                    "sha": sha[:7],
                    "author": author,
                    "date": date,
                    "message": message,
                    "html_url": f"Local repository (branch: {target_branch})"
                })
        return result
    except Exception as e:
        return [{"error": f"Failed to read local git commits: {str(e)}"}]

def get_github_profile(username: str = None) -> dict:
    """
    Fetches basic profile information for a GitHub account.
    """
    headers = get_headers()
    
    if GITHUB_TOKEN and not username:
        url = "https://api.github.com/user"
    else:
        local_owner, _ = get_local_git_info()
        target_username = username or GITHUB_USERNAME or local_owner
        if not target_username:
            return {"error": "No GitHub username or GITHUB_TOKEN provided."}
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
            return {"error": f"Failed to fetch profile: Status {response.status_code}"}
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
        local_owner, _ = get_local_git_info()
        target_username = username or GITHUB_USERNAME or local_owner
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

def get_github_recent_activity(username: str = None, count: int = 5, include_private: bool = True) -> list:
    """
    Retrieves recent activity events for a GitHub user (including private events if authenticated).
    """
    headers = get_headers()
    local_owner, _ = get_local_git_info()
    target_username = username or GITHUB_USERNAME or local_owner
    if not target_username and GITHUB_TOKEN:
        profile = get_github_profile()
        target_username = profile.get("login")
            
    if not target_username:
        return [{"error": "No GitHub username or GITHUB_TOKEN provided."}]
        
    # Use /events for private events if authenticated, else /events/public
    endpoint_suffix = "events" if (include_private and GITHUB_TOKEN) else "events/public"
    url = f"https://api.github.com/users/{target_username}/{endpoint_suffix}?per_page={count}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            events = response.json()
            result = []
            for e in events:
                event_type = e.get("type")
                repo_name = e.get("repo", {}).get("name")
                created_at = e.get("created_at")
                
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
    Lists recent commits for a given repository, falling back to local Git database if remote branch is not found.
    """
    local_owner, local_repo = get_local_git_info()
    owner = username or GITHUB_USERNAME or local_owner
    if not owner and GITHUB_TOKEN:
        profile = get_github_profile()
        owner = profile.get("login")
            
    is_local_repo = False
    if local_repo and repo_name.lower().replace(".git", "") == local_repo.lower().replace(".git", ""):
        is_local_repo = True
        
    if not owner:
        if is_local_repo:
            return get_local_commits(branch, count)
        return [{"error": "No GitHub username/owner or GITHUB_TOKEN provided."}]
        
    url = f"https://api.github.com/repos/{owner}/{repo_name}/commits?per_page={count}"
    if branch:
        url += f"&sha={branch}"
        
    try:
        headers = get_headers()
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
            # Succeeded in resolving target owner/repo, but API failed (e.g. 404/422 branch not pushed to GitHub yet)
            if is_local_repo:
                local_res = get_local_commits(branch, count)
                if local_res and "error" not in local_res[0]:
                    return local_res
            return [{"error": f"Failed to fetch commits: Status {response.status_code} - {response.text}"}]
    except Exception as e:
        if is_local_repo:
            local_res = get_local_commits(branch, count)
            if local_res and "error" not in local_res[0]:
                return local_res
        return [{"error": f"Error fetching commits: {str(e)}"}]

def get_local_branches() -> list:
    """
    Lists all branches in the local git repository.
    """
    try:
        import subprocess
        res = subprocess.run(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            capture_output=True,
            text=True,
            check=True,
            cwd=BASE_DIR
        )
        lines = res.stdout.strip().split("\n")
        branches = []
        for line in lines:
            branch = line.strip()
            if not branch:
                continue
            if "HEAD" in branch:
                continue
            # Remove remote branch prefixes like origin/ to match local format where helpful
            if branch.startswith("remotes/"):
                branch = branch.replace("remotes/", "")
            branches.append(branch)
        return list(set(branches))
    except Exception as e:
        return [{"error": f"Failed to list local branches: {str(e)}"}]

def list_github_branches(repo_name: str, username: str = None) -> list:
    """
    Lists branches for a given repository. Falls back to local git branch list if remote fetch fails.
    """
    local_owner, local_repo = get_local_git_info()
    owner = username or GITHUB_USERNAME or local_owner
    if not owner and GITHUB_TOKEN:
        profile = get_github_profile()
        owner = profile.get("login")
        
    is_local_repo = False
    if local_repo and repo_name.lower().replace(".git", "") == local_repo.lower().replace(".git", ""):
        is_local_repo = True
        
    if not owner:
        if is_local_repo:
            return get_local_branches()
        return [{"error": "No GitHub username/owner or GITHUB_TOKEN provided."}]
        
    url = f"https://api.github.com/repos/{owner}/{repo_name}/branches"
    try:
        headers = get_headers()
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            branches = response.json()
            result = []
            for b in branches:
                result.append(b.get("name"))
            
            if is_local_repo:
                local_b = get_local_branches()
                if local_b and isinstance(local_b, list) and "error" not in local_b[0]:
                    result = list(set(result + local_b))
            return result
        else:
            if is_local_repo:
                local_res = get_local_branches()
                if local_res and isinstance(local_res, list) and "error" not in local_res[0]:
                    return local_res
            return [{"error": f"Failed to fetch branches from GitHub: Status {response.status_code}"}]
    except Exception as e:
        if is_local_repo:
            local_res = get_local_branches()
            if local_res and isinstance(local_res, list) and "error" not in local_res[0]:
                return local_res
        return [{"error": f"Error fetching branches: {str(e)}"}]


def get_github_file_content(repo_name: str, path: str, username: str = None, branch: str = None) -> dict:
    """
    Fetches the content of a file or lists a directory from a GitHub repository via the GitHub Contents API.
    """
    headers = get_headers()
    local_owner, local_repo = get_local_git_info()
    owner = username or GITHUB_USERNAME or local_owner
    if not owner and GITHUB_TOKEN:
        profile = get_github_profile()
        if profile and "login" in profile:
            owner = profile.get("login")
        
    if not owner:
        return {"error": "No GitHub username/owner or GITHUB_TOKEN provided."}
        
    # Remove leading slash from path if present
    clean_path = path.lstrip("/")
    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{clean_path}"
    if branch:
        url += f"?ref={branch}"
        
    try:
        import base64
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # It is a directory listing
                items = []
                for item in data:
                    items.append({
                        "name": item.get("name"),
                        "path": item.get("path"),
                        "type": item.get("type"),
                        "size": item.get("size"),
                        "html_url": item.get("html_url")
                    })
                return {
                    "type": "directory",
                    "path": clean_path,
                    "items": items
                }
            elif isinstance(data, dict):
                # It is a single file (or symlink, submodule, etc.)
                item_type = data.get("type")
                if item_type == "file":
                    encoding = data.get("encoding")
                    content_str = data.get("content", "")
                    if encoding == "base64":
                        try:
                            # Remove newlines
                            clean_content = content_str.replace("\n", "").replace("\r", "")
                            decoded_bytes = base64.b64decode(clean_content)
                            # Try to decode as utf-8 string
                            try:
                                decoded_text = decoded_bytes.decode("utf-8")
                                return {
                                    "type": "file",
                                    "name": data.get("name"),
                                    "path": data.get("path"),
                                    "size": data.get("size"),
                                    "encoding": "utf-8",
                                    "content": decoded_text,
                                    "html_url": data.get("html_url")
                                }
                            except UnicodeDecodeError:
                                # Binary file
                                return {
                                    "type": "file",
                                    "name": data.get("name"),
                                    "path": data.get("path"),
                                    "size": data.get("size"),
                                    "encoding": "binary",
                                    "content": "[Binary File content cannot be displayed]",
                                    "html_url": data.get("html_url")
                                }
                        except Exception as e:
                            return {"error": f"Failed to decode base64 content: {str(e)}"}
                    else:
                        # Return raw content if not base64
                        return {
                            "type": "file",
                            "name": data.get("name"),
                            "path": data.get("path"),
                            "size": data.get("size"),
                            "encoding": encoding,
                            "content": content_str,
                            "html_url": data.get("html_url")
                        }
                else:
                    return {
                        "type": item_type,
                        "name": data.get("name"),
                        "path": data.get("path"),
                        "html_url": data.get("html_url"),
                        "info": f"Content type is {item_type}"
                    }
            else:
                return {"error": "Unexpected API response format."}
        else:
            return {"error": f"Failed to fetch content: Status {response.status_code} - {response.text}"}
    except Exception as e:
        return {"error": f"Error fetching GitHub repository contents: {str(e)}"}


def search_github_code(query: str, username: str = None, repo_name: str = None, page: int = 1, count: int = 10) -> dict:
    """
    Searches for code inside GitHub repositories using the GitHub Search Code API.
    """
    headers = get_headers()
    local_owner, local_repo = get_local_git_info()
    
    owner = username or GITHUB_USERNAME or local_owner
    if not owner and GITHUB_TOKEN:
        profile = get_github_profile()
        if profile and "login" in profile:
            owner = profile.get("login")
        
    # Construct the query string
    q_parts = [query]
    if repo_name:
        if owner:
            q_parts.append(f"repo:{owner}/{repo_name}")
        else:
            q_parts.append(f"repo:{repo_name}")
    elif owner:
        # Search within owner's repositories by default if query doesn't specify any repo filter
        if "repo:" not in query and "user:" not in query and "org:" not in query:
            q_parts.append(f"user:{owner}")
            
    q_str = " ".join(q_parts)
    url = "https://api.github.com/search/code"
    params = {
        "q": q_str,
        "page": page,
        "per_page": count
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            items = []
            for item in data.get("items", []):
                items.append({
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "repository": item.get("repository", {}).get("full_name"),
                    "html_url": item.get("html_url")
                })
            return {
                "total_count": data.get("total_count"),
                "items": items
            }
        else:
            return {"error": f"Failed to search code: Status {response.status_code} - {response.text}"}
    except Exception as e:
        return {"error": f"Error searching code: {str(e)}"}

