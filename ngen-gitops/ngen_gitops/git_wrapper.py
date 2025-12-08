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


def git_log(repo: str, ref: str = 'HEAD', max_count: int = 10, 
            commit_id: Optional[str] = None, org: Optional[str] = None, 
            remote: Optional[str] = None, username: Optional[str] = None, 
            app_password: Optional[str] = None, json_format: bool = False,
            short_hash: bool = False) -> dict:
    """Show git commit logs.
    
    Args:
        repo: Repository name (e.g., 'myrepo' or 'org/myrepo')
        ref: Branch/tag reference (default: HEAD)
        max_count: Maximum number of commits to show (default: 10)
        commit_id: Specific commit ID to show details (optional)
        org: Organization name (defaults to config)
        remote: Remote type (defaults to config)
        username: Username for authentication (optional)
        app_password: App password/token for authentication (optional)
        json_format: Return structured data for JSON output (optional)
        
    Returns:
        dict: Git log data with 'output' (raw text) and 'commits' (structured data)
        
    Raises:
        GitError: If log command fails
    """
    # Parse repo if it contains org
    if '/' in repo:
        parts = repo.split('/', 1)
        org = org or parts[0]
        repo = parts[1]
    
    # Use defaults from config
    org = org or get_default_org()
    remote = remote or get_default_remote()
    
    # Create temporary directory for cloning
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Build git URL
        git_url = _build_git_url(org, repo, remote, username, app_password)
        
        # Clone repository (single branch for efficiency)
        clone_args = ['clone', '--single-branch', '-b', ref, '--depth', str(max_count + 10), git_url, temp_dir]
        
        try:
            _run_git_command(clone_args, capture_output=True)
        except GitError:
            # If branch doesn't exist, try with default branch
            import shutil
            shutil.rmtree(temp_dir)
            temp_dir = tempfile.mkdtemp()
            clone_args = ['clone', '--single-branch', '--depth', str(max_count + 10), git_url, temp_dir]
            _run_git_command(clone_args, capture_output=True)
        
        # Build log command
        if commit_id:
            # Show detailed info for specific commit
            log_args = ['show', commit_id, '--stat']
            result = _run_git_command(log_args, cwd=temp_dir, capture_output=True)
            
            # For JSON format, also get structured data
            if json_format:
                json_args = ['show', commit_id, '--format=%H%n%an%n%ae%n%at%n%s%n%b', '--stat']
                json_result = _run_git_command(json_args, cwd=temp_dir, capture_output=True)
                lines = json_result.stdout.strip().split('\n')
                
                return {
                    'success': True,
                    'output': result.stdout,
                    'commit': {
                        'hash': lines[0] if len(lines) > 0 else '',
                        'author': lines[1] if len(lines) > 1 else '',
                        'email': lines[2] if len(lines) > 2 else '',
                        'timestamp': lines[3] if len(lines) > 3 else '',
                        'subject': lines[4] if len(lines) > 4 else '',
                        'body': '\n'.join(lines[5:]) if len(lines) > 5 else ''
                    }
                }
            
            return {'success': True, 'output': result.stdout}
        else:
            # Show oneline log
            log_args = ['log', f'-{max_count}', '--oneline', '--decorate']
            result = _run_git_command(log_args, cwd=temp_dir, capture_output=True)
            
            # For JSON format, get structured data
            if json_format:
                json_args = ['log', f'-{max_count}', '--format=%H|%an|%ae|%at|%s']
                json_result = _run_git_command(json_args, cwd=temp_dir, capture_output=True)
                
                commits = []
                for line in json_result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|')
                        if len(parts) >= 5:
                            commits.append({
                                'hash': parts[0],
                                'author': parts[1],
                                'email': parts[2],
                                'timestamp': parts[3],
                                'subject': '|'.join(parts[4:])  # In case subject contains |
                            })
                
                return {
                    'success': True,
                    'output': result.stdout,
                    'count': len(commits),
                    'commits': commits
                }
            
            if short_hash:
                # Return only short hash of the last commit
                log_args = ['log', '-1', '--format=%h']
                result = _run_git_command(log_args, cwd=temp_dir, capture_output=True)
                return {'success': True, 'output': result.stdout.strip()}

            return {'success': True, 'output': result.stdout}
        
    finally:
        # Cleanup temporary directory
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def git_get_file(repo: str, ref: str, file_path: str, 
                 org: Optional[str] = None, remote: Optional[str] = None,
                 username: Optional[str] = None, app_password: Optional[str] = None) -> dict:
    """Get file content from a git repository.
    
    Args:
        repo: Repository name (e.g., 'myrepo' or 'org/myrepo')
        ref: Branch/tag reference
        file_path: Path to file in repository
        org: Organization name (defaults to config)
        remote: Remote type (defaults to config)
        username: Username for authentication (optional)
        app_password: App password/token for authentication (optional)
        
    Returns:
        dict: File data with 'success', 'content', 'path', 'ref'
        
    Raises:
        GitError: If file retrieval fails
    """
    # Parse repo if it contains org
    if '/' in repo:
        parts = repo.split('/', 1)
        org = org or parts[0]
        repo = parts[1]
    
    # Use defaults from config
    org = org or get_default_org()
    remote = remote or get_default_remote()
    
    # Create temporary directory for cloning
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Build git URL
        git_url = _build_git_url(org, repo, remote, username, app_password)
        
        # Clone repository (single branch, depth 1 for efficiency)
        clone_args = ['clone', '--single-branch', '-b', ref, '--depth', '1', git_url, temp_dir]
        
        try:
            _run_git_command(clone_args, capture_output=True)
        except GitError as e:
            raise GitError(f"Failed to clone repository: {str(e)}")
        
        # Check if file exists
        full_path = os.path.join(temp_dir, file_path)
        if not os.path.exists(full_path):
            raise GitError(f"File not found: {file_path}")
        
        if not os.path.isfile(full_path):
            raise GitError(f"Path is not a file: {file_path}")
        
        # Read file content
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try reading as binary if UTF-8 fails
            with open(full_path, 'rb') as f:
                content = f.read()
                # Encode as base64 for binary files
                import base64
                content = base64.b64encode(content).decode('ascii')
                return {
                    'success': True,
                    'content': content,
                    'path': file_path,
                    'ref': ref,
                    'encoding': 'base64',
                    'binary': True
                }
        
        return {
            'success': True,
            'content': content,
            'path': file_path,
            'ref': ref,
            'encoding': 'utf-8',
            'binary': False
        }
        
    finally:
        # Cleanup temporary directory
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
