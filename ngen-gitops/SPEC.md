# Project Specification: ngen-gitops

## Overview
`ngen-gitops` is a versatile GitOps automation tool designed to streamline development workflows. It provides both a Command Line Interface (CLI) and a FastAPI-based REST API server. Its primary functions include managing git branches, creating and merging pull requests, updating image tags in YAML configuration files, and integrating with Bitbucket and Microsoft Teams for notifications.

## Architecture

### Directory Structure
```
ngen-gitops/
├── ngen_gitops/           # Main package directory
│   ├── __init__.py        # Package initialization (version info)
│   ├── cli.py             # CLI entry point (argparse)
│   ├── server.py          # FastAPI web server implementation
│   ├── config.py          # Configuration and environment management
│   ├── headers.py         # Bitbucket API headers management
│   ├── bitbucket.py       # Bitbucket API interaction layer
│   ├── git_wrapper.py     # Wrapper for local git operations
│   └── teams_notify.py    # Microsoft Teams notification logic
├── setup.py               # Package installation configuration
├── README.md              # User documentation
└── SPEC.md                # This specification file
```

### Core Modules

#### 1. CLI (`cli.py`)
The `cli.py` module is the entry point for the command-line tool. It uses `argparse` to define and handle various commands.
*   **Commands**:
    *   `clone`: Wrapper for `git clone`.
    *   `create-branch`: Creates a new branch via Bitbucket API.
    *   `pull-request`: Creates a pull request.
    *   `merge`: Merges an existing pull request.
    *   `set-image-yaml`: Updates image tags in Kubernetes YAML manifests.
    *   `server`: Starts the REST API server.
    *   `webhook`: Manages Bitbucket webhooks.
    *   `k8s-pr`: specialized workflow for K8s manifest updates.
    *   Git passthrough: `pull`, `push`, `fetch`, `commit`, `status`, `logs`.

#### 2. Server (`server.py`)
A FastAPI application that exposes key GitOps functionalities via HTTP endpoints. This allows other tools or CI/CD pipelines to trigger GitOps actions remotely.
*   **Endpoints**:
    *   `POST /api/v1/branch`: Create a branch.
    *   `POST /api/v1/image`: Update image in YAML.
    *   `POST /api/v1/pr`: Create a pull request.
    *   `POST /api/v1/merge`: Merge a pull request.
    *   `GET /health`: Health check.

#### 3. Configuration (`config.py`)
Manages application settings using a hierarchical approach:
1.  **Environment Variables**: Highest priority (e.g., `BITBUCKET_USER`).
2.  **.env File**: Located at `~/.ngen-gitops/.env`.
3.  **Defaults**: Hardcoded fallbacks (e.g., default organization `loyaltoid`).

It also handles credential retrieval from `.netrc` for Bitbucket authentication.

#### 4. Bitbucket Integration (`bitbucket.py`)
Encapsulates all logic for interacting with the Bitbucket Cloud API v2.
*   Handles authentication using App Passwords.
*   Manages PRs, branches, and repository queries.

#### 5. Git Wrapper (`git_wrapper.py`)
Provides a Pythonic interface for executing local `git` commands using `subprocess`. It handles URL construction for different providers (Bitbucket, GitHub, GitLab).

## Configuration Guide

The application expects a configuration file at `~/.ngen-gitops/.env`. If it doesn't exist, it is auto-created with reference comments.

**Key Variables:**
*   `BITBUCKET_USER`: Bitbucket username.
*   `BITBUCKET_APP_PASSWORD`: App password with write permissions.
*   `BITBUCKET_ORG`: Default organization/workspace (default: `loyaltoid`).
*   `TEAMS_WEBHOOK`: URL for Microsoft Teams notifications.
*   `GIT_DEFAULT_REMOTE`: Default remote host (default: `bitbucket.org`).

## Cloning & Adaptation Guide

To adapt this project for a similar use case (e.g., `project-x-gitops`):

1.  **Rename Package**:
    *   Rename the `ngen_gitops` directory to `project_x_gitops`.
    *   Update `setup.py`: Change `name`, `packages`, and `package_dir`.
    *   Update imports in all `.py` files (find/replace `ngen_gitops` with `project_x_gitops`).

2.  **Update Configuration Defaults**:
    *   Modify `ngen_gitops/config.py`:
        *   Update `CONFIG_DIR` (e.g., `~/.project-x-gitops`).
        *   Change default values for organizations/registries in `load_config` and `create_default_env`.

3.  **Custom Logic**:
    *   If your workflow differs (e.g., using GitHub instead of Bitbucket), refactor `bitbucket.py` to target the GitHub API or create a new `github.py` module.
    *   Adjust `cli.py` commands to match your specific requirements.

4.  **Install**:
    ```bash
    pip install -e .
    ```

5.  **Verify**:
    Run `project-x-gitops config` (or your new CLI name) to generate the initial environment file and verify settings.
