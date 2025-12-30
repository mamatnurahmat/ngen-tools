#!/usr/bin/env python3
"""CLI entry point for ngen-buildx."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from . import __version__
from .config import (
    load_config,
    load_build_args,
    get_config_file_path,
    get_arg_file_path,
    config_exists,
    create_default_env,
    create_default_arg_json,
    ensure_config_dir
)
from .builder import execute_build, BuildxError, get_git_info


def cmd_build(args):
    """Handle build command."""
    try:
        # Determine if remote build
        remote = not args.local
        
        # Get repo and ref - auto-detect from git if in local mode and not provided
        repo = args.repo
        ref = args.ref
        
        if args.local and (not repo or not ref):
            if not args.json:
                print("🔍 Detecting git repository info...")
            git_info = get_git_info()
            if not repo:
                repo = git_info["repo"]
            if not ref:
                ref = git_info["ref"]
            if not args.json:
                print(f"   Repository: {repo}")
                print(f"   Reference: {ref}")
        
        # Validate required args for remote build
        if not args.local and (not repo or not ref):
            print("❌ Error: repo and ref are required for remote builds", file=sys.stderr)
            print("   Use --local flag to build from current directory", file=sys.stderr)
            sys.exit(1)
        
        # Determine cicd path for local builds
        cicd_path = None
        if args.cicd:
            cicd_path = args.cicd
        elif args.local:
            # Default local path when using --local
            cicd_path = "cicd/cicd.json"
        
        # Parse extra build args from CLI
        extra_build_args = []
        if args.build_arg:
            for arg in args.build_arg:
                extra_build_args.extend(["--build-arg", arg])
        
        result = execute_build(
            repo=repo,
            ref=ref,
            context_path=args.context if args.local else None,
            dockerfile=args.dockerfile,
            tag=args.tag,
            push=args.push,
            platform=args.platform,
            org=args.org,
            dry_run=args.dry_run,
            remote=remote,
            rebuild=args.rebuild,
            cicd_path=cicd_path,
            extra_args=extra_build_args if extra_build_args else None,
            json_mode=args.json or args.json_detail
        )
        
        if args.json_detail:
            # Full JSON output
            print(json.dumps(result, indent=2))
        elif args.json:
            # Simple JSON output: only NS, DEPLOY, IMAGE
            simple_result = {
                "ready": result.get("success", False),
                "NS": result.get("NS", ""),
                "DEPLOY": result.get("DEPLOY", ""),
                "IMAGE": result.get("image_tag", "")
            }
            if result.get("error"):
                simple_result["error"] = result.get("error")
            print(json.dumps(simple_result, indent=2))
        else:
            if result.get('dry_run'):
                print(f"\n🔍 Dry Run Mode")
                print(f"{'=' * 60}")
                print(result['command'])
                print(f"{'=' * 60}")
                if result.get('image_tag'):
                    print(f"\n🏷️  Image tag: {result['image_tag']}")
                    if result.get('image_exists'):
                        print(f"   ⚠️  Image already exists in registry")
                    else:
                        print(f"   ✅ Image does not exist, will be built")
                print(f"\nℹ️  {result['message']}")
                print(f"\n📋 CICD Config from repository:")
                for key, value in result.get('cicd_config', {}).items():
                    print(f"   {key}: {value}")
            elif result.get('skipped'):
                print(f"\n⏭️  {result['message']}")
            elif result['success']:
                print(f"\n✅ {result['message']}")
                if result.get('image_tag'):
                    print(f"   🏷️  Image: {result['image_tag']}")
            else:
                print(f"\n❌ {result['message']}", file=sys.stderr)
        
        sys.exit(0 if result['success'] else 1)
        
    except BuildxError as e:
        if args.json or args.json_detail:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.json or args.json_detail:
            print(json.dumps({'success': False, 'error': str(e)}, indent=2))
        else:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config(args):
    """Handle config command."""
    try:
        config = load_config()
        build_args = load_build_args()
        
        if args.json:
            output = {
                "config": config,
                "build_args": build_args,
                "config_file": get_config_file_path(),
                "arg_file": get_arg_file_path()
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"📋 ngen-buildx Configuration")
            print(f"   Config file: {get_config_file_path()}")
            print(f"   Args file:   {get_arg_file_path()}")
            print()
            print(f"Builder:")
            builder = config.get('builder', {})
            print(f"   Name: {builder.get('name', '(not set)')}")
            print(f"   Memory: {builder.get('memory', '(not set)')}")
            print(f"   CPU Period: {builder.get('cpu_period', '(not set)')}")
            print(f"   CPU Quota: {builder.get('cpu_quota', '(not set)')}")
            print()
            print(f"Registry:")
            registry = config.get('registry', {})
            print(f"   Registry01 URL: {registry.get('registry01_url', '(not set)')}")
            print()
            print(f"GitOps:")
            gitops = config.get('gitops', {})
            print(f"   Organization: {gitops.get('org', 'loyaltoid')}")
            print()
            print(f"Build Arguments (from arg.json):")
            for key, value in build_args.items():
                print(f"   {key}: {value}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_init(args):
    """Handle init command."""
    try:
        ensure_config_dir()
        
        env_existed = config_exists()
        
        if args.force or not config_exists():
            create_default_env()
            create_default_arg_json()
            
            if env_existed and args.force:
                print(f"✅ Configuration files recreated (forced)")
            else:
                print(f"✅ Configuration files created")
            
            print(f"   Config: {get_config_file_path()}")
            print(f"   Args:   {get_arg_file_path()}")
            print()
            print(f"ℹ️  Please update the config files with your settings:")
            print(f"   - Edit {get_config_file_path()} for environment variables")
            print(f"   - Edit {get_arg_file_path()} for build arguments")
        else:
            print(f"ℹ️  Configuration files already exist")
            print(f"   Config: {get_config_file_path()}")
            print(f"   Args:   {get_arg_file_path()}")
            print()
            print(f"   Use --force to recreate")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='ngen-buildx / buildx',
        description='Docker Buildx CLI wrapper with GitOps integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build from remote repository (default)
  buildx saas-apigateway develop
  buildx saas-apigateway develop --dry-run
  
  # Build from local directory (auto-detects repo and branch from git)
  buildx --local                             # Auto-detect repo and ref
  buildx --local --dry-run                   # Preview build command
  buildx myrepo main --local                 # Explicit repo and ref
  
  # Build with custom cicd.json path
  buildx --local --cicd config/cicd.json
  
  # Build with custom options
  buildx myrepo main --platform linux/amd64,linux/arm64
  buildx myrepo v1.0.0 --local --tag myregistry/myapp:v1.0.0 --push
  
  # Configuration
  buildx --config                # Show current configuration
  buildx --init                  # Initialize config files
  buildx --init --force          # Recreate config files

Configuration files:
  ~/.ngen-buildx/.env            # Environment variables
  ~/.ngen-buildx/arg.json        # Build arguments template

For more information, visit: https://github.com/mamatnurahmat/ngen-buildx
        """
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    # Config and init flags
    parser.add_argument('--config', action='store_true', help='Show current configuration')
    parser.add_argument('--init', action='store_true', help='Initialize configuration files')
    parser.add_argument('--force', action='store_true', help='Force recreate config files (use with --init)')
    
    # Build arguments (positional)
    parser.add_argument('repo', nargs='?', help='Repository name')
    parser.add_argument('ref', nargs='?', help='Branch or tag reference')
    
    # Build options
    parser.add_argument('--local', action='store_true', help='Build from local context instead of remote repo')
    parser.add_argument('--rebuild', action='store_true', help='Force rebuild even if image exists')
    parser.add_argument('--cicd', metavar='PATH', 
                        help='Path to local cicd.json (default: cicd/cicd.json when using --local)')
    parser.add_argument('--context', default='.', help='Build context path for local builds (default: .)')
    parser.add_argument('--dockerfile', '-f', default='Dockerfile', help='Dockerfile path (default: Dockerfile)')
    parser.add_argument('--tag', '-t', help='Image tag (default: from cicd.json)')
    parser.add_argument('--push', action='store_true', help='Push image after build (default for remote builds)')
    parser.add_argument('--platform', help='Target platform (e.g., linux/amd64,linux/arm64)')
    parser.add_argument('--org', help='Organization (default: from config)')
    parser.add_argument('--build-arg', action='append', metavar='KEY=VALUE', 
                        help='Set build argument (can be used multiple times, overrides arg.json)')
    parser.add_argument('--dry-run', action='store_true', help='Show command without executing')
    parser.add_argument('--json', action='store_true', help='Output as simple JSON (NS, DEPLOY, IMAGE)')
    parser.add_argument('--json-detail', action='store_true', help='Output as detailed JSON with all fields')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle --config
    if args.config:
        cmd_config(args)
        return
    
    # Handle --init
    if args.init:
        cmd_init(args)
        return
    
    # Handle build (default)
    # For --local mode, repo and ref are optional (auto-detected from git)
    if not args.local and (not args.repo or not args.ref):
        parser.print_help()
        sys.exit(1)
    
    cmd_build(args)


if __name__ == '__main__':
    main()

