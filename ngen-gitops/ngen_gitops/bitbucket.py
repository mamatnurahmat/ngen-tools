"""Bitbucket API integration for GitOps operations."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
import yaml

from .config import get_bitbucket_credentials
from .teams_notify import (
    notify_branch_created,
    notify_image_updated,
    notify_pr_created,
    notify_pr_merged
)


BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0/repositories"


class GitOpsError(Exception):
    """Base exception for GitOps operations."""
    pass


def list_pull_requests(
    repo: str,
    status: str = "open",
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None
) -> Dict[str, Any]:
    """List pull requests in a Bitbucket repository.
    
    Args:
        repo: Repository name
        status: PR status filter (open, merged, declined, draft)
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
    
    Returns:
        dict: Result with list of PRs
    
    Raises:
        GitOpsError: If API request fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    # Map status to Bitbucket API state
    status_map = {
        'open': 'OPEN',
        'merged': 'MERGED',
        'declined': 'DECLINED',
        'draft': 'OPEN'  # Draft PRs are OPEN with draft flag
    }
    
    api_state = status_map.get(status.lower(), 'OPEN')
    
    result = {
        'success': False,
        'repository': repo,
        'status': status,
        'count': 0,
        'pull_requests': [],
        'message': ''
    }
    
    try:
        # Fetch pull requests from API
        pr_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/pullrequests?state={api_state}"
        
        resp = requests.get(pr_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Repository '{repo}' not found")
        
        resp.raise_for_status()
        data = resp.json()
        
        prs = []
        for pr in data.get('values', []):
            pr_data = {
                'id': pr.get('id'),
                'title': pr.get('title', ''),
                'source': pr.get('source', {}).get('branch', {}).get('name', ''),
                'destination': pr.get('destination', {}).get('branch', {}).get('name', ''),
                'author': pr.get('author', {}).get('display_name', 'unknown'),
                'state': pr.get('state', ''),
                'created_on': pr.get('created_on', '')[:10] if pr.get('created_on') else '',
                'url': pr.get('links', {}).get('html', {}).get('href', '')
            }
            
            # Filter draft if requested
            if status.lower() == 'draft':
                # Bitbucket doesn't have native draft support in Cloud
                # For now, include all OPEN PRs when draft is requested
                pass
            
            prs.append(pr_data)
        
        result['success'] = True
        result['count'] = len(prs)
        result['pull_requests'] = prs
        result['message'] = f"Found {len(prs)} pull request(s)"
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise


def get_pull_request_diff(
    repo: str,
    pr_id: int,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None
) -> Dict[str, Any]:
    """Get diff for a specific pull request.
    
    Args:
        repo: Repository name
        pr_id: Pull request ID
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
    
    Returns:
        dict: Result with PR diff content
    
    Raises:
        GitOpsError: If API request fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'pr_id': pr_id,
        'diff': '',
        'message': ''
    }
    
    try:
        # Fetch diff from API
        diff_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/pullrequests/{pr_id}/diff"
        
        resp = requests.get(diff_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Pull request #{pr_id} not found in repository '{repo}'")
        
        resp.raise_for_status()
        
        result['success'] = True
        result['diff'] = resp.text
        result['message'] = f"Retrieved diff for PR #{pr_id}"
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise


def create_branch(
    repo: str,
    src_branch: str,
    dest_branch: str,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new branch in Bitbucket repository from source branch.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        username: Bitbucket username (optional, reads from config if not provided)
        app_password: Bitbucket app password (optional, reads from config if not provided)
        org: Bitbucket organization (optional, reads from config if not provided)
    
    Returns:
        dict: Result with success status and details
    
    Raises:
        GitOpsError: If branch creation fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'source_branch': src_branch,
        'destination_branch': dest_branch,
        'message': ''
    }
    
    try:
        print(f"🔍 Creating branch '{dest_branch}' from '{src_branch}' in repository '{repo}'...")
        
        # Step 1: Validate source branch exists and get commit hash
        src_branch_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches/{src_branch}"
        
        resp = requests.get(src_branch_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Source branch '{src_branch}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        src_data = resp.json()
        
        commit_hash = src_data.get('target', {}).get('hash')
        if not commit_hash:
            raise GitOpsError(f"Could not get commit hash from source branch '{src_branch}'")
        
        print(f"✅ Source branch '{src_branch}' validated (commit: {commit_hash[:7]})")
        
        # Step 2: Check if destination branch already exists
        dest_branch_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches/{dest_branch}"
        
        check_resp = requests.get(dest_branch_url, auth=(username, app_password), timeout=30)
        
        if check_resp.status_code == 200:
            print(f"ℹ️  Branch '{dest_branch}' already exists")
            result['success'] = True
            result['message'] = f"Branch '{dest_branch}' already exists"
            result['branch_url'] = f"https://bitbucket.org/{org}/{repo}/branch/{dest_branch}"
            return result
        
        # Step 3: Create new branch
        create_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches"
        
        payload = {
            "name": dest_branch,
            "target": {
                "hash": commit_hash
            }
        }
        
        create_resp = requests.post(
            create_url,
            auth=(username, app_password),
            json=payload,
            timeout=30
        )
        
        if create_resp.status_code == 409:
            print(f"ℹ️  Branch '{dest_branch}' already exists")
            result['success'] = True
            result['message'] = f"Branch '{dest_branch}' already exists"
            result['branch_url'] = f"https://bitbucket.org/{org}/{repo}/branch/{dest_branch}"
            return result
        
        create_resp.raise_for_status()
        
        print(f"✅ Branch '{dest_branch}' created successfully from '{src_branch}'")
        result['success'] = True
        result['message'] = f"Branch '{dest_branch}' created successfully"
        result['branch_url'] = f"https://bitbucket.org/{org}/{repo}/branch/{dest_branch}"
        
        # Send Teams notification
        notify_branch_created(repo, src_branch, dest_branch, result['branch_url'], user=user)
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise GitOpsError(str(e)) from e


def _extract_yaml_image(data: Any) -> List[str]:
    """Recursively extract all image fields from YAML structure."""
    images = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'image' and isinstance(value, str):
                images.append(value)
            else:
                images.extend(_extract_yaml_image(value))
    elif isinstance(data, list):
        for item in data:
            images.extend(_extract_yaml_image(item))
    return images


def _update_yaml_image(data: Any, new_image: str) -> bool:
    """Recursively update image fields in YAML structure."""
    updated = False
    
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'image' and isinstance(value, str):
                data[key] = new_image
                updated = True
            else:
                updated = _update_yaml_image(value, new_image) or updated
    elif isinstance(data, list):
        for item in data:
            updated = _update_yaml_image(item, new_image) or updated
    return updated


def set_image_in_yaml(
    repo: str,
    refs: str,
    yaml_path: str,
    image: str,
    dry_run: bool = False,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Update image reference inside YAML file in Bitbucket repo.
    
    Args:
        repo: Repository name
        refs: Branch/tag reference
        yaml_path: Path to YAML file in repository
        image: New image to set
        dry_run: If True, don't push changes
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
    
    Returns:
        dict: Result with success status and details
    
    Raises:
        GitOpsError: If image update operation fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'branch': refs,
        'yaml_path': yaml_path,
        'image': image,
        'message': ''
    }
    
    base_tmp = Path(tempfile.gettempdir()) / 'ngen-gitops-set-image'
    repo_dir = base_tmp / repo
    
    email = f"{username}@users.noreply.bitbucket.org"
    os.environ.setdefault('GIT_ASKPASS', 'true')  # avoid interactive prompts
    
    clone_url = (
        f"https://{quote(username, safe='')}:{quote(app_password, safe='')}"
        f"@bitbucket.org/{org}/{repo}.git"
    )
    
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        print(f"🔍 Cloning repository {repo} (branch: {refs})...")
        
        clone = subprocess.run(
            ['git', 'clone', '--single-branch', '--branch', refs, clone_url, str(repo_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if clone.returncode != 0:
            raise GitOpsError(f"Git clone failed: {clone.stderr.strip()}")
        
        print(f"✅ Repository cloned")
        
        target_file = repo_dir / yaml_path
        if not target_file.exists():
            raise GitOpsError(f"File '{yaml_path}' not found in repository")
        
        # Read and parse YAML
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise GitOpsError(f"Failed to parse YAML: {exc}")
        
        if data is None:
            raise GitOpsError("YAML file is empty or invalid")
        
        # Check current images
        current_images = _extract_yaml_image(data)
        if current_images:
            print(f"   Current image(s): {', '.join(current_images)}")
            print(f"   New image: {image}")
            
            # Check if image is already set
            if image in current_images:
                result['success'] = True
                result['message'] = f"Image already up-to-date: {image}"
                result['skipped'] = True
                print(f"✅ Image already up-to-date")
                return result
        
        # Update image
        if not _update_yaml_image(data, image):
            raise GitOpsError(f"No 'image' field found to update in {yaml_path}")
        
        # Write updated YAML
        with open(target_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        
        print(f"✅ Updated image in YAML file")
        
        if dry_run:
            result['success'] = True
            result['message'] = 'Changes prepared (dry-run). No commit/push performed.'
            print("ℹ️  Dry-run mode: no commit/push")
            return result
        
        # Git config
        subprocess.run(['git', 'config', 'user.name', username], cwd=repo_dir, check=False)
        subprocess.run(['git', 'config', 'user.email', email], cwd=repo_dir, check=False)
        
        # Check for changes
        diff = subprocess.run(['git', 'status', '--porcelain'], cwd=repo_dir, capture_output=True, text=True)
        if not diff.stdout.strip():
            result['success'] = True
            result['message'] = 'No changes to commit'
            return result
        
        # Stage, commit, and push
        subprocess.run(['git', 'add', yaml_path], cwd=repo_dir, check=True)
        
        commit_msg = f"chore: update image to {image}"
        commit = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_dir, capture_output=True, text=True)
        if commit.returncode != 0:
            raise GitOpsError(f"Failed to commit changes: {commit.stderr.strip()}")
        
        print(f"✅ Changes committed")
        
        push = subprocess.run(['git', 'push', 'origin', f"HEAD:{refs}"], cwd=repo_dir, capture_output=True, text=True)
        if push.returncode != 0:
            raise GitOpsError(f"Failed to push to origin: {push.stderr.strip()}")
        
        print(f"✅ Changes pushed to {refs}")
        
        result['success'] = True
        result['message'] = f"Image updated to {image} and pushed to {refs}"
        result['commit'] = commit.stdout.strip()
        
        # Send Teams notification
        notify_image_updated(repo, refs, yaml_path, image, commit.stdout.strip(), user=user)
        
        return result
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Git operation failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise
    finally:
        # Cleanup cloned repository
        if repo_dir.exists():
            shutil.rmtree(repo_dir)


def create_pull_request(
    repo: str,
    src_branch: str,
    dest_branch: str,
    delete_after_merge: bool = False,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a pull request in Bitbucket repository.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        delete_after_merge: Whether to delete source branch after merge
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
    
    Returns:
        dict: Result with success status and PR details
    
    Raises:
        GitOpsError: If PR creation fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'source': src_branch,
        'destination': dest_branch,
        'delete_after_merge': delete_after_merge,
        'pr_url': '',
        'message': ''
    }
    
    try:
        print(f"🔍 Creating pull request from '{src_branch}' to '{dest_branch}' in repository '{repo}'...")
        if delete_after_merge:
            print(f"   ⚠️  Source branch '{src_branch}' will be deleted after merge")
        
        # Step 1: Validate source branch exists
        src_branch_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches/{src_branch}"
        
        resp = requests.get(src_branch_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Source branch '{src_branch}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        print(f"✅ Source branch '{src_branch}' validated")
        
        # Step 2: Validate destination branch exists
        dest_branch_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches/{dest_branch}"
        
        resp = requests.get(dest_branch_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Destination branch '{dest_branch}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        print(f"✅ Destination branch '{dest_branch}' validated")
        
        # Step 3: Create pull request
        pr_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/pullrequests"
        
        pr_payload = {
            "title": f"Merge {src_branch} into {dest_branch}",
            "description": f"Auto-generated pull request from ngen-gitops",
            "source": {
                "branch": {
                    "name": src_branch
                }
            },
            "destination": {
                "branch": {
                    "name": dest_branch
                }
            },
            "close_source_branch": delete_after_merge
        }
        
        pr_resp = requests.post(
            pr_url,
            auth=(username, app_password),
            json=pr_payload,
            timeout=30
        )
        
        if pr_resp.status_code == 400:
            error_data = pr_resp.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            if 'already exists' in error_msg.lower():
                raise GitOpsError(f"Pull request already exists for {src_branch} -> {dest_branch}")
            raise GitOpsError(f"Failed to create pull request: {error_msg}")
        
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        
        pr_id = pr_data.get('id')
        web_url = pr_data.get('links', {}).get('html', {}).get('href', '')
        
        print(f"✅ Pull request created successfully")
        print(f"   PR #{pr_id}")
        print(f"   URL: {web_url}")
        
        result['success'] = True
        result['pr_id'] = pr_id
        result['pr_url'] = web_url
        result['message'] = f"Pull request #{pr_id} created successfully"
        
        # Send Teams notification
        notify_pr_created(repo, src_branch, dest_branch, pr_id, web_url, user=user)
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise


def merge_pull_request(
    pr_url: str,
    delete_after_merge: bool = False,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Merge a pull request from Bitbucket PR URL.
    
    Args:
        pr_url: Pull request URL (e.g., https://bitbucket.org/org/repo/pull-requests/123)
        delete_after_merge: Whether to delete source branch after merge
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
    
    Returns:
        dict: Result with success status and merge details
    
    Raises:
        GitOpsError: If merge operation fails
    """
    # Get credentials
    if not username or not app_password:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = creds['organization']
    
    result = {
        'success': False,
        'pr_url': pr_url,
        'repository': '',
        'pr_id': '',
        'source': '',
        'destination': '',
        'message': '',
        'delete_after_merge': delete_after_merge
    }
    
    try:
        # Parse PR URL
        url_pattern = r'https?://bitbucket\.org/([^/]+)/([^/]+)/pull-requests/(\d+)'
        match = re.search(url_pattern, pr_url)
        
        if not match:
            raise GitOpsError(f"Invalid pull request URL format. Expected: https://bitbucket.org/org/repo/pull-requests/ID")
        
        org_from_url, repo, pr_id = match.groups()
        result['repository'] = repo
        result['pr_id'] = pr_id
        
        print(f"🔍 Merging pull request #{pr_id} in repository '{repo}'...")
        if delete_after_merge:
            print(f"   ⚠️  Source branch will be deleted after merge")
        
        # Get PR details
        pr_details_url = f"{BITBUCKET_API_BASE}/{org_from_url}/{repo}/pullrequests/{pr_id}"
        
        resp = requests.get(pr_details_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Pull request #{pr_id} not found in repository '{repo}'")
        
        resp.raise_for_status()
        pr_data = resp.json()
        
        pr_state = pr_data.get('state', '').upper()
        source_branch = pr_data.get('source', {}).get('branch', {}).get('name', 'unknown')
        dest_branch = pr_data.get('destination', {}).get('branch', {}).get('name', 'unknown')
        result['source'] = source_branch
        result['destination'] = dest_branch
        
        if pr_state == 'MERGED':
            print(f"✅ Pull request #{pr_id} is already merged")
            merge_commit = pr_data.get('merge_commit', {})
            if merge_commit:
                merge_hash = merge_commit.get('hash', 'unknown')
                short_hash = merge_hash[:7] if len(merge_hash) >= 7 else merge_hash
                print(f"   Merge commit: {short_hash}")
                result['merge_commit'] = short_hash
            result['success'] = True
            result['message'] = 'Pull request already merged'
            return result
        
        if pr_state in ['DECLINED', 'SUPERSEDED']:
            raise GitOpsError(f"Pull request #{pr_id} is {pr_state.lower()}. Cannot merge a {pr_state.lower()} pull request.")
        
        print(f"✅ Pull request validated")
        print(f"   Source branch: {source_branch}")
        print(f"   Destination branch: {dest_branch}")
        print(f"   State: {pr_state}")
        
        # Merge the pull request
        merge_url = f"{BITBUCKET_API_BASE}/{org_from_url}/{repo}/pullrequests/{pr_id}/merge"
        
        merge_payload = {
            "close_source_branch": delete_after_merge,
            "merge_strategy": "merge_commit",
            "message": f"Merged pull request #{pr_id} via ngen-gitops"
        }
        
        merge_resp = requests.post(
            merge_url,
            auth=(username, app_password),
            json=merge_payload,
            timeout=30
        )
        
        if merge_resp.status_code == 400:
            error_data = merge_resp.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            raise GitOpsError(f"Failed to merge pull request: {error_msg}")
        
        merge_resp.raise_for_status()
        merge_data = merge_resp.json()
        
        merge_commit = merge_data.get('hash', 'unknown')
        short_hash = merge_commit[:7] if len(merge_commit) >= 7 else merge_commit
        
        print(f"✅ Pull request #{pr_id} merged successfully")
        print(f"   Merge commit: {short_hash}")
        
        if delete_after_merge:
            print(f"✅ Source branch '{source_branch}' deleted")
        
        result['success'] = True
        result['merge_commit'] = short_hash
        result['message'] = f"Pull request #{pr_id} merged successfully"
        
        # Send Teams notification
        notify_pr_merged(repo, pr_id, source_branch, dest_branch, short_hash, user=user)
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise


def run_k8s_pr_workflow(
    cluster: str,
    namespace: str,
    deploy: str,
    image: str,
    approve_merge: bool = False,
    repo: str = "gitops-k8s",
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Run complete K8s PR workflow.
    
    Steps:
    1. Create branch: {namespace}/{deploy}_deployment.yaml
    2. Set image in YAML
    3. Create Pull Request
    4. (Optional) Merge Pull Request
    
    Args:
        cluster: Source branch (e.g., cluster name)
        namespace: Kubernetes namespace
        deploy: Deployment name
        image: New image tag
        approve_merge: Whether to auto-merge the PR
        repo: Repository name (default: gitops-k8s)
        user: User triggering the workflow
        
    Returns:
        dict: Workflow results
    """
    dest_branch = f"{namespace}/{deploy}_deployment.yaml"
    yaml_path = f"{namespace}/{deploy}_deployment.yaml"
    
    print(f"🚀 Starting K8s PR Workflow for {deploy} in {namespace}")
    print(f"   Repo: {repo}")
    print(f"   Cluster/Source: {cluster}")
    print(f"   Image: {image}")
    print(f"   User: {user or 'unknown'}")
    
    workflow_result = {
        "success": False,
        "steps": [],
        "pr_url": "",
        "message": ""
    }
    
    try:
        # Step 1: Create Branch
        print("\n[Step 1/4] Creating branch...")
        branch_res = create_branch(
            repo=repo,
            src_branch=cluster,
            dest_branch=dest_branch,
            user=user
        )
        workflow_result["steps"].append({"name": "create_branch", "result": branch_res})
        
        # Step 2: Set Image
        print("\n[Step 2/4] Updating image in YAML...")
        image_res = set_image_in_yaml(
            repo=repo,
            refs=dest_branch,
            yaml_path=yaml_path,
            image=image,
            user=user
        )
        workflow_result["steps"].append({"name": "set_image", "result": image_res})
        
        if image_res.get('skipped'):
            print("⚠️  Image already up to date, stopping workflow.")
            workflow_result["success"] = True
            workflow_result["message"] = "Image already up to date"
            return workflow_result

        # Step 3: Create PR
        print("\n[Step 3/4] Creating Pull Request...")
        pr_res = create_pull_request(
            repo=repo,
            src_branch=dest_branch,
            dest_branch=cluster,
            delete_after_merge=True,
            user=user
        )
        workflow_result["steps"].append({"name": "create_pr", "result": pr_res})
        workflow_result["pr_url"] = pr_res.get("pr_url")
        
        # Step 4: Merge (Optional)
        if approve_merge:
            print("\n[Step 4/4] Merging Pull Request...")
            merge_res = merge_pull_request(
                pr_url=pr_res["pr_url"],
                delete_after_merge=True,
                user=user
            )
            workflow_result["steps"].append({"name": "merge_pr", "result": merge_res})
            workflow_result["message"] = "Workflow completed successfully (merged)"
        else:
            print("\n[Step 4/4] Skipping merge (use --approve-merge to auto-merge)")
            workflow_result["message"] = "Workflow completed successfully (PR created)"
            
        workflow_result["success"] = True
        return workflow_result
        
    except Exception as e:
        print(f"\n❌ Workflow failed: {str(e)}")
        workflow_result["message"] = str(e)
        workflow_result["success"] = False
        return workflow_result


def create_tag(
    repo: str,
    branch: str,
    commit_id: str,
    tag_name: str,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a tag on a specific commit in Bitbucket repository.
    
    Args:
        repo: Repository name
        branch: Branch name (for validation)
        commit_id: Commit hash to tag
        tag_name: Tag name/version
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
        user: User creating the tag (optional)
    
    Returns:
        dict: Result with success status and tag details
    
    Raises:
        GitOpsError: If tag creation fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'branch': branch,
        'commit_id': commit_id,
        'tag_name': tag_name,
        'message': ''
    }
    
    try:
        print(f"🔍 Creating tag '{tag_name}' on commit '{commit_id[:7]}' in repository '{repo}'...")
        
        # Step 1: Validate branch exists
        branch_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/branches/{branch}"
        
        resp = requests.get(branch_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Branch '{branch}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        print(f"✅ Branch '{branch}' validated")
        
        # Step 2: Validate commit exists
        commit_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/commit/{commit_id}"
        
        resp = requests.get(commit_url, auth=(username, app_password), timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Commit '{commit_id}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        commit_data = resp.json()
        commit_hash = commit_data.get('hash', commit_id)
        print(f"✅ Commit '{commit_hash[:7]}' validated")
        
        # Step 3: Check if tag already exists
        tag_check_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/tags/{tag_name}"
        
        check_resp = requests.get(tag_check_url, auth=(username, app_password), timeout=30)
        
        if check_resp.status_code == 200:
            existing_tag = check_resp.json()
            existing_hash = existing_tag.get('target', {}).get('hash', '')
            if existing_hash == commit_hash:
                print(f"ℹ️  Tag '{tag_name}' already exists on this commit")
                result['success'] = True
                result['message'] = f"Tag '{tag_name}' already exists on commit {commit_hash[:7]}"
                result['tag_url'] = f"https://bitbucket.org/{org}/{repo}/src/{tag_name}"
                return result
            else:
                raise GitOpsError(f"Tag '{tag_name}' already exists on a different commit ({existing_hash[:7]})")
        
        # Step 4: Create tag
        create_tag_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/refs/tags"
        
        payload = {
            "name": tag_name,
            "target": {
                "hash": commit_hash
            }
        }
        
        create_resp = requests.post(
            create_tag_url,
            auth=(username, app_password),
            json=payload,
            timeout=30
        )
        
        if create_resp.status_code == 409:
            raise GitOpsError(f"Tag '{tag_name}' already exists")
        
        create_resp.raise_for_status()
        
        print(f"✅ Tag '{tag_name}' created successfully on commit {commit_hash[:7]}")
        result['success'] = True
        result['message'] = f"Tag '{tag_name}' created on commit {commit_hash[:7]}"
        result['tag_url'] = f"https://bitbucket.org/{org}/{repo}/src/{tag_name}"
        result['commit_hash'] = commit_hash
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise GitOpsError(str(e)) from e


def manage_webhook(
    repo: str,
    webhook_url: str,
    delete: bool = False,
    username: Optional[str] = None,
    app_password: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Manage webhooks in Bitbucket repository.
    
    Args:
        repo: Repository name
        webhook_url: Webhook URL to add or delete
        delete: If True, delete the webhook instead of creating
        username: Bitbucket username (optional)
        app_password: Bitbucket app password (optional)
        org: Bitbucket organization (optional)
        user: User managing the webhook (optional)
    
    Returns:
        dict: Result with success status and webhook details
    
    Raises:
        GitOpsError: If webhook operation fails
    """
    # Get credentials
    if not username or not app_password or not org:
        creds = get_bitbucket_credentials()
        username = username or creds['username']
        app_password = app_password or creds['app_password']
        org = org or creds['organization']
    
    result = {
        'success': False,
        'repository': repo,
        'webhook_url': webhook_url,
        'action': 'delete' if delete else 'create',
        'message': ''
    }
    
    try:
        webhooks_url = f"{BITBUCKET_API_BASE}/{org}/{repo}/hooks"
        
        if delete:
            # Delete webhook
            print(f"🔍 Searching for webhook '{webhook_url}' in repository '{repo}'...")
            
            # Get all webhooks
            resp = requests.get(webhooks_url, auth=(username, app_password), timeout=30)
            resp.raise_for_status()
            
            webhooks_data = resp.json()
            webhooks = webhooks_data.get('values', [])
            
            # Find webhook by URL
            webhook_to_delete = None
            for webhook in webhooks:
                if webhook.get('url') == webhook_url:
                    webhook_to_delete = webhook
                    break
            
            if not webhook_to_delete:
                raise GitOpsError(f"Webhook with URL '{webhook_url}' not found in repository '{repo}'")
            
            webhook_uuid = webhook_to_delete.get('uuid')
            if not webhook_uuid:
                raise GitOpsError("Could not get webhook UUID")
            
            # Delete the webhook
            delete_url = f"{webhooks_url}/{webhook_uuid}"
            delete_resp = requests.delete(delete_url, auth=(username, app_password), timeout=30)
            
            if delete_resp.status_code == 404:
                raise GitOpsError(f"Webhook not found")
            
            delete_resp.raise_for_status()
            
            print(f"✅ Webhook deleted successfully")
            result['success'] = True
            result['message'] = f"Webhook '{webhook_url}' deleted successfully"
            result['webhook_uuid'] = webhook_uuid
            
        else:
            # Create webhook
            print(f"🔍 Creating webhook in repository '{repo}'...")
            print(f"   URL: {webhook_url}")
            
            # Check if webhook already exists
            resp = requests.get(webhooks_url, auth=(username, app_password), timeout=30)
            resp.raise_for_status()
            
            webhooks_data = resp.json()
            existing_webhooks = webhooks_data.get('values', [])
            
            for webhook in existing_webhooks:
                if webhook.get('url') == webhook_url:
                    print(f"ℹ️  Webhook already exists")
                    result['success'] = True
                    result['message'] = f"Webhook already exists"
                    result['webhook_uuid'] = webhook.get('uuid')
                    result['webhook_url'] = webhook.get('url')
                    return result
            
            # Create new webhook
            payload = {
                "description": f"Webhook created by ngen-gitops",
                "url": webhook_url,
                "active": True,
                "events": [
                    "repo:push",
                    "pullrequest:created",
                    "pullrequest:updated",
                    "pullrequest:fulfilled"
                ]
            }
            
            create_resp = requests.post(
                webhooks_url,
                auth=(username, app_password),
                json=payload,
                timeout=30
            )
            
            if create_resp.status_code == 400:
                error_data = create_resp.json()
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                raise GitOpsError(f"Failed to create webhook: {error_msg}")
            
            create_resp.raise_for_status()
            webhook_data = create_resp.json()
            
            webhook_uuid = webhook_data.get('uuid')
            
            print(f"✅ Webhook created successfully")
            print(f"   UUID: {webhook_uuid}")
            
            result['success'] = True
            result['message'] = f"Webhook created successfully"
            result['webhook_uuid'] = webhook_uuid
            result['webhook_url'] = webhook_data.get('url')
            result['events'] = payload['events']
        
        return result
        
    except requests.exceptions.RequestException as e:
        if e.response is not None and e.response.status_code == 403:
            raise GitOpsError(
                "Permission denied (403). Please check if your App Password has 'Webhooks' (Read & Write) permissions enabled."
            ) from e
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise GitOpsError(str(e)) from e
