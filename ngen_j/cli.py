#!/usr/bin/env python3
"""CLI dispatcher for ngen-j Jenkins management tool."""

import sys
import os
import subprocess
from pathlib import Path
from . import __version__
from .jenkins import JenkinsClient, save_env_file, load_env_file, get_env_file_path


def find_script(command: str) -> Path:
    """
    Find the script wrapper for the given command.

    Args:
        command: The subcommand (e.g., "rancher", "git")

    Returns:
        Path to the script, or None if not found
    """
    # Check in bundled scripts only
    package_dir = Path(__file__).parent
    bundled_script = package_dir / "scripts" / f"ngen-j-{command}"
    if bundled_script.exists() and bundled_script.is_file():
        return bundled_script

    return None


def execute_script(script_path: Path, args: list) -> int:
    """
    Execute the script with the given arguments.
    
    Args:
        script_path: Path to the script to execute
        args: List of arguments to pass to the script
        
    Returns:
        Exit code from the script execution
    """
    try:
        # Make script executable if it's not already
        if not os.access(script_path, os.X_OK):
            os.chmod(script_path, 0o755)
        
        # Execute the script with arguments
        result = subprocess.run([str(script_path)] + args)
        return result.returncode
    except Exception as e:
        print(f"Error executing {script_path}: {e}", file=sys.stderr)
        return 1


def handle_login_command(args: list) -> int:
    """
    Handle login command to save Jenkins credentials.

    Args:
        args: List of arguments for login command

    Returns:
        Exit code
    """
    import getpass

    print("ngen-j Jenkins Login")
    print("===================")

    # Get current env vars
    current_env = load_env_file()

    # Prompt for Jenkins URL
    current_url = current_env.get("JENKINS_URL", "")
    if current_url:
        url = input(f"Jenkins URL [{current_url}]: ").strip() or current_url
    else:
        url = input("Jenkins URL: ").strip()

    if not url:
        print("Error: Jenkins URL is required", file=sys.stderr)
        return 1

    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        print("Error: Jenkins URL must start with http:// or https://", file=sys.stderr)
        return 1

    # Choose authentication method
    print("\nAuthentication method:")
    print("1. Username + API Token (recommended)")
    print("2. Username + Password")
    print("3. Base64 encoded credentials")

    while True:
        choice = input("Choose method [1]: ").strip() or "1"
        if choice in ["1", "2", "3"]:
            break
        print("Invalid choice. Please enter 1, 2, or 3.")

    env_vars = {"JENKINS_URL": url}

    if choice == "1":
        # Username + API Token
        current_user = current_env.get("JENKINS_USER", "")
        if current_user:
            user = input(f"Username [{current_user}]: ").strip() or current_user
        else:
            user = input("Username: ").strip()

        if not user:
            print("Error: Username is required", file=sys.stderr)
            return 1

        current_token = current_env.get("JENKINS_TOKEN", "")
        if current_token:
            token = getpass.getpass(f"API Token [current token set]: ").strip() or current_token
        else:
            token = getpass.getpass("API Token: ").strip()

        if not token:
            print("Error: API Token is required", file=sys.stderr)
            return 1

        env_vars["JENKINS_USER"] = user
        env_vars["JENKINS_TOKEN"] = token

    elif choice == "2":
        # Username + Password
        current_user = current_env.get("JENKINS_USER", "")
        if current_user:
            user = input(f"Username [{current_user}]: ").strip() or current_user
        else:
            user = input("Username: ").strip()

        if not user:
            print("Error: Username is required", file=sys.stderr)
            return 1

        password = getpass.getpass("Password: ").strip()

        if not password:
            print("Error: Password is required", file=sys.stderr)
            return 1

        # Create base64 auth
        import base64
        auth_string = f"{user}:{password}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        env_vars["JENKINS_AUTH"] = auth_b64

    elif choice == "3":
        # Base64 encoded
        current_auth = current_env.get("JENKINS_AUTH", "")
        if current_auth:
            auth_b64 = input(f"Base64 encoded credentials [current set]: ").strip() or current_auth
        else:
            auth_b64 = input("Base64 encoded credentials (username:password): ").strip()

        if not auth_b64:
            print("Error: Base64 encoded credentials are required", file=sys.stderr)
            return 1

        env_vars["JENKINS_AUTH"] = auth_b64

    # Save to .env file
    if save_env_file(env_vars):
        env_file_path = get_env_file_path()
        print(f"\n✅ Credentials saved to: {env_file_path}")
        print("You can now use Jenkins commands without setting environment variables.")

        # Test connection
        print("\nTesting connection...")
        try:
            # Temporarily set env vars for testing
            old_env = {}
            for key, value in env_vars.items():
                old_env[key] = os.environ.get(key)
                os.environ[key] = value

            client = JenkinsClient()
            version = client.client.version
            print(f"✅ Connection successful! Jenkins version: {version}")

            # Restore old env vars
            for key, value in old_env.items():
                if value is not None:
                    os.environ[key] = value
                elif key in os.environ:
                    del os.environ[key]

        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            print("Please check your credentials and try again.")

        return 0
    else:
        print("❌ Failed to save credentials", file=sys.stderr)
        return 1


