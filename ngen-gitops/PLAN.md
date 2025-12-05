# 🏗️ Build Plan: ngen-gitops

## Project Overview

**ngen-gitops** adalah Python package CLI dan Web Server untuk operasi GitOps dengan Bitbucket. Package ini menyediakan automasi untuk:
- Branch management
- Image updates dalam Kubernetes YAML
- Pull request creation & merging
- General git operations dengan multi-remote support (Bitbucket, GitHub, GitLab)

## 📋 Project Structure

```
ngen-gitops/
├── ngen_gitops/               # Main package directory
│   ├── __init__.py            # Package metadata (version, etc.)
│   ├── cli.py                 # CLI entry point (argparse)
│   ├── config.py              # Configuration management (.env)
│   ├── bitbucket.py           # Bitbucket API operations
│   ├── git_wrapper.py         # Git command wrapper
│   ├── server.py              # FastAPI web server
│   └── teams_notify.py        # Microsoft Teams notifications
├── pyproject.toml             # Package configuration & dependencies
├── setup.py                   # Legacy setup (optional)
├── MANIFEST.in                # Include non-Python files
├── README.md                  # Documentation
└── .gitignore                 # Git ignore rules
```

---

## 🔧 Step-by-Step Implementation

### Step 1: Initialize Project Structure

```bash
mkdir -p ngen-gitops/ngen_gitops
cd ngen-gitops
```

Create initial files:
1. `pyproject.toml` - Package configuration
2. `ngen_gitops/__init__.py` - Package metadata
3. `.gitignore` - Git ignore rules

### Step 2: Create Configuration Module (`config.py`)

**Purpose:** Manage application configuration from `.env` file and environment variables.

**Features:**
- Config directory: `~/.ngen-gitops/`
- Config file: `~/.ngen-gitops/.env`
- Auto-create sample `.env` on first run
- Priority: Environment variables > .env file

**Functions to implement:**

```python
# 1. Directory/file management
ensure_config_dir()          # Create ~/.ngen-gitops if not exists
create_default_env()         # Create sample .env with comments
config_exists() -> bool      # Check if .env exists
get_config_file_path() -> str  # Return path to .env

# 2. Load configuration
load_config() -> Dict[str, Any]  # Load all config as dictionary

# 3. Get specific config sections
get_bitbucket_credentials() -> Dict[str, str]  # username, app_password, org
get_server_config() -> Dict[str, Any]          # host, port
get_git_config() -> Dict[str, str]             # default_remote, default_org
get_default_remote() -> str   # e.g., "bitbucket.org"
get_default_org() -> str      # e.g., "loyaltoid"
get_teams_webhook() -> Optional[str]  # Teams webhook URL
get_current_user() -> str     # Get user name (git config or system)
```

**Configuration structure (.env format):**

```bash
# Bitbucket Credentials
BITBUCKET_USER=your-username
BITBUCKET_APP_PASSWORD=your-app-password
BITBUCKET_ORG=your-org

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Git Settings
GIT_DEFAULT_REMOTE=bitbucket.org
GIT_DEFAULT_ORG=your-org

# Notifications
TEAMS_WEBHOOK=https://your-org.webhook.office.com/...
```

**Dependencies:** `python-dotenv`

---

### Step 3: Create Git Wrapper Module (`git_wrapper.py`)

**Purpose:** Wrapper untuk git command dengan multi-remote support.

**Features:**
- Support Bitbucket, GitHub, GitLab remotes
- Build authenticated git URLs
- Execute git commands dengan error handling

**Exception Class:**

```python
class GitError(Exception):
    """Base exception for git operations."""
    pass
```

**Functions to implement:**

