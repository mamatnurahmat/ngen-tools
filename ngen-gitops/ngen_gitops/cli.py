#!/usr/bin/env python3
"""CLI entry point for ngen-gitops."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import __version__
from .bitbucket import (
    create_branch,
    set_image_in_yaml,
    create_pull_request,
    merge_pull_request,
    run_k8s_pr_workflow,
    list_pull_requests,
    GitOpsError
)
from .config import (
    load_config,
    get_config_file_path,
    config_exists,
    get_bitbucket_credentials,
    get_default_remote,
    get_default_org,
    get_current_user
)
from .git_wrapper import (
    git_clone,
    git_pull,
    git_push,
    git_fetch,
    git_commit,
    git_status,
    GitError
)


def cmd_create_branch(args):
    """Handle create-branch command."""
    try:
        user = get_current_user()
        result = create_branch(
            repo=args.repo,
            src_branch=args.src_branch,
            dest_branch=args.dest_branch,
            user=user
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ {result['message']}")
            if result.get('branch_url'):
                print(f"   Branch URL: {result['branch_url']}")
        
        sys.exit(0 if result['success'] else 1)
        
    except GitOpsError as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_set_image_yaml(args):
    """Handle set-image-yaml command."""
    try:
        user = get_current_user()
        result = set_image_in_yaml(
            repo=args.repo,
            refs=args.refs,
            yaml_path=args.yaml_path,
            image=args.image,
            dry_run=args.dry_run,
            user=user
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ {result['message']}")
            if result.get('commit'):
                print(f"   {result['commit']}")
        
        sys.exit(0 if result['success'] else 1)
        
    except GitOpsError as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pull_request(args):
    """Handle pull-request command."""
    try:
        user = get_current_user()
        result = create_pull_request(
            repo=args.repo,
            src_branch=args.src_branch,
            dest_branch=args.dest_branch,
            delete_after_merge=args.delete_after_merge,
            user=user
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ {result['message']}")
            if result.get('pr_url'):
                print(f"   Pull Request URL: {result['pr_url']}")
        
        sys.exit(0 if result['success'] else 1)
        
    except GitOpsError as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_merge(args):
    """Handle merge command."""
    try:
        user = get_current_user()
        result = merge_pull_request(
            pr_url=args.pr_url,
            delete_after_merge=args.delete_after_merge,
            user=user
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n✅ {result['message']}")
            if result.get('merge_commit'):
                print(f"   Merge commit: {result['merge_commit']}")
        
        sys.exit(0 if result['success'] else 1)
        
    except GitOpsError as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pr_list(args):
    """Handle pr command (list pull requests)."""
    try:
        result = list_pull_requests(
            repo=args.repo,
            status=args.status
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n📋 Pull Requests in {args.repo} (status: {args.status})")
            print()
            
            prs = result.get('pull_requests', [])
            if not prs:
                print("   No pull requests found.")
            else:
                # Print table header
                print(f"  {'#ID':<6} | {'Source Branch':<40} | {'Destination':<40} | {'Author':<40} | {'Created':<40}")
                print(f"  {'-'*6}-+-{'-'*40}-+-{'-'*40}-+-{'-'*40}-+-{'-'*40}")
                
                for pr in prs:
                    pr_id = f"#{pr['id']}"
                    source = pr['source']
                    dest = pr['destination']
                    author = pr['author']
                    created = pr['created_on']
                    
                    print(f"  {pr_id:<6} | {source:<40} | {dest:<40} | {author:<40} | {created:<40}")
                
                print()
                print(f"Total: {result['count']} pull request(s)")
        
        sys.exit(0 if result['success'] else 1)
        
    except GitOpsError as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_k8s_pr(args):
    """Handle k8s-pr command."""
    try:
        user = get_current_user()
        
        result = run_k8s_pr_workflow(
            cluster=args.cluster,
            namespace=args.namespace,
            deploy=args.deploy,
            image=args.image,
            approve_merge=args.approve_merge,
            repo=args.repo,
            user=user
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result['success']:
                print(f"\n✅ {result['message']}")
                if result.get('pr_url'):
                    print(f"   PR URL: {result['pr_url']}")
            else:
                print(f"\n❌ {result['message']}")
        
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_server(args):
    """Handle server command."""
    try:
        from .server import start_server
        
        host = args.host
        port = args.port
        
        print(f"🚀 Starting ngen-gitops server...")
        print(f"   Host: {host}")
        print(f"   Port: {port}")
        print(f"   Endpoints:")
        print(f"     - POST /v1/gitops/create-branch")
        print(f"     - POST /v1/gitops/set-image-yaml")
        print(f"     - POST /v1/gitops/pull-request")
        print(f"     - POST /v1/gitops/merge")
        print()
        
        start_server(host=host, port=port)
        
    except Exception as e:
        print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_clone(args):
    """Handle clone command."""
    try:
        # Get credentials if available (for private repos)
        username = None
        app_password = None
        try:
            creds = get_bitbucket_credentials()
            username = creds['username']
            app_password = creds['app_password']
        except ValueError:
            # Credentials not configured, continue without auth
            pass
        
        result = git_clone(
            repo=args.repo,
            branch=args.branch,
            org=args.org,
            remote=args.remote,
            username=username,
            app_password=app_password,
            destination=args.destination,
            single_branch=not args.full,
            full=args.full
        )
        
        print(f"\n✅ Repository cloned successfully to: {result}")
        sys.exit(0)
        
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pull(args):
    """Handle pull command."""
    try:
        git_pull(branch=args.branch, cwd=args.cwd)
        sys.exit(0)
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_push(args):
    """Handle push command."""
    try:
        git_push(branch=args.branch, cwd=args.cwd, force=args.force)
        sys.exit(0)
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_fetch(args):
    """Handle fetch command."""
    try:
        git_fetch(cwd=args.cwd)
        sys.exit(0)
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_commit(args):
    """Handle commit command."""
    try:
        git_commit(message=args.message, cwd=args.cwd, add_all=args.all)
        sys.exit(0)
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Handle status command."""
    try:
        git_status(cwd=args.cwd)
        sys.exit(0)
    except GitError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config(args):
    """Handle config command."""
    try:
        config = load_config()
        
        if args.json:
            # Mask sensitive data in JSON output
            safe_config = config.copy()
            if 'bitbucket' in safe_config and 'app_password' in safe_config['bitbucket']:
                safe_config['bitbucket']['app_password'] = '***MASKED***'
            print(json.dumps(safe_config, indent=2))
        else:
            print(f"📋 ngen-gitops Configuration")
            print(f"   Config file: {get_config_file_path()}")
            print()
            print(f"Bitbucket:")
            print(f"   Username: {config.get('bitbucket', {}).get('username', '(not set)')}")
            print(f"   App Password: {'***SET***' if config.get('bitbucket', {}).get('app_password') else '(not set)'}")
            print(f"   Organization: {config.get('bitbucket', {}).get('organization', 'loyaltoid')}")
            print()
            print(f"Server:")
            print(f"   Host: {config.get('server', {}).get('host', '0.0.0.0')}")
            print(f"   Port: {config.get('server', {}).get('port', 8080)}")
            print()
            print(f"Git:")
            print(f"   Default Remote: {config.get('git', {}).get('default_remote', 'bitbucket.org')}")
            print(f"   Default Org: {config.get('git', {}).get('default_org', 'loyaltoid')}")
            print()
            print(f"Notifications:")
            teams_webhook = config.get('notifications', {}).get('teams_webhook', '')
            if teams_webhook:
                print(f"   Teams Webhook: {'***SET***'}")
            else:
                print(f"   Teams Webhook: (not set)")
            
            # Check if credentials are valid
            try:
                creds = get_bitbucket_credentials()
                print()
                print("✅ Credentials configured")
            except ValueError as e:
                print()
                print(f"⚠️  {e}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='ngen-gitops / gitops',
        description='GitOps CLI and web server for Bitbucket operations with general git commands',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GitOps Commands (Bitbucket)
  gitops create-branch myrepo main feature/new-feature
  gitops set-image-yaml myrepo develop k8s/deployment.yaml myapp:v1.0.0
  gitops pull-request myrepo feature/new-feature develop --delete-after-merge
  gitops merge https://bitbucket.org/org/repo/pull-requests/123
  
  # Git Commands (multi-remote support)
  gitops clone myrepo main                    # Clone from Bitbucket (default)
  gitops clone myrepo main --remote github.com  # Clone from GitHub
  gitops clone org/repo develop --full         # Clone all branches
  gitops status
  gitops pull develop
  gitops commit -m "Update files" --all
  gitops push
  
  # Server
  gitops server --port 8080
  
  # Configuration
  gitops config

For more information, visit: https://github.com/mamatnurahmat/ngen-gitops
        """
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # create-branch command
    parser_create_branch = subparsers.add_parser(
        'create-branch',
        help='Create a new branch from source branch'
    )
    parser_create_branch.add_argument('repo', help='Repository name')
    parser_create_branch.add_argument('src_branch', help='Source branch name')
    parser_create_branch.add_argument('dest_branch', help='Destination branch name')
    parser_create_branch.add_argument('--json', action='store_true', help='Output as JSON')
    parser_create_branch.set_defaults(func=cmd_create_branch)
    
    # set-image-yaml command
    parser_set_image = subparsers.add_parser(
        'set-image-yaml',
        help='Update image reference in YAML file'
    )
    parser_set_image.add_argument('repo', help='Repository name')
    parser_set_image.add_argument('refs', help='Branch/tag reference')
    parser_set_image.add_argument('yaml_path', help='Path to YAML file in repository')
    parser_set_image.add_argument('image', help='New image to set (e.g., myapp:v1.0.0)')
    parser_set_image.add_argument('--dry-run', action='store_true', help='Prepare changes without pushing')
    parser_set_image.add_argument('--json', action='store_true', help='Output as JSON')
    parser_set_image.set_defaults(func=cmd_set_image_yaml)
    
    # pull-request command
    parser_pr = subparsers.add_parser(
        'pull-request',
        help='Create a pull request'
    )
    parser_pr.add_argument('repo', help='Repository name')
    parser_pr.add_argument('src_branch', help='Source branch name')
    parser_pr.add_argument('dest_branch', help='Destination branch name')
    parser_pr.add_argument('--delete-after-merge', action='store_true', 
                          help='Delete source branch after merge')
    parser_pr.add_argument('--json', action='store_true', help='Output as JSON')
    parser_pr.set_defaults(func=cmd_pull_request)
    
    # merge command
    parser_merge = subparsers.add_parser(
        'merge',
        help='Merge a pull request'
    )
    parser_merge.add_argument('pr_url', help='Pull request URL')
    parser_merge.add_argument('--delete-after-merge', action='store_true',
                             help='Delete source branch after merge')
    parser_merge.add_argument('--json', action='store_true', help='Output as JSON')
    parser_merge.set_defaults(func=cmd_merge)
    
    # pr command (list pull requests)
    parser_pr_list = subparsers.add_parser(
        'pr',
        help='List pull requests in a repository'
    )
    parser_pr_list.add_argument('repo', help='Repository name')
    parser_pr_list.add_argument(
        '--status', '-s',
        default='open',
        choices=['open', 'merged', 'declined', 'draft'],
        help='Filter by status (default: open)'
    )
    parser_pr_list.add_argument('--json', action='store_true', help='Output as JSON')
    parser_pr_list.set_defaults(func=cmd_pr_list)
    
    # k8s-pr command
    parser_k8s_pr = subparsers.add_parser(
        'k8s-pr',
        help='Run complete K8s GitOps workflow (Branch -> Image -> PR -> Merge)'
    )
    parser_k8s_pr.add_argument('cluster', help='Source branch (e.g., cluster name)')
    parser_k8s_pr.add_argument('namespace', help='Kubernetes namespace')
    parser_k8s_pr.add_argument('deploy', help='Deployment name')
    parser_k8s_pr.add_argument('image', help='New image tag')
    parser_k8s_pr.add_argument('--approve-merge', action='store_true', help='Auto-merge the PR')
    parser_k8s_pr.add_argument('--repo', default='gitops-k8s', help='Repository name (default: gitops-k8s)')
    parser_k8s_pr.add_argument('--json', action='store_true', help='Output as JSON')
    parser_k8s_pr.set_defaults(func=cmd_k8s_pr)
    
    # server command
    parser_server = subparsers.add_parser(
        'server',
        help='Start web server'
    )
    parser_server.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser_server.add_argument('--port', type=int, default=8080, help='Server port (default: 8080)')
    parser_server.set_defaults(func=cmd_server)
    
    # config command
    parser_config = subparsers.add_parser(
        'config',
        help='Show configuration'
    )
    parser_config.add_argument('--json', action='store_true', help='Output as JSON')
    parser_config.set_defaults(func=cmd_config)
    
    # Git commands
    # clone command
    parser_clone = subparsers.add_parser(
        'clone',
        help='Clone a git repository'
    )
    parser_clone.add_argument('repo', help='Repository name (e.g., myrepo or org/myrepo)')
    parser_clone.add_argument('branch', nargs='?', help='Branch or tag to clone (optional)')
    parser_clone.add_argument('--org', help='Organization name (defaults to config)')
    parser_clone.add_argument('--remote', help='Remote type: bitbucket.org, github.com, gitlab.com (defaults to config)')
    parser_clone.add_argument('--destination', '-d', help='Destination directory (optional)')
    parser_clone.add_argument('--full', action='store_true', help='Clone all branches (default: single-branch only)')
    parser_clone.set_defaults(func=cmd_clone)
    
    # pull command
    parser_pull = subparsers.add_parser(
        'pull',
        help='Pull from remote repository'
    )
    parser_pull.add_argument('branch', nargs='?', help='Branch to pull (optional, uses current if not specified)')
    parser_pull.add_argument('--cwd', help='Working directory (defaults to current)')
    parser_pull.set_defaults(func=cmd_pull)
    
    # push command
    parser_push = subparsers.add_parser(
        'push',
        help='Push to remote repository'
    )
    parser_push.add_argument('branch', nargs='?', help='Branch to push (optional, uses current if not specified)')
    parser_push.add_argument('--cwd', help='Working directory (defaults to current)')
    parser_push.add_argument('--force', '-f', action='store_true', help='Force push (use with caution)')
    parser_push.set_defaults(func=cmd_push)
    
    # fetch command
    parser_fetch = subparsers.add_parser(
        'fetch',
        help='Fetch from remote repository'
    )
    parser_fetch.add_argument('--cwd', help='Working directory (defaults to current)')
    parser_fetch.set_defaults(func=cmd_fetch)
    
    # commit command
    parser_commit = subparsers.add_parser(
        'commit',
        help='Commit changes'
    )
    parser_commit.add_argument('-m', '--message', required=True, help='Commit message')
    parser_commit.add_argument('--cwd', help='Working directory (defaults to current)')
    parser_commit.add_argument('--all', '-a', action='store_true', help='Add all changes before committing')
    parser_commit.set_defaults(func=cmd_commit)
    
    # status command
    parser_status = subparsers.add_parser(
        'status',
        help='Show git status'
    )
    parser_status.add_argument('--cwd', help='Working directory (defaults to current)')
    parser_status.set_defaults(func=cmd_status)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()