def handle_check_command(args: list) -> int:
    """
    Handle check command to validate Jenkins access.

    Args:
        args: List of arguments for check command

    Returns:
        Exit code
    """
    print("ngen-j Jenkins Connection Check")
    print("==============================")

    try:
        # Try to create Jenkins client (will load from .env or env vars)
        client = JenkinsClient()

        print(f"✅ Connected to Jenkins: {client.url}")
        print(f"   User: {client.user or 'N/A'}")

        # Get Jenkins version
        try:
            # Try different ways to get version
            if hasattr(client.client, 'version'):
                version = client.client.version
            else:
                # Fallback: try to get server info
                info = client.client.api_json()
                version = info.get('version', 'Unknown')
            print(f"   Version: {version}")
        except Exception as e:
            print(f"   Version: Unable to retrieve ({e})")

        # Try to get basic info
        try:
            # Get number of jobs using correct API
            jobs = client.list_jobs()
            jobs_count = len(jobs)
            print(f"   Jobs: {jobs_count} job(s) found")
        except Exception as e:
            print(f"   Jobs: Unable to retrieve ({e})")

        # Test API access with a simple call
        try:
            # Test with a simple API call that should work
            if hasattr(client.client, 'api_json'):
                info = client.client.api_json()
                if 'mode' in info or 'nodeDescription' in info:
                    print("   API Access: ✅ OK")
                else:
                    print("   API Access: ⚠️  Limited (basic info only)")
            else:
                # Fallback: try to list jobs as API test
                jobs = client.list_jobs()
                print("   API Access: ✅ OK")
        except Exception as e:
            print(f"   API Access: ❌ Failed ({e})")
            return 1

        print("\n🎉 Jenkins connection is working correctly!")
        print("You can now use Jenkins commands.")

        return 0

    except Exception as e:
        print(f"❌ Jenkins connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if Jenkins URL is correct and accessible")
        print("2. Verify your credentials using 'ngen-j login'")
        print("3. Ensure Jenkins user has API access permissions")
        print("4. Check network connectivity and firewall settings")
        print("5. For HTTPS, ensure SSL certificates are valid")
        return 1


def main():
    """Main entry point for ngen-j command."""
    # Handle version flag
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        print(f"ngen-j version {__version__}")
        sys.exit(0)
    
    if len(sys.argv) < 2:
        print("Usage: ngen-j <command> [args...]", file=sys.stderr)
        print("\nAvailable commands:", file=sys.stderr)
        # List available commands
        commands_found = set()
        
        # Add built-in commands
        commands_found.add("login")
        commands_found.add("check")
        commands_found.add("jobs")
        commands_found.add("job")
        commands_found.add("build")
        
        # Check bundled scripts
        package_dir = Path(__file__).parent
        bundled_dir = package_dir / "scripts"
        if bundled_dir.exists():
            for script in bundled_dir.glob("ngen-j-*"):
                if script.is_file():
                    command = script.name.replace("ngen-j-", "", 1)
                    commands_found.add(command)
        
        # Print commands
        for cmd in sorted(commands_found):
            if cmd in ["login", "check", "jobs", "job", "build"]:
                print(f"  {cmd} (builtin)")
            else:
                print(f"  {cmd}")
        if not commands_found:
            print("  (no commands found)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Handle help flags
    if command in ("-h", "--help", "help"):
        print("Usage: ngen-j <command> [args...]", file=sys.stderr)
        print("\nngen-j is a Jenkins API management CLI tool.", file=sys.stderr)
        print("\nBuilt-in commands:", file=sys.stderr)
        print("  login             Save Jenkins credentials", file=sys.stderr)
        print("  check             Validate Jenkins access", file=sys.stderr)
        print("  jobs              List all Jenkins jobs", file=sys.stderr)
        print("  job <name>        Get job details", file=sys.stderr)
        print("  build <job-name>  Trigger a build", file=sys.stderr)
        print("\nScript commands:", file=sys.stderr)
        print("  <script-name>     Execute bundled script", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  ngen-j --version", file=sys.stderr)
        print("  ngen-j jobs", file=sys.stderr)
        print("  ngen-j job my-job", file=sys.stderr)
        print("  ngen-j build my-job", file=sys.stderr)
        sys.exit(0)
    
    # Handle login command
    if command == "login":
        exit_code = handle_login_command(sys.argv[2:])
        sys.exit(exit_code)

    # Handle check command
    if command == "check":
        exit_code = handle_check_command(sys.argv[2:])
        sys.exit(exit_code)

    # Handle jobs command
    if command == "jobs":
        client = JenkinsClient()
        jobs = client.list_jobs()
        if jobs:
            print("Jenkins Jobs:")
            for job in jobs:
                print(f"  {job['name']} - {job['url']}")
        else:
            print("No jobs found")
        sys.exit(0)

    # Handle job command
    if command == "job":
        if len(sys.argv) < 3:
            print("Error: job name required", file=sys.stderr)
            print("Usage: ngen-j job <name>", file=sys.stderr)
            sys.exit(1)
        job_name = sys.argv[2]
        client = JenkinsClient()
        job_info = client.get_job(job_name)
        print(f"Job: {job_info['name']}")
        print(f"URL: {job_info['url']}")
        if job_info.get('description'):
            print(f"Description: {job_info['description']}")
        print(f"Buildable: {job_info.get('buildable', False)}")
        sys.exit(0)

    # Handle build command
    if command == "build":
        if len(sys.argv) < 3:
            print("Error: job name required", file=sys.stderr)
            print("Usage: ngen-j build <job-name>", file=sys.stderr)
            sys.exit(1)
        job_name = sys.argv[2]
        client = JenkinsClient()
        build_info = client.trigger_build(job_name)
        print(f"Build triggered for job: {job_name}")
        print(f"Queue ID: {build_info['queue_id']}")
        print(f"Queue URL: {build_info['url']}")
        sys.exit(0)

    # Try to find and execute script
    args = sys.argv[2:]
    script_path = find_script(command)
    
    if script_path is not None:
        exit_code = execute_script(script_path, args)
        sys.exit(exit_code)
    
    # Command not found
    print(f"Error: command '{command}' not found", file=sys.stderr)
    print(f"Expected bundled script: ngen-j-{command}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
