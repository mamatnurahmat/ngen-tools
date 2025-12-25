#!/usr/bin/env python3
"""CLI dispatcher for argoapi tool."""

import sys
import os
import json
import getpass
from . import __version__
from .argocd import ArgocdClient, save_env_file, load_env_file, get_env_file_path

def handle_login_command(args: list) -> int:
    """
    Handle login command to save ArgoCD credentials.
    Supports both interactive and non-interactive modes.
    
    Non-interactive: argoapi login --url <url> --user <user> --password <pass>
    Interactive: argoapi login
    """
    # Parse command line arguments for non-interactive mode
    url = None
    user = None
    password = None
    
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif arg.startswith("--url="):
            url = arg.split("=", 1)[1]
            i += 1
        elif arg == "--user" and i + 1 < len(args):
            user = args[i + 1]
            i += 2
        elif arg.startswith("--user="):
            user = arg.split("=", 1)[1]
            i += 1
        elif arg == "--password" and i + 1 < len(args):
            password = args[i + 1]
            i += 2
        elif arg.startswith("--password="):
            password = arg.split("=", 1)[1]
            i += 1
        elif arg in ("-h", "--help"):
            print("Usage: argoapi login [OPTIONS]", file=sys.stderr)
            print("\nOptions:", file=sys.stderr)
            print("  --url <url>         ArgoCD server URL", file=sys.stderr)
            print("  --user <username>   Username", file=sys.stderr)
            print("  --password <pass>   Password", file=sys.stderr)
            print("\nExamples:", file=sys.stderr)
            print("  argoapi login", file=sys.stderr)
            print("  argoapi login --url https://argocd.example.com --user admin --password secret", file=sys.stderr)
            return 0
        else:
            i += 1
    
    # Check if all non-interactive params are provided
    is_interactive = not (url and user and password)
    
    if is_interactive:
        print("argoapi Login")
        print("=============")

        # Get current env vars
        current_env = load_env_file()

        # Prompt for ArgoCD URL if not provided
        if not url:
            current_url = current_env.get("ARGOCD_URL", "")
            if current_url:
                url = input(f"ArgoCD URL [{current_url}]: ").strip() or current_url
            else:
                url = input("ArgoCD URL: ").strip()

        if not url:
            print("Error: ArgoCD URL is required", file=sys.stderr)
            return 1

        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            print("Error: ArgoCD URL must start with http:// or https://", file=sys.stderr)
            return 1

        # Username if not provided
        if not user:
            current_user = current_env.get("ARGOCD_USER", "")
            if current_user:
                user = input(f"Username [{current_user}]: ").strip() or current_user
            else:
                user = input("Username: ").strip()

        if not user:
            print("Error: Username is required", file=sys.stderr)
            return 1

        # Password if not provided
        if not password:
            password = getpass.getpass("Password: ").strip()
            
        if not password:
            print("Error: Password is required", file=sys.stderr)
            return 1

        print("\nAuthenticating...")
    else:
        # Non-interactive mode validation
        if not url.startswith(('http://', 'https://')):
            print("Error: ArgoCD URL must start with http:// or https://", file=sys.stderr)
            return 1
        print(f"Authenticating to {url}...")
    
    try:
        # Insecure by default as requested
        token = ArgocdClient.obtain_token(url, user, password, insecure=True)
        
        env_vars = {
            "ARGOCD_URL": url,
            "ARGOCD_USER": user,
            "ARGOCD_TOKEN": token
        }

        if save_env_file(env_vars):
            print(f"✅ Credentials saved to: {get_env_file_path()}")
            print("You can now use argoapi commands.")
            return 0
        else:
             print("❌ Failed to save credentials", file=sys.stderr)
             return 1
             
    except Exception as e:
        print(f"❌ Authentication failed: {e}", file=sys.stderr)
        return 1