```python
# Internal helpers
_build_git_url(org, repo, remote, username=None, app_password=None) -> str
_run_git_command(args, cwd=None, capture_output=False) -> CompletedProcess

# Public git operations
git_clone(repo, branch=None, org=None, remote=None, username=None, 
          app_password=None, destination=None, single_branch=True, full=False)
git_pull(branch=None, cwd=None)
git_push(branch=None, cwd=None, force=False)
git_fetch(cwd=None)
git_commit(message, cwd=None, add_all=False)
git_status(cwd=None) -> str
git_add(files=None, cwd=None, all_files=False)
git_branch(list_all=False, cwd=None) -> str
git_checkout(branch, create=False, cwd=None)
```

**URL Building Logic:**
- Bitbucket: `https://username:app_password@bitbucket.org/org/repo.git`
- GitHub: `https://github.com/org/repo.git`
- GitLab: `https://gitlab.com/org/repo.git`

---

### Step 4: Create Bitbucket API Module (`bitbucket.py`)

**Purpose:** Bitbucket REST API integration untuk GitOps operations.

**API Base URL:** `https://api.bitbucket.org/2.0/repositories`

**Exception Class:**

```python
class GitOpsError(Exception):
    """Base exception for GitOps operations."""
    pass
```

**Functions to implement:**

```python
# 1. Create Branch
create_branch(repo, src_branch, dest_branch, username=None, 
              app_password=None, org=None, user=None) -> Dict
"""
Steps:
1. Get source branch commit hash via API
2. Create new branch using git push
3. Notify Teams (optional)
4. Return result with branch URL
"""

# 2. Update Image in YAML
set_image_in_yaml(repo, refs, yaml_path, image, dry_run=False,
                  username=None, app_password=None, org=None, user=None) -> Dict
"""
Steps:
1. Clone repository (tempdir)
2. Read YAML file
3. Update image field(s) recursively
4. Commit changes
5. Push to remote
6. Cleanup tempdir
7. Notify Teams (optional)
8. Return result with commit info
"""

# Helper functions for YAML
_extract_yaml_image(data) -> List[str]   # Find all image fields
_update_yaml_image(data, new_image)      # Update image fields recursively

# 3. Create Pull Request
create_pull_request(repo, src_branch, dest_branch, delete_after_merge=False,
                    username=None, app_password=None, org=None, user=None) -> Dict
"""
API: POST /repositories/{org}/{repo}/pullrequests
Body: {
    "title": "Merge {src} to {dest}",
    "source": {"branch": {"name": src_branch}},
    "destination": {"branch": {"name": dest_branch}},
    "close_source_branch": delete_after_merge
}
"""

# 4. Merge Pull Request
merge_pull_request(pr_url, delete_after_merge=False, 
                   username=None, app_password=None, user=None) -> Dict
"""
Steps:
1. Parse PR URL to extract org, repo, pr_id
2. Get PR details via API
3. Merge via API: POST /repositories/{org}/{repo}/pullrequests/{id}/merge
4. Notify Teams (optional)
"""

# 5. Kubernetes PR Workflow (Combined)
run_k8s_pr_workflow(cluster, namespace, deploy, image, 
                    approve_merge=False, repo="gitops-k8s", user=None) -> Dict
"""
Complete workflow:
1. Create branch: {namespace}/{deploy}_deployment.yaml
2. Set image in YAML: {namespace}/{deploy}_deployment.yaml
3. Create PR from new branch to cluster
4. (Optional) Merge PR if approve_merge=True
"""
```

**Dependencies:** `requests`, `pyyaml`

---

### Step 5: Create Teams Notification Module (`teams_notify.py`)

**Purpose:** Send notifications to Microsoft Teams via webhook.

**Functions to implement:**

```python
# Generic notification sender
send_teams_notification(title, message, color="0078D4", facts=None) -> bool
"""
Uses Microsoft Teams MessageCard format.
Silently skips if no webhook configured.
"""

# Specific notification types
notify_branch_created(repo, src_branch, dest_branch, branch_url, user=None)
notify_image_updated(repo, branch, yaml_path, image, commit, user=None)
notify_pr_created(repo, src_branch, dest_branch, pr_id, pr_url, user=None)
notify_pr_merged(repo, pr_id, src_branch, dest_branch, merge_commit, user=None)
```

