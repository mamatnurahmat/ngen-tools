"""Git wrapper for general git operations with flexible remote support."""
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote

from .config import get_default_remote, get_default_org


class GitError(Exception):
    """Base exception for git operations."""
    pass


def _build_git_url(org: str, repo: str, remote: str, username: Optional[str] = None, 
                   app_password: Optional[str] = None) -> str:
    """Build git URL based on remote type.
    
    Args:
        org: Organization/user name
        repo: Repository name
        remote: Remote type (bitbucket.org, github.com, gitlab.com)
        username: Optional username for authentication
        app_password: Optional app password/token for authentication
        
    Returns:
        str: Git URL
    """
    # Remove .git suffix if present
    if repo.endswith('.git'):
        repo = repo[:-4]
    
    # Build URL based on remote
    if remote == 'bitbucket.org':
        if username and app_password:
            return f"https://{quote(username)}:{quote(app_password)}@bitbucket.org/{org}/{repo}.git"
        return f"https://bitbucket.org/{org}/{repo}.git"
    elif remote == 'github.com':
        if username and app_password:
            return f"https://{quote(username)}:{quote(app_password)}@github.com/{org}/{repo}.git"
        return f"https://github.com/{org}/{repo}.git"
    elif remote == 'gitlab.com':
        if username and app_password:
            return f"https://{quote(username)}:{quote(app_password)}@gitlab.com/{org}/{repo}.git"
        return f"https://gitlab.com/{org}/{repo}.git"
    else:
        # Custom remote URL
        if '://' in remote:
            # Full URL provided
            return remote
        else:
            # Assume it's a hostname
            if username and app_password:
                return f"https://{quote(username)}:{quote(app_password)}@{remote}/{org}/{repo}.git"
            return f"https://{remote}/{org}/{repo}.git"