def handle_app_command(args: list) -> int:
    """
    Handle app related commands (list, get, diff, refresh).
    """
    if not args:
        print("Usage: argoapi app <command> [args...]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        print("  list              List all applications", file=sys.stderr)
        print("  get <name>        Get application details", file=sys.stderr)
        print("  diff <name>       Show diff against live state", file=sys.stderr)
        print("  refresh <name>    Refresh application", file=sys.stderr)
        return 1

    subcommand = args[0]
    
    if subcommand == "list":
        try:
            client = ArgocdClient()
            apps = client.list_applications()
            
            if not apps:
                print("No applications found.")
                return 0
                
            # Print header
            print(f"{'NAME':<30} {'SYNC STATUS':<15} {'HEALTH STATUS':<15} {'AUTO SYNC':<10}")
            print("-" * 72)
            
            for app in apps:
                name = app.get('metadata', {}).get('name', 'N/A')
                status = app.get('status', {})
                spec = app.get('spec', {})
                sync_status = status.get('sync', {}).get('status', 'Unknown')
                health_status = status.get('health', {}).get('status', 'Unknown')
                
                # Check auto sync policy
                sync_policy = spec.get('syncPolicy', {})
                automated = sync_policy.get('automated')
                if automated is not None:
                    auto_sync = "Yes"
                else:
                    auto_sync = "No"
                
                # Colorize sync status
                # Synced = Green, OutOfSync = Yellow/Red
                sync_display = sync_status
                if sync_status == 'Synced':
                    sync_display = f"\033[92m{sync_status}\033[0m"
                elif sync_status == 'OutOfSync':
                    sync_display = f"\033[93m{sync_status}\033[0m"
                
                # Colorize health status
                # Healthy = Green, Degraded = Red
                health_display = health_status
                if health_status == 'Healthy':
                    health_display = f"\033[92m{health_status}\033[0m"
                elif health_status in ('Degraded', 'Missing'):
                    health_display = f"\033[91m{health_status}\033[0m"
                elif health_status == 'Progressing':
                     health_display = f"\033[94m{health_status}\033[0m"
                
                # Colorize auto sync
                auto_sync_display = auto_sync
                if auto_sync == "Yes":
                    auto_sync_display = f"\033[92m{auto_sync}\033[0m"
                else:
                    auto_sync_display = f"\033[93m{auto_sync}\033[0m"

                print(f"{name:<30} {sync_display:<24} {health_display:<24} {auto_sync_display:<10}")
                
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    if subcommand == "diff":
        if len(args) < 2:
            print("Error: application name required", file=sys.stderr)
            print("Usage: argoapi app diff <name> [--type=compact|inline]", file=sys.stderr)
            return 1
        
        app_name = args[1]
        diff_type = "inline" # default
        
        # Parse diff type
        for arg in args[2:]:
            if arg.startswith("--type="):
                diff_type = arg.split("=", 1)[1]
            elif arg == "--compact":
                diff_type = "compact"
            elif arg == "--inline":
                diff_type = "inline"
                
        if diff_type not in ("compact", "inline"):
             print(f"Error: Unknown diff type '{diff_type}'. Use 'compact' or 'inline'.", file=sys.stderr)
             return 1
             
        try:
            client = ArgocdClient()
            app = client.get_application(app_name)
            
            # Check overall sync status first
            sync_status = app.get('status', {}).get('sync', {}).get('status', 'Unknown')
            if sync_status == 'Synced':
                print(f"Application '{app_name}' is fully synced. No diffs.")
                return 0
                
            # Get managed resources
            resources = app.get('status', {}).get('resources', [])
            out_of_sync = [r for r in resources if r.get('status') == 'OutOfSync']
            
            if not out_of_sync:
                print(f"Application '{app_name}' status is {sync_status} but no OutOfSync resources found (or maybe waiting for refresh).")
                return 0
                
            print(f"Found {len(out_of_sync)} OutOfSync resource(s). Fetching diffs...")
            
            diffs_found = False
            for res in out_of_sync:
                group = res.get('group', '')
                kind = res.get('kind', '')
                name = res.get('name', '')
                namespace = res.get('namespace', '')
                version = res.get('version', '')
                res_status = res.get('status', 'OutOfSync')
                
                print(f"\nResource: {kind}/{name} ({res_status})")
                
                diff_data = client.get_resource_diff(app_name, group, kind, name, namespace, version)
                
                # Retrieve the diff content
                # Structure: { "diff": "...", "base": "...", "target": "..." }
                # Or sometimes it's a list.
                
                diff_content = diff_data.get('diff')
                
                if not diff_content:
                     print("  (No diff content returned by API)")
                     continue
                     
                diffs_found = True
                
                # Check formatting
                # Inline (standard diff)
                if diff_type == "inline":
                    # Colorize the diff
                    for line in diff_content.splitlines():
                        if line.startswith('+'):
                             print(f"\033[92m{line}\033[0m")
                        elif line.startswith('-'):
                             print(f"\033[91m{line}\033[0m")
                        else:
                             print(line)
                
                # Compact (summary or side-by-side simulation? usually means just changed lines)
                elif diff_type == "compact":
                    # Compact view: only show lines that changed with context?
                    # Or just show the diff without excessive context if provided.
                    # Since we only get 'diff' string from API (which is usually uniform text),
                    # we can filter it.
                    
                    # Simple compact implementation: Show only lines starting with + or -
                    # (and maybe 1 line context?)
                    
                    lines = diff_content.splitlines()
                    for i, line in enumerate(lines):
                        if line.startswith('+') or line.startswith('-'):
                             if line.startswith('+'):
                                 print(f"\033[92m{line}\033[0m")
                             else:
                                 print(f"\033[91m{line}\033[0m")
                        elif line.startswith('@@'):
                             print(f"\033[36m{line}\033[0m")
                             
            if not diffs_found:
                 print("\nNo detailed diffs available.")
                 
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if subcommand == "get":
        if len(args) < 2:
            print("Error: application name required", file=sys.stderr)
            print("Usage: argoapi app get <name>", file=sys.stderr)
            return 1
        
        app_name = args[1]
        try:
            client = ArgocdClient()
            app = client.get_application(app_name)
            print(json.dumps(app, indent=2))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif subcommand == "refresh":
        if len(args) < 2:
            print("Error: application name required", file=sys.stderr)
            print("Usage: argoapi app refresh <name> [--hard]", file=sys.stderr)
            return 1
        
        app_name = args[1]
        hard = "--hard" in args
        
        try:
            client = ArgocdClient()
            app = client.refresh_application(app_name, hard=hard)
            print(f"Application '{app_name}' refresh triggered.")
            # Verify refresh timestamp or status if possible, but basic response is app json
            status = app.get('status', {}).get('sync', {}).get('status', 'Unknown')
            health = app.get('status', {}).get('health', {}).get('status', 'Unknown')
            print(f"Current Status: {status}")
            print(f"Health: {health}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
    else:
        print(f"Unknown app command: {subcommand}", file=sys.stderr)
        return 1

def handle_detail_command(args: list) -> int:
    """
    Handle detail command to show application details including images.
    Usage: argoapi detail <app_name>
    """
    if not args or args[0] in ("-h", "--help"):
        print("Usage: argoapi detail <app_name>", file=sys.stderr)
        print("\nShow application details including container images.", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  argoapi detail my-app", file=sys.stderr)
        print("  argoapi detail my-app --json", file=sys.stderr)
        return 0

    app_name = args[0]
    json_output = "--json" in args
    
    try:
        client = ArgocdClient()
        result = client.get_application_images(app_name)
        
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            images = result.get("images", [])
            details = result.get("details", [])
            
            print(f"Application: {app_name}")
            print(f"Total Images: {len(images)}")
            print("")
            
            if images:
                print("Container Images:")
                print("-" * 60)
                for i, image in enumerate(images, 1):
                    # Parse image to show registry/repo:tag
                    print(f"  {i}. {image}")
            else:
                print("No container images found.")
            
            if details:
                print("")
                print("Workload Resources:")
                print("-" * 60)
                print(f"{'KIND':<20} {'NAME':<25} {'STATUS':<15}")
                for d in details:
                    kind = d.get("kind", "")
                    name = d.get("name", "")
                    status = d.get("status", "Unknown")
                    health = d.get("health", "Unknown")
                    
                    # Colorize status
                    if status == "Synced":
                        status_display = f"\033[92m{status}\033[0m"
                    elif status == "OutOfSync":
                        status_display = f"\033[93m{status}\033[0m"
                    else:
                        status_display = status
                    
                    print(f"  {kind:<18} {name:<25} {status_display}")
        
        return 0
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

def main():
    """Main entry point."""
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        print(f"argoapi version {__version__}")
        sys.exit(0)

    if len(sys.argv) < 2:
        print("argoapi - ArgoCD API CLI Tool", file=sys.stderr)
        print("Usage: argoapi <command> [args...]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        print("  login             Login to ArgoCD and save credentials", file=sys.stderr)
        print("  app               Application management commands", file=sys.stderr)
        print("  detail <name>     Show application details and images", file=sys.stderr)
        print("  server            Start REST API server with Swagger UI", file=sys.stderr)
        sys.exit(0)

    command = sys.argv[1]

    if command in ("-h", "--help", "help"):
        print("argoapi - ArgoCD API CLI Tool", file=sys.stderr)
        print("Usage: argoapi <command> [args...]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        print("  login             Login to ArgoCD and save credentials", file=sys.stderr)
        print("  app               Application management commands", file=sys.stderr)
        print("  detail <name>     Show application details and images", file=sys.stderr)
        print("  server            Start REST API server with Swagger UI", file=sys.stderr)
        print("  auto=true <name>  Enable auto-sync for application", file=sys.stderr)
        print("  auto=false <name> Disable auto-sync for application", file=sys.stderr)
        sys.exit(0)

    if command == "login":
        sys.exit(handle_login_command(sys.argv[2:]))

    if command == "app":
        sys.exit(handle_app_command(sys.argv[2:]))

    if command == "detail":
        sys.exit(handle_detail_command(sys.argv[2:]))

    if command == "server":
        # Parse server options
        port = 8899
        host = "0.0.0.0"
        
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--port" and i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                except ValueError:
                    print(f"Error: Invalid port number: {args[i + 1]}", file=sys.stderr)
                    sys.exit(1)
                i += 2
            elif arg.startswith("--port="):
                try:
                    port = int(arg.split("=", 1)[1])
                except ValueError:
                    print(f"Error: Invalid port number", file=sys.stderr)
                    sys.exit(1)
                i += 1
            elif arg == "--host" and i + 1 < len(args):
                host = args[i + 1]
                i += 2
            elif arg.startswith("--host="):
                host = arg.split("=", 1)[1]
                i += 1
            elif arg in ("-h", "--help"):
                print("Usage: argoapi server [OPTIONS]", file=sys.stderr)
                print("\nOptions:", file=sys.stderr)
                print("  --port <port>   Server port (default: 8899)", file=sys.stderr)
                print("  --host <host>   Server host (default: 0.0.0.0)", file=sys.stderr)
                print("\nEndpoints:", file=sys.stderr)
                print("  GET /app/list         List all applications", file=sys.stderr)
                print("  GET /app/{name}       Get application details", file=sys.stderr)
                print("  GET /app/refresh/{name}  Refresh application", file=sys.stderr)
                print("  GET /app/diff/{name}  Get application diff", file=sys.stderr)
                print("\nSwagger UI: http://localhost:{port}/docs", file=sys.stderr)
                sys.exit(0)
            else:
                i += 1
        
        # Import and run server
        try:
            from .server import run_server
            run_server(host=host, port=port)
        except ImportError as e:
            print(f"Error: Server dependencies not installed. Run: pip install fastapi uvicorn", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle 'auto' without value - show help
    if command == "auto":
        print("Usage: argoapi auto=<true|false> <app_name> [OPTIONS]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  argoapi auto=true my-app           Enable auto-sync", file=sys.stderr)
        print("  argoapi auto=true my-app --prune   Enable with prune", file=sys.stderr)
        print("  argoapi auto=false my-app          Disable auto-sync", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --prune       Enable pruning of resources", file=sys.stderr)
        print("  --self-heal   Enable self-healing", file=sys.stderr)
        sys.exit(0)

    # Handle auto=true/false command
    if command.startswith("auto="):
        value = command.split("=", 1)[1].lower()
        
        if value not in ("true", "false"):
            print("Error: auto value must be 'true' or 'false'", file=sys.stderr)
            print("Usage: argoapi auto=true <app_name>", file=sys.stderr)
            print("       argoapi auto=false <app_name>", file=sys.stderr)
            sys.exit(1)
        
        if len(sys.argv) < 3:
            print("Error: application name required", file=sys.stderr)
            print("Usage: argoapi auto=true <app_name>", file=sys.stderr)
            print("       argoapi auto=false <app_name>", file=sys.stderr)
            sys.exit(1)
        
        app_name = sys.argv[2]
        enabled = value == "true"
        
        # Parse optional flags
        prune = "--prune" in sys.argv[3:]
        self_heal = "--self-heal" in sys.argv[3:]
        
        try:
            client = ArgocdClient()
            result = client.set_auto_sync(app_name, enabled, prune=prune, self_heal=self_heal)
            
            if enabled:
                options = []
                if prune:
                    options.append("prune")
                if self_heal:
                    options.append("self-heal")
                options_str = f" ({', '.join(options)})" if options else ""
                print(f"✅ Auto-sync enabled for '{app_name}'{options_str}")
            else:
                print(f"✅ Auto-sync disabled for '{app_name}'")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Unknown command: {command}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