**Teams Message Card Format:**

```python
{
    "@type": "MessageCard",
    "@context": "https://schema.org/extensions",
    "themeColor": "0078D4",  # Hex color
    "title": "Notification Title",
    "text": "Message body",
    "sections": [{
        "facts": [
            {"name": "Key", "value": "Value"},
            ...
        ]
    }]
}
```

**Color Codes:**
- Green (success): `28A745`
- Blue (info): `0078D4`
- Purple (PR): `6F42C1`

---

### Step 6: Create Web Server Module (`server.py`)

**Purpose:** FastAPI REST API server untuk GitOps operations.

**Framework:** FastAPI + Uvicorn

**Request Models (Pydantic):**

```python
class CreateBranchRequest(BaseModel):
    repo: str
    src_branch: str
    dest_branch: str

class SetImageYamlRequest(BaseModel):
    repo: str
    refs: str
    yaml_path: str
    image: str
    dry_run: bool = False

class PullRequestRequest(BaseModel):
    repo: str
    src_branch: str
    dest_branch: str
    delete_after_merge: bool = False

class MergeRequest(BaseModel):
    pr_url: str
    delete_after_merge: bool = False

class K8sPRRequest(BaseModel):
    cluster: str
    namespace: str
    deploy: str
    image: str
    approve_merge: bool = False
    repo: str = "gitops-k8s"
```