def _run_git_command(args: List[str], cwd: Optional[str] = None, 
                     capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run git command.
    
    Args:
        args: Git command arguments
        cwd: Working directory
        capture_output: Whether to capture output
        
    Returns:
        CompletedProcess: Result of git command
        
    Raises:
        GitError: If git command fails
    """
    try:
        if capture_output:
            result = subprocess.run(
                ['git'] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
        else:
            result = subprocess.run(
                ['git'] + args,
                cwd=cwd,
                check=False
            )
        
        if result.returncode != 0:
            error_msg = result.stderr if capture_output else f"Git command failed with code {result.returncode}"
            raise GitError(error_msg)
        
        return result
    except FileNotFoundError:
        raise GitError("git command not found. Please install git.")
    except Exception as e:
        raise GitError(f"Git command failed: {str(e)}")


def git_clone(repo: str, branch: Optional[str] = None, 
              org: Optional[str] = None, remote: Optional[str] = None,
              username: Optional[str] = None, app_password: Optional[str] = None,
              destination: Optional[str] = None, single_branch: bool = True,
              full: bool = False) -> str:
    """Clone a git repository.
    
    Args:
        repo: Repository name (e.g., 'myrepo' or 'org/myrepo')
        branch: Branch/tag to clone (optional)
        org: Organization name (defaults to config)
        remote: Remote type (defaults to config)
        username: Username for authentication (optional)
        app_password: App password/token for authentication (optional)
        destination: Destination directory (optional)
        single_branch: Clone only single branch (default: True)
        full: Clone all branches (overrides single_branch)
        
    Returns:
        str: Path to cloned repository
        
    Raises:
        GitError: If clone fails
    """
    # Parse repo if it contains org
    if '/' in repo:
        parts = repo.split('/', 1)
        org = org or parts[0]
        repo = parts[1]
    
    # Use defaults from config
    org = org or get_default_org()
    remote = remote or get_default_remote()
    
    # Build git URL
    git_url = _build_git_url(org, repo, remote, username, app_password)
    
    # Build clone command
    clone_args = ['clone']
    
    # Handle single-branch vs full clone
    if full:
        # Clone all branches
        pass
    elif single_branch and branch:
        # Clone only specified branch
        clone_args.extend(['--single-branch', '-b', branch])
    elif single_branch:
        # Clone only default branch
        clone_args.append('--single-branch')
    elif branch:
        # Clone with specific branch but get all branches
        clone_args.extend(['-b', branch])
    
    clone_args.append(git_url)
    
    if destination:
        clone_args.append(destination)
    
    # Run clone
    print(f"🔄 Cloning {org}/{repo} from {remote}...")
    if branch:
        print(f"   Branch/Tag: {branch}")
    if full:
        print(f"   Mode: Full (all branches)")
    elif single_branch:
        print(f"   Mode: Single branch")
    
    _run_git_command(clone_args)
    
    dest_path = destination or repo
    print(f"✅ Successfully cloned to {dest_path}")
    
    return dest_path


def git_pull(branch: Optional[str] = None, cwd: Optional[str] = None) -> None:
    """Pull from remote repository.
    
    Args:
        branch: Branch to pull (optional, uses current branch if not specified)
        cwd: Working directory (defaults to current directory)
        
    Raises:
        GitError: If pull fails
    """
    pull_args = ['pull']
    if branch:
        pull_args.extend(['origin', branch])
    
    print(f"🔄 Pulling from remote...")
    _run_git_command(pull_args, cwd=cwd)
    print(f"✅ Successfully pulled changes")


def git_push(branch: Optional[str] = None, cwd: Optional[str] = None, 
             force: bool = False) -> None:
    """Push to remote repository.
    
    Args:
        branch: Branch to push (optional, uses current branch if not specified)
        cwd: Working directory (defaults to current directory)
        force: Force push (use with caution)
        
    Raises:
        GitError: If push fails
    """
    push_args = ['push']
    if force:
        push_args.append('--force')
    
    if branch:
        push_args.extend(['origin', branch])
    
    print(f"🔄 Pushing to remote...")
    _run_git_command(push_args, cwd=cwd)
    print(f"✅ Successfully pushed changes")


def git_fetch(cwd: Optional[str] = None) -> None:
    """Fetch from remote repository.
    
    Args:
        cwd: Working directory (defaults to current directory)
        
    Raises:
        GitError: If fetch fails
    """
    print(f"🔄 Fetching from remote...")
    _run_git_command(['fetch'], cwd=cwd)
    print(f"✅ Successfully fetched changes")


def git_commit(message: str, cwd: Optional[str] = None, add_all: bool = False) -> None:
    """Commit changes.
    
    Args:
        message: Commit message
        cwd: Working directory (defaults to current directory)
        add_all: Add all changes before committing
        
    Raises:
        GitError: If commit fails
    """
    if add_all:
        print(f"🔄 Adding all changes...")
        _run_git_command(['add', '.'], cwd=cwd)
    
    print(f"🔄 Committing changes...")
    _run_git_command(['commit', '-m', message], cwd=cwd)
    print(f"✅ Successfully committed changes")


def git_status(cwd: Optional[str] = None) -> str:
    """Show git status.
    
    Args:
        cwd: Working directory (defaults to current directory)
        
    Returns:
        str: Git status output
        
    Raises:
        GitError: If status command fails
    """
    result = _run_git_command(['status'], cwd=cwd, capture_output=True)
    output = result.stdout
    print(output)
    return output


def git_add(files: Optional[List[str]] = None, cwd: Optional[str] = None, 
            all_files: bool = False) -> None:
    """Add files to staging.
    
    Args:
        files: List of files to add (optional)
        cwd: Working directory (defaults to current directory)
        all_files: Add all files
        
    Raises:
        GitError: If add fails
    """
    add_args = ['add']
    
    if all_files:
        add_args.append('.')
    elif files:
        add_args.extend(files)
    else:
        raise GitError("Either files or all_files must be specified")
    
    print(f"🔄 Adding files to staging...")
    _run_git_command(add_args, cwd=cwd)
    print(f"✅ Successfully added files")


def git_branch(list_all: bool = False, cwd: Optional[str] = None) -> str:
    """List or show current branch.
    
    Args:
        list_all: List all branches
        cwd: Working directory (defaults to current directory)
        
    Returns:
        str: Branch output
        
    Raises:
        GitError: If branch command fails
    """
    branch_args = ['branch']
    if list_all:
        branch_args.append('-a')
    
    result = _run_git_command(branch_args, cwd=cwd, capture_output=True)
    output = result.stdout
    print(output)
    return output


def git_checkout(branch: str, create: bool = False, cwd: Optional[str] = None) -> None:
    """Checkout a branch.
    
    Args:
        branch: Branch name
        create: Create new branch
        cwd: Working directory (defaults to current directory)
        
    Raises:
        GitError: If checkout fails
    """
    checkout_args = ['checkout']
    if create:
        checkout_args.append('-b')
    checkout_args.append(branch)
    
    print(f"🔄 Checking out branch {branch}...")
    _run_git_command(checkout_args, cwd=cwd)
    print(f"✅ Successfully checked out {branch}")
