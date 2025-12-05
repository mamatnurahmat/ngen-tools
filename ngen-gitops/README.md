# ngen-gitops

GitOps CLI and web server for Bitbucket operations with general git commands supporting multi-remote workflows. Automate branch creation, YAML image updates, pull request creation, merging, and general git operations via command-line interface or REST API.

[![PyPI version](https://badge.fury.io/py/ngen-gitops.svg)](https://badge.fury.io/py/ngen-gitops)
[![Python](https://img.shields.io/pypi/pyversions/ngen-gitops.svg)](https://pypi.org/project/ngen-gitops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### GitOps Operations (Bitbucket)
- 🌿 **Branch Management**: Create branches from source branches
- 🖼️ **Image Updates**: Update container images in Kubernetes YAML files
- 🔄 **Pull Requests**: Create, list, and merge pull requests automatically
- 📋 **PR List**: List pull requests with status filtering (open, merged, declined)
- 📄 **PR Diff**: View diff/changes for specific pull requests
- 🚀 **K8s Workflow**: Complete K8s GitOps workflow with interactive mode
- 🌐 **Web API**: REST API server with FastAPI for integration

### Git Commands (Multi-Remote)
- 🚀 **Clone**: Clone repositories from Bitbucket, GitHub, or GitLab
- 📥 **Pull/Fetch**: Pull or fetch changes from remote
- 📤 **Push**: Push changes to remote
- 💾 **Commit**: Commit changes with automatic add option
- 📊 **Status**: Check repository status
- 🔀 **Flexible Remotes**: Default to Bitbucket, but works with GitHub and GitLab

### General
- 🔐 **Secure**: Uses app passwords for authentication
- 🔑 **Netrc Support**: Automatically uses `~/.netrc` credentials if available
- 📦 **Easy Configuration**: Simple `.env` config file
- 🚀 **Dual Command**: Use `ngen-gitops` or `gitops` command
- 💻 **PyPI Package**: Install with pip

## Installation

```bash
pip install ngen-gitops
```

Both `ngen-gitops` and `gitops` commands will be available after installation.

## Quick Start

### 1. Configuration

ngen-gitops supports multiple credential sources with the following priority:

1. **Environment variables** (highest priority)
2. **`~/.ngen-gitops/.env` file**
3. **`~/.netrc` file** (automatic fallback)

#### Option A: Using ~/.netrc (Recommended for existing setups)

If you already have a `~/.netrc` file configured for Bitbucket, ngen-gitops will automatically use it:

```bash
# ~/.netrc
machine bitbucket.org
  login your-username
  password your-app-password
```

No additional configuration needed! Just run `gitops config` to verify.

#### Option B: Using ~/.ngen-gitops/.env

On first run, ngen-gitops creates a config file at `~/.ngen-gitops/.env`:

```bash
# ngen-gitops Configuration

# Bitbucket Credentials
BITBUCKET_USER=
BITBUCKET_APP_PASSWORD=
BITBUCKET_ORG=loyaltoid

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Git Settings
GIT_DEFAULT_REMOTE=bitbucket.org
GIT_DEFAULT_ORG=loyaltoid

# Notifications
TEAMS_WEBHOOK=
```

**Update the config with your credentials:**

1. Go to Bitbucket Settings → App passwords
2. Create a new app password with repository read/write permissions
3. Update `~/.ngen-gitops/.env` with your username and app password

#### Option C: Using environment variables

```bash
export BITBUCKET_USER="your-username"
export BITBUCKET_APP_PASSWORD="your-app-password"
export BITBUCKET_ORG="your-organization"
```

**Optional: Configure Teams Webhook for notifications:**

```bash
export TEAMS_WEBHOOK="https://your-org.webhook.office.com/webhookb2/..."
```

Or add it to `~/.ngen-gitops/.env`:

```bash
TEAMS_WEBHOOK="https://your-org.webhook.office.com/webhookb2/..."
```

When configured, you'll receive Microsoft Teams notifications for:
- ✅ Branch creation
- ✅ Image updates
- ✅ Pull request creation
- ✅ Pull request merging

### 2. Verify Configuration

```bash
gitops config
```

**Output:**
```
📋 ngen-gitops Configuration
   Config file: /home/user/.ngen-gitops/.env

Bitbucket:
   Username: your-username
   App Password: ***SET***
   Organization: loyaltoid

Server:
   Host: 0.0.0.0
   Port: 8080

Git:
   Default Remote: bitbucket.org
   Default Org: loyaltoid

Notifications:
   Teams Webhook: ***SET***

✅ Credentials configured
```

## Usage

### Git Commands (Multi-Remote Support)

The `gitops` command provides general git operations with smart remote detection and support for Bitbucket, GitHub, and GitLab.

#### Clone Repository

Clone a repository with single-branch (default) or full clone:

```bash
# Clone single branch from Bitbucket (default)
gitops clone myrepo main

# Clone from GitHub
gitops clone myrepo main --remote github.com

# Clone from GitLab
gitops clone myrepo develop --remote gitlab.com

# Clone all branches (full clone)
gitops clone myrepo main --full

# Clone with custom org
gitops clone myrepo main --org myorg

# Clone with full repo path
gitops clone myorg/myrepo feature/test

# Clone to specific directory
gitops clone myrepo main --destination my-project
```

**Example Output:**
```
🔄 Cloning loyaltoid/myrepo from bitbucket.org...
   Branch/Tag: main
   Mode: Single branch
Cloning into 'myrepo'...
✅ Successfully cloned to myrepo

✅ Repository cloned successfully to: myrepo
```

**Command Options:**
- `repo`: Repository name (e.g., `myrepo` or `org/myrepo`)
- `branch`: Branch or tag to clone (optional)
- `--org`: Organization name (defaults to config)
- `--remote`: Remote type - `bitbucket.org`, `github.com`, `gitlab.com` (defaults to config)
- `--destination, -d`: Destination directory (optional)
- `--full`: Clone all branches instead of single branch (default: single-branch only)

#### Pull Changes

```bash
# Pull current branch
gitops pull

# Pull specific branch
gitops pull develop

# Pull in specific directory
gitops pull --cwd /path/to/repo
```

#### Push Changes

```bash
# Push current branch
gitops push

# Push specific branch
gitops push main

# Force push (use with caution)
gitops push --force

# Push in specific directory
gitops push --cwd /path/to/repo
```

#### Commit Changes

```bash
# Commit with message
gitops commit -m "Update configuration"

# Commit all changes (add + commit)
gitops commit -m "Update files" --all

# Commit in specific directory
gitops commit -m "Fix bug" --cwd /path/to/repo
```

#### Check Status

```bash
# Show status
gitops status

# Show status in specific directory
gitops status --cwd /path/to/repo
```

#### Fetch Changes

```bash
# Fetch from remote
gitops fetch

# Fetch in specific directory
gitops fetch --cwd /path/to/repo
```

### GitOps Commands (Bitbucket Operations)

#### Create Branch

Create a new branch from a source branch:

```bash
gitops create-branch <repo> <src_branch> <dest_branch>
```

**Example:**
```bash
gitops create-branch my-app main feature/new-feature
```

**Output:**
```
🔍 Creating branch 'feature/new-feature' from 'main' in repository 'my-app'...
✅ Source branch 'main' validated (commit: abc1234)
✅ Branch 'feature/new-feature' created successfully from 'main'

✅ Branch 'feature/new-feature' created successfully
   Branch URL: https://bitbucket.org/org/my-app/branch/feature/new-feature
```

#### Update Image in YAML

Update container image in Kubernetes YAML file:

```bash
gitops set-image-yaml <repo> <branch> <yaml_path> <image> [--dry-run]
```

**Example:**
```bash
gitops set-image-yaml my-app develop k8s/deployment.yaml myregistry/myapp:v1.2.3
```

**Output:**
```
🔍 Cloning repository my-app (branch: develop)...
✅ Repository cloned
   Current image(s): myregistry/myapp:v1.2.0
   New image: myregistry/myapp:v1.2.3
✅ Updated image in YAML file
✅ Changes committed
✅ Changes pushed to develop

✅ Image updated to myregistry/myapp:v1.2.3 and pushed to develop
   [develop abc1234] chore: update image to myregistry/myapp:v1.2.3
```

**Dry-run mode** (don't push changes):
```bash
gitops set-image-yaml my-app develop k8s/deployment.yaml myapp:v1.0.0 --dry-run
```

#### Create Pull Request

Create a pull request from source to destination branch:

```bash
gitops pull-request <repo> <src_branch> <dest_branch> [--delete-after-merge]
```

**Example:**
```bash
gitops pull-request my-app feature/new-feature develop --delete-after-merge
```

**Output:**
```
🔍 Creating pull request from 'feature/new-feature' to 'develop' in repository 'my-app'...
   ⚠️  Source branch 'feature/new-feature' will be deleted after merge
✅ Source branch 'feature/new-feature' validated
✅ Destination branch 'develop' validated
✅ Pull request created successfully
   PR #42
   URL: https://bitbucket.org/org/my-app/pull-requests/42

✅ Pull request #42 created successfully
   Pull Request URL: https://bitbucket.org/org/my-app/pull-requests/42
```

#### Merge Pull Request

Merge an existing pull request:

```bash
gitops merge <pr_url> [--delete-after-merge]
```

**Example:**
```bash
gitops merge https://bitbucket.org/org/my-app/pull-requests/42
```

**Output:**
```
🔍 Merging pull request #42 in repository 'my-app'...
✅ Pull request validated
   Source branch: feature/new-feature
   Destination branch: develop
   State: OPEN
✅ Pull request #42 merged successfully
   Merge commit: abc1234

✅ Pull request #42 merged successfully
   Merge commit: abc1234
```

#### List Pull Requests

List pull requests in a repository with status filtering:

```bash
gitops pr <repo> [--status STATUS]
```

**Status options:**
- `open` (default)
- `merged`
- `declined`
- `draft`

**Examples:**
```bash
# List open PRs (default)
gitops pr my-app

# List merged PRs
gitops pr my-app --status merged

# List declined PRs
gitops pr my-app --status declined

# JSON output
gitops pr my-app --json
```

**Output:**
```
📋 Pull Requests in my-app (status: open)

  #ID    | Source Branch                            | Destination                              | Author                                   | Created                                 
  -------+------------------------------------------+------------------------------------------+------------------------------------------+-----------------------------------------
  #123   | feature/login                            | develop                                  | John Doe                                 | 2024-12-01                              
  #124   | fix/bug-456                              | main                                     | Jane Smith                               | 2024-12-02                              

Total: 2 pull request(s)
```

#### View Pull Request Diff

View the diff/changes for a specific pull request:

```bash
gitops pr <repo> --diff <PR_ID>
```

**Example:**
```bash
gitops pr my-app --diff 123
```

**Output:**
```
📄 Pull Request #123 Diff in my-app
================================================================================
diff --git a/src/app.py b/src/app.py
index abc1234..def5678 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,7 @@ def main():
-    print("Hello World")
+    print("Hello, GitOps!")
...
```

```

#### View Commit Logs

View commit history for a repository:

```bash
# Show last 10 commits (oneline)
gitops logs myrepo main

# Show last 20 commits
gitops logs myrepo develop -n 20

# Show only the last commit
gitops logs myrepo main --last

# Show detailed info for a specific commit
gitops logs myrepo main --detail abc1234

# JSON output
gitops logs myrepo main --json
```

#### Get File Content

Retrieve file content from a repository:

```bash
# Print file content to stdout
gitops get-file myrepo main README.md

# Save file to disk
gitops get-file myrepo develop config.yaml -o local_config.yaml

# Get binary file (base64 encoded in JSON)
gitops get-file myrepo main logo.png --json
```

#### Create Tag

Create a tag on a specific commit:

```bash
gitops tag <repo> <branch> <commit_id> <tag_name>
```

**Example:**
```bash
gitops tag my-app main abc1234 v1.0.0
```

**Output:**
```
🔍 Creating tag 'v1.0.0' on commit 'abc1234' in repository 'my-app'...
✅ Branch 'main' validated
✅ Commit 'abc1234' validated
✅ Tag 'v1.0.0' created successfully on commit abc1234

✅ Tag 'v1.0.0' created on commit abc1234
   Tag URL: https://bitbucket.org/org/my-app/src/v1.0.0
   Commit: abc1234
```

#### Manage Webhooks

Manage webhooks in a repository:

```bash
# Create webhook
gitops webhook <repo> <webhook_url>

# Delete webhook
gitops webhook <repo> <webhook_url> --delete
```

**Example:**
```bash
gitops webhook my-app https://webhook.example.com/trigger
```

**Output:**
```
🔍 Creating webhook in repository 'my-app'...
   URL: https://webhook.example.com/trigger
✅ Webhook created successfully
   UUID: {uuid-string}
   Events: repo:push, pullrequest:created, pullrequest:updated, pullrequest:fulfilled

✅ Webhook created successfully
   UUID: {uuid-string}
   Events: repo:push, pullrequest:created, pullrequest:updated, pullrequest:fulfilled
```

#### Kubernetes PR Workflow (Interactive Mode)

Run a complete GitOps workflow: Create Branch -> Update Image -> Create PR -> Merge (optional).

**Interactive Mode** - Run without arguments to be prompted:

```bash
gitops k8s-pr
```

The command will interactively prompt for:
- 🔧 Cluster (source branch)
- 🔧 Kubernetes namespace
- 🔧 Deployment name
- 🔧 New image tag
- ❓ Auto-merge the PR? [y/N]

**Non-Interactive Mode** - Provide all arguments:

```bash
gitops k8s-pr <cluster> <namespace> <deploy> <image> [--approve-merge] [--repo REPO]
```

**Arguments:**
- `cluster`: Source branch (e.g., cluster name like `k8s-cluster-1`)
- `namespace`: Kubernetes namespace
- `deploy`: Deployment name
- `image`: New image tag
- `--approve-merge`: Automatically merge the PR (skip confirmation prompt)
- `--repo`: Repository name (default: `gitops-k8s`)

**Examples:**
```bash
# Interactive mode
gitops k8s-pr

# Non-interactive with auto-merge
gitops k8s-pr main my-ns my-app myregistry/app:v2 --approve-merge

# Non-interactive without auto-merge (will prompt)
gitops k8s-pr main my-ns my-app myregistry/app:v2

# Custom repository
gitops k8s-pr main my-ns my-app myregistry/app:v2 --repo my-gitops-repo
```

**Workflow Steps:**
1. Creates branch `my-ns/my-app_deployment.yaml` from `main`
2. Updates image in `my-ns/my-app_deployment.yaml` file
3. Creates PR from new branch to `main`
4. Merges PR (if `--approve-merge` is set)

#### Start Web Server

Start the REST API server:

```bash
gitops server [--host HOST] [--port PORT]
```

**Example:**
```bash
gitops server --port 8080
```

**Output:**
```
🚀 Starting ngen-gitops server...
   Host: 0.0.0.0
   Port: 8080
   Endpoints:
     - POST /v1/gitops/create-branch
     - POST /v1/gitops/set-image-yaml
     - POST /v1/gitops/pull-request
     - POST /v1/gitops/merge

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### JSON Output

GitOps commands support `--json` flag for machine-readable output:

```bash
gitops create-branch my-app main develop --json
```

**Output:**
```json
{
  "success": true,
  "repository": "my-app",
  "source_branch": "main",
  "destination_branch": "develop",
  "message": "Branch 'develop' created successfully",
  "branch_url": "https://bitbucket.org/org/my-app/branch/develop"
}
```

## REST API

### Starting the Server

```bash
gitops server --port 8080
```

### API Endpoints

#### 1. Create Branch

**Endpoint:** `POST /v1/gitops/create-branch`

**Request:**
```json
{
  "repo": "my-app",
  "src_branch": "main",
  "dest_branch": "feature/new-feature"
}
```

**Response:**
```json
{
  "success": true,
  "repository": "my-app",
  "source_branch": "main",
  "destination_branch": "feature/new-feature",
  "message": "Branch 'feature/new-feature' created successfully",
  "branch_url": "https://bitbucket.org/org/my-app/branch/feature/new-feature"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/v1/gitops/create-branch \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "my-app",
    "src_branch": "main",
    "dest_branch": "feature/new-feature"
  }'
```

#### 2. Update Image in YAML

**Endpoint:** `POST /v1/gitops/set-image-yaml`

**Request:**
```json
{
  "repo": "my-app",
  "refs": "develop",
  "yaml_path": "k8s/deployment.yaml",
  "image": "myregistry/myapp:v1.2.3",
  "dry_run": false
}
```

**Response:**
```json
{
  "success": true,
  "repository": "my-app",
  "branch": "develop",
  "yaml_path": "k8s/deployment.yaml",
  "image": "myregistry/myapp:v1.2.3",
  "message": "Image updated to myregistry/myapp:v1.2.3 and pushed to develop",
  "commit": "[develop abc1234] chore: update image to myregistry/myapp:v1.2.3"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/v1/gitops/set-image-yaml \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "my-app",
    "refs": "develop",
    "yaml_path": "k8s/deployment.yaml",
    "image": "myregistry/myapp:v1.2.3",
    "dry_run": false
  }'
```

#### 3. Create Pull Request

**Endpoint:** `POST /v1/gitops/pull-request`

**Request:**
```json
{
  "repo": "my-app",
  "src_branch": "feature/new-feature",
  "dest_branch": "develop",
  "delete_after_merge": false
}
```

**Response:**
```json
{
  "success": true,
  "repository": "my-app",
  "source": "feature/new-feature",
  "destination": "develop",
  "delete_after_merge": false,
  "pr_id": 42,
  "pr_url": "https://bitbucket.org/org/my-app/pull-requests/42",
  "message": "Pull request #42 created successfully"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/v1/gitops/pull-request \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "my-app",
    "src_branch": "feature/new-feature",
    "dest_branch": "develop",
    "delete_after_merge": false
  }'
```

#### 4. Merge Pull Request

**Endpoint:** `POST /v1/gitops/merge`

**Request:**
```json
{
  "pr_url": "https://bitbucket.org/org/my-app/pull-requests/42",
  "delete_after_merge": false
}
```

**Response:**
```json
{
  "success": true,
  "pr_url": "https://bitbucket.org/org/my-app/pull-requests/42",
  "repository": "my-app",
  "pr_id": "42",
  "source": "feature/new-feature",
  "destination": "develop",
  "message": "Pull request #42 merged successfully",
  "merge_commit": "abc1234",
  "delete_after_merge": false
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/v1/gitops/merge \
  -H "Content-Type: application/json" \
  -d '{
    "pr_url": "https://bitbucket.org/org/my-app/pull-requests/42",
    "delete_after_merge": false
  }'
```

#### 5. Kubernetes PR Workflow

**Endpoint:** `POST /v1/gitops/k8s-pr`

**Request:**
```json
{
  "cluster": "main",
  "namespace": "my-ns",
  "deploy": "my-app",
  "image": "myregistry/app:v2",
  "approve_merge": true,
  "repo": "gitops-k8s"
}
```

**Response:**
```json
{
  "success": true,
  "steps": [
    {"name": "create_branch", "result": {...}},
    {"name": "set_image", "result": {...}},
    {"name": "create_pr", "result": {...}},
    {"name": "merge_pr", "result": {...}}
  ],
  "pr_url": "https://bitbucket.org/...",
  "message": "Workflow completed successfully (merged)"
}
```

### API Documentation

When the server is running, visit:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

## Use Cases

### Multi-Remote Git Workflow

**Clone from different remotes:**

```bash
# Clone from Bitbucket (default)
gitops clone my-app main

# Clone from GitHub
gitops clone my-company/app main --remote github.com

# Clone from GitLab
gitops clone group/project develop --remote gitlab.com
```

**Work with cloned repo:**

```bash
# Make changes
cd my-app
echo "update" >> README.md

# Commit and push
gitops commit -m "Update README" --all
gitops push
```

### CI/CD Integration

**Update image after Docker build:**

```bash
# Build Docker image
docker build -t myregistry/myapp:${VERSION} .
docker push myregistry/myapp:${VERSION}

# Update Kubernetes deployment
gitops set-image-yaml my-app develop k8s/deployment.yaml myregistry/myapp:${VERSION}
```

**Automated PR workflow:**

```bash
# Create feature branch
gitops create-branch my-app develop feature/auto-update-${VERSION}

# Update image in feature branch
gitops set-image-yaml my-app feature/auto-update-${VERSION} k8s/deployment.yaml myregistry/myapp:${VERSION}

# Create pull request
PR_URL=$(gitops pull-request my-app feature/auto-update-${VERSION} develop --delete-after-merge --json | jq -r '.pr_url')

# Auto-merge (optional)
gitops merge $PR_URL
```

### REST API Integration

**Python example:**

```python
import requests

# Create branch
response = requests.post('http://localhost:8080/v1/gitops/create-branch', json={
    'repo': 'my-app',
    'src_branch': 'main',
    'dest_branch': 'feature/new-feature'
})
print(response.json())

# Update image
response = requests.post('http://localhost:8080/v1/gitops/set-image-yaml', json={
    'repo': 'my-app',
    'refs': 'develop',
    'yaml_path': 'k8s/deployment.yaml',
    'image': 'myapp:v1.0.0',
    'dry_run': False
})
print(response.json())
```

## Configuration

### Config File Location

### Config File Location

`~/.ngen-gitops/.env`

### Config Structure

The configuration uses standard environment variable format (key=value).

```bash
# Bitbucket
BITBUCKET_USER=your-username
BITBUCKET_APP_PASSWORD=your-app-password
BITBUCKET_ORG=your-org

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# Git
GIT_DEFAULT_REMOTE=bitbucket.org
GIT_DEFAULT_ORG=your-org

# Notifications
TEAMS_WEBHOOK=https://your-org.webhook.office.com/webhookb2/...
```

### Configuration Options

#### Bitbucket Settings
- `BITBUCKET_USER`: Your Bitbucket username
- `BITBUCKET_APP_PASSWORD`: Bitbucket app password
- `BITBUCKET_ORG`: Default organization

#### Server Settings
- `SERVER_HOST`: Server bind address
- `SERVER_PORT`: Server port

#### Git Settings
- `GIT_DEFAULT_REMOTE`: Default git remote
- `GIT_DEFAULT_ORG`: Default organization/user

#### Notifications Settings
- `TEAMS_WEBHOOK`: Microsoft Teams webhook URL

### Environment Variables

Override config with environment variables:

- `BITBUCKET_USER`: Bitbucket username
- `BITBUCKET_APP_PASSWORD`: Bitbucket app password
- `BITBUCKET_ORG`: Bitbucket organization
- `TEAMS_WEBHOOK`: Microsoft Teams webhook URL for notifications

## Command Reference

### GitOps Commands

| Command | Description |
|---------|-------------|
| `gitops create-branch` | Create a new branch from source branch |
| `gitops set-image-yaml` | Update image in YAML file |
| `gitops pull-request` | Create a pull request |
| `gitops merge` | Merge a pull request |
| `gitops k8s-pr` | Run complete K8s GitOps workflow |
| `gitops server` | Start REST API server |
| `gitops config` | Show configuration |

### Git Commands

| Command | Description |
|---------|-------------|
| `gitops clone` | Clone repository with multi-remote support |
| `gitops pull` | Pull changes from remote |
| `gitops push` | Push changes to remote |
| `gitops fetch` | Fetch from remote |
| `gitops commit` | Commit changes |
| `gitops status` | Show git status |

### Common Flags

- `--json`: Output as JSON (GitOps commands)
- `--dry-run`: Preview changes without executing
- `--remote`: Specify git remote (bitbucket.org, github.com, gitlab.com)
- `--org`: Specify organization
- `--full`: Clone all branches (instead of single-branch)
- `--force, -f`: Force operation
- `--all, -a`: Include all changes

## Development

### Build from Source

```bash
# Clone repository
git clone https://github.com/mamatnurahmat/ngen-gitops.git
cd ngen-gitops

# Install in development mode
pip install -e .

# Run commands
gitops --help
```

### Build Package

```bash
# Use the build script
./build.sh

# Or use the build script with options
./build.sh --build-only    # Build only, don't publish
./build.sh --release        # Build and publish to PyPI
```

### Publish to PyPI

```bash
# Update version in pyproject.toml and ngen_gitops/__init__.py

# Build and publish
./build.sh --release
```

## Troubleshooting

### Authentication Errors

**Problem:** `Bitbucket credentials not configured`

**Solution:**
1. Check config file exists: `~/.ngen-gitops/.env`
2. Verify credentials are set correctly
3. Or set environment variables: `BITBUCKET_USER` and `BITBUCKET_APP_PASSWORD`

### Branch Not Found

**Problem:** `Source branch 'xyz' not found`

**Solution:**
1. Verify branch name is correct (case-sensitive)
2. Check branch exists in Bitbucket repository
3. Use `gitops status` to check current branch

### Git Clone Fails

**Problem:** `git command not found` or authentication fails

**Solution:**
1. Ensure git is installed: `git --version`
2. For private repos, ensure credentials are configured
3. Check remote is correct: `bitbucket.org`, `github.com`, or `gitlab.com`

### Image Update Fails

**Problem:** `File 'k8s/deployment.yaml' not found`

**Solution:**
1. Verify YAML path is correct relative to repository root
2. Check file exists in the specified branch
3. Ensure YAML file contains `image:` field

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

ngen-gitops contributors

## Related Projects

- [ngen-j](https://github.com/mamatnurahmat/ngen-j) - Jenkins API management CLI

## Links

- **GitHub**: https://github.com/mamatnurahmat/ngen-gitops
- **PyPI**: https://pypi.org/project/ngen-gitops/
- **Issues**: https://github.com/mamatnurahmat/ngen-gitops/issues