**API Endpoints:**

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/` | `root()` | Welcome page |
| GET | `/health` | `health()` | Health check |
| POST | `/v1/gitops/create-branch` | `api_create_branch()` | Create branch |
| POST | `/v1/gitops/set-image-yaml` | `api_set_image_yaml()` | Update image |
| POST | `/v1/gitops/pull-request` | `api_pull_request()` | Create PR |
| POST | `/v1/gitops/merge` | `api_merge()` | Merge PR |
| POST | `/v1/gitops/k8s-pr` | `api_k8s_pr()` | K8s workflow |

**Server Function:**

```python
def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start FastAPI server with uvicorn."""
    uvicorn.run(app, host=host, port=port)
```

**CORS Configuration:**
- Allow all origins (`*`)
- Allow all methods
- Allow credentials

**Auto Documentation:**
- Swagger UI: `/docs`
- ReDoc: `/redoc`

---

### Step 7: Create CLI Module (`cli.py`)

**Purpose:** Command-line interface using argparse.

**Entry Points (pyproject.toml):**
- `ngen-gitops` → `ngen_gitops.cli:main`
- `gitops` → `ngen_gitops.cli:main`

**Command Structure:**

```
gitops [command] [options]

GitOps Commands:
  create-branch     Create a new branch
  set-image-yaml    Update image in YAML file
  pull-request      Create a pull request
  merge             Merge a pull request
  k8s-pr            Run K8s PR workflow
  server            Start REST API server
  config            Show configuration

Git Commands:
  clone             Clone repository
  pull              Pull changes
  push              Push changes
  fetch             Fetch from remote
  commit            Commit changes
  status            Show git status
```

**Command Handlers:**

```python
def cmd_create_branch(args): ...
def cmd_set_image_yaml(args): ...
def cmd_pull_request(args): ...
def cmd_merge(args): ...
def cmd_k8s_pr(args): ...
def cmd_server(args): ...
def cmd_clone(args): ...
def cmd_pull(args): ...
def cmd_push(args): ...
def cmd_fetch(args): ...
def cmd_commit(args): ...
def cmd_status(args): ...
def cmd_config(args): ...
```

**Common Flags:**
- `--json` - Output as JSON (GitOps commands)
- `--dry-run` - Preview without executing
- `--remote` - Specify remote (bitbucket.org, github.com, gitlab.com)
- `--org` - Specify organization
- `--cwd` - Working directory

**Main Function Pattern:**

```python
def main():
    parser = argparse.ArgumentParser(
        prog="gitops",
        description="GitOps CLI for Bitbucket operations"
    )
    parser.add_argument("--version", action="version", version=__version__)
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add subparsers for each command
    # ...
    
    args = parser.parse_args()
    
    # Route to appropriate handler
    if args.command == "create-branch":
        cmd_create_branch(args)
    # ...
```

---

### Step 8: Package Configuration (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ngen-gitops"
version = "0.1.0"
description = "GitOps CLI and web server for Bitbucket operations"
readme = "README.md"
requires-python = ">=3.7"
license = {text = "MIT"}
authors = [{name = "Your Name"}]
keywords = ["cli", "gitops", "bitbucket", "devops", "api", "ci-cd"]
dependencies = [
    "requests>=2.25.0",
    "fastapi>=0.68.0",
    "uvicorn>=0.15.0",
    "pyyaml>=5.4.0",
    "python-dotenv>=0.19.0",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

[project.scripts]
ngen-gitops = "ngen_gitops.cli:main"
gitops = "ngen_gitops.cli:main"

[project.urls]
Homepage = "https://github.com/your-username/ngen-gitops"
Repository = "https://github.com/your-username/ngen-gitops"

[tool.setuptools.packages.find]
where = ["."]
include = ["ngen_gitops*"]
```

---

### Step 9: Create Package Init (`__init__.py`)

```python
"""ngen-gitops - GitOps CLI and web server for Bitbucket operations."""

__version__ = "0.1.0"
__author__ = "Your Name"
```

---

### Step 10: Build & Test

**Development install:**
```bash
pip install -e .
```

**Test commands:**
```bash
gitops --version
gitops --help
gitops config
gitops server --port 8080
```

**Build package:**
```bash
python -m build
```

**Publish to PyPI:**
```bash
twine upload dist/*
```

---

## 📊 Dependencies Summary

| Package | Version | Purpose |
|---------|---------|---------|
| requests | >=2.25.0 | HTTP client for Bitbucket API |
| fastapi | >=0.68.0 | Web framework for REST API |
| uvicorn | >=0.15.0 | ASGI server |
| pyyaml | >=5.4.0 | YAML parsing |
| python-dotenv | >=0.19.0 | .env file loading |

---

## 🔄 Data Flow

```
CLI/API Request
      ↓
   config.py (load credentials)
      ↓
   ┌─────────────────┐
   │  Operation Type │
   └─────────────────┘
         ↓
   ┌─────────────────────────────────┐
   │ git_wrapper.py   bitbucket.py │
   │ (git commands)   (API calls)  │
   └─────────────────────────────────┘
         ↓
   teams_notify.py (optional notification)
         ↓
   Return JSON response
```

---

## ✅ Implementation Checklist

- [ ] Create project structure
- [ ] Implement `config.py`
- [ ] Implement `git_wrapper.py`
- [ ] Implement `bitbucket.py`
- [ ] Implement `teams_notify.py`
- [ ] Implement `server.py`
- [ ] Implement `cli.py`
- [ ] Configure `pyproject.toml`
- [ ] Create `__init__.py`
- [ ] Write `README.md`
- [ ] Test all commands
- [ ] Build & publish to PyPI

---

## 🎯 Key Design Principles

1. **Modular Design** - Each module has single responsibility
2. **Config Priority** - Environment variables > .env file
3. **Error Handling** - Custom exceptions for better debugging
4. **Dual Interface** - CLI + REST API with same business logic
5. **Multi-Remote Support** - Works with Bitbucket, GitHub, GitLab
6. **Optional Notifications** - Teams webhook is optional feature
7. **Dry Run Support** - Preview changes before executing
8. **JSON Output** - Machine-readable output for automation
