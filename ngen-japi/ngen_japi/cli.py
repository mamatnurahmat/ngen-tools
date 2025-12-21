#!/usr/bin/env python3
"""CLI dispatcher for japi Jenkins management tool."""

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
    bundled_script = package_dir / "scripts" / f"japi-{command}"
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

    print("japi Jenkins Login")
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
    print("japi Jenkins Connection Check")
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
        print("2. Verify your credentials using 'japi login'")
        print("3. Ensure Jenkins user has API access permissions")
        print("4. Check network connectivity and firewall settings")
        print("5. For HTTPS, ensure SSL certificates are valid")
        return 1


def main():
    """Main entry point for ngen-j command."""
    # Handle version flag
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        print(f"japi version {__version__}")
        sys.exit(0)
    
    if len(sys.argv) < 2:
        print("Usage: japi <command> [args...]", file=sys.stderr)
        print("\njapi is a Jenkins API management CLI tool.", file=sys.stderr)
        print("\nBuilt-in commands:", file=sys.stderr)
        print("  login             Save Jenkins credentials", file=sys.stderr)
        print("  check             Validate Jenkins access", file=sys.stderr)
        print("  jobs              List all Jenkins jobs", file=sys.stderr)
        print("  job <name>        Get job details", file=sys.stderr)
        print("  job --last-success Get last 10 successful jobs", file=sys.stderr)
        print("  job --last-failure Get last 10 failed jobs", file=sys.stderr)
        print("  build <job-name>  Trigger a build", file=sys.stderr)
        print("  log <name> <num>  Get build console output", file=sys.stderr)
        print("  get-xml <name>    Get job configuration XML", file=sys.stderr)
        print("  create <name> <xml> Create/update job from XML", file=sys.stderr)
        print("  delete <name>     Delete a job", file=sys.stderr)
        print("  plugin list       List installed plugins", file=sys.stderr)
        print("  plugin backup     Backup plugins to JSON/TXT file", file=sys.stderr)
        print("  plugin restore    Restore/install plugins from backup", file=sys.stderr)
        print("  plugin install   Install plugin(s)", file=sys.stderr)
        print("  plugin uninstall Uninstall plugin(s)", file=sys.stderr)
        print("                    Use --format json|csv|txt and --output <file> for export", file=sys.stderr)
        print("  cred list         List all credentials", file=sys.stderr)
        print("  cred create       Create credential (interactive or non-interactive)", file=sys.stderr)
        print("  cred delete <id>  Delete credential", file=sys.stderr)
        print("\nScript commands:", file=sys.stderr)
        print("  <script-name>     Execute bundled script", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  japi --version", file=sys.stderr)
        print("  japi jobs", file=sys.stderr)
        print("  japi job my-job", file=sys.stderr)
        print("  japi job --last-success", file=sys.stderr)
        print("  japi job --last-failure", file=sys.stderr)
        print("  japi build my-job", file=sys.stderr)
        print("  japi build my-job --param REF_NAME=develop", file=sys.stderr)
        print("  japi build my-job --param=REF_NAME=develop", file=sys.stderr)
        print("  japi log my-job 42", file=sys.stderr)
        print("  japi get-xml my-job", file=sys.stderr)
        print("  japi create my-job job.xml", file=sys.stderr)
        print("  japi delete my-job", file=sys.stderr)
        print("  japi delete my-job --force", file=sys.stderr)
        print("  japi plugin list", file=sys.stderr)
        print("  japi plugin list --format json --output plugins.json", file=sys.stderr)
        print("  japi plugin list --format csv --output plugins.csv", file=sys.stderr)
        print("  japi plugin list --format txt --output plugins.txt", file=sys.stderr)
        print("  japi plugin backup --file plugins.txt --format txt", file=sys.stderr)
        print("  japi plugin restore --file plugins.txt", file=sys.stderr)
        print("  japi plugin install git", file=sys.stderr)
        print("  japi plugin uninstall git", file=sys.stderr)
        print("  japi cred list", file=sys.stderr)
        print("  japi cred create", file=sys.stderr)
        print("  japi cred delete my-cred", file=sys.stderr)
        sys.exit(0)
    
    command = sys.argv[1]
    
    # Handle help flags
    if command in ("-h", "--help", "help"):
        print("Usage: japi <command> [args...]", file=sys.stderr)
        print("\njapi is a Jenkins API management CLI tool.", file=sys.stderr)
        print("\nBuilt-in commands:", file=sys.stderr)
        print("  login             Save Jenkins credentials", file=sys.stderr)
        print("  check             Validate Jenkins access", file=sys.stderr)
        print("  jobs              List all Jenkins jobs", file=sys.stderr)
        print("  job <name>        Get job details", file=sys.stderr)
        print("  job --last-success Get last 10 successful jobs", file=sys.stderr)
        print("  job --last-failure Get last 10 failed jobs", file=sys.stderr)
        print("  build <job-name>  Trigger a build", file=sys.stderr)
        print("  log <name> <num>  Get build console output", file=sys.stderr)
        print("  get-xml <name>    Get job configuration XML", file=sys.stderr)
        print("  create <name> <xml> Create/update job from XML", file=sys.stderr)
        print("  delete <name>     Delete a job", file=sys.stderr)
        print("  plugin list       List installed plugins", file=sys.stderr)
        print("  plugin install   Install plugin(s)", file=sys.stderr)
        print("  plugin uninstall Uninstall plugin(s)", file=sys.stderr)
        print("                    Use --format json|csv and --output <file> for export", file=sys.stderr)
        print("  cred list         List all credentials", file=sys.stderr)
        print("  cred create       Create credential (interactive or non-interactive)", file=sys.stderr)
        print("  cred delete <id>  Delete credential", file=sys.stderr)
        print("  cred backup       Backup all credentials to JSON", file=sys.stderr)
        print("  cred restore      Restore credentials from JSON", file=sys.stderr)
        print("  user list         List all users", file=sys.stderr)
        print("  user backup       Backup all users to JSON", file=sys.stderr)
        print("  user restore      Restore users from JSON", file=sys.stderr)
        print("\nScript commands:", file=sys.stderr)
        print("  <script-name>     Execute bundled script", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  japi --version", file=sys.stderr)
        print("  japi jobs", file=sys.stderr)
        print("  japi job my-job", file=sys.stderr)
        print("  japi job --last-success", file=sys.stderr)
        print("  japi job --last-failure", file=sys.stderr)
        print("  japi build my-job", file=sys.stderr)
        print("  japi build my-job --param REF_NAME=develop", file=sys.stderr)
        print("  japi build my-job --param=REF_NAME=develop", file=sys.stderr)
        print("  japi log my-job 42", file=sys.stderr)
        print("  japi get-xml my-job", file=sys.stderr)
        print("  japi create my-job job.xml", file=sys.stderr)
        print("  japi delete my-job", file=sys.stderr)
        print("  japi delete my-job --force", file=sys.stderr)
        print("  japi plugin list", file=sys.stderr)
        print("  japi plugin list --format json --output plugins.json", file=sys.stderr)
        print("  japi plugin list --format csv --output plugins.csv", file=sys.stderr)
        print("  japi plugin list --format txt --output plugins.txt", file=sys.stderr)
        print("  japi plugin backup --file plugins.txt --format txt", file=sys.stderr)
        print("  japi plugin restore --file plugins.txt", file=sys.stderr)
        print("  japi plugin install git", file=sys.stderr)
        print("  japi plugin uninstall git", file=sys.stderr)
        print("  japi cred list", file=sys.stderr)
        print("  japi cred create", file=sys.stderr)
        print("  japi cred delete my-cred", file=sys.stderr)
        print("  japi cred backup --file my-backup.json", file=sys.stderr)
        print("  japi cred restore --file my-backup.json --force", file=sys.stderr)
        print("  japi user list", file=sys.stderr)
        print("  japi user backup --file users.json", file=sys.stderr)
        print("  japi user restore --file users.json --password newpass123", file=sys.stderr)
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
        args = sys.argv[2:]

        # Check for flags
        if '--last-success' in args:
            args.remove('--last-success')
            client = JenkinsClient()
            jobs_info = client.get_recent_jobs_by_status('SUCCESS', 10)
            print("Last 10 Successful Jobs:")
            print("=" * 80)
            for i, job_info in enumerate(jobs_info, 1):
                print(f"{i}. {job_info['name']}")
                print(f"   URL: {job_info['url']}")
                if job_info.get('description'):
                    print(f"   Description: {job_info['description']}")
                print(f"   Buildable: {job_info.get('buildable', False)}")
                last_build = job_info.get('last_build', {})
                if last_build:
                    status = last_build['status']
                    # Colorize status
                    if status == 'SUCCESS':
                        status_display = f"\033[92m{status}\033[0m"  # Green
                    elif status == 'FAILURE':
                        status_display = f"\033[91m{status}\033[0m"  # Red
                    elif status == 'BUILDING':
                        status_display = f"\033[93m{status}\033[0m"  # Yellow
                    else:
                        status_display = status

                    print(f"   Last Build: #{last_build.get('number', 'N/A')} - {status_display}")
                    print(f"   Build Time: {last_build.get('start_time', 'N/A')}")
                    print(f"   Duration: {last_build.get('duration', 'N/A')}")
                print()
            if not jobs_info:
                print("No successful jobs found.")
            sys.exit(0)

        elif '--last-failure' in args:
            args.remove('--last-failure')
            client = JenkinsClient()
            jobs_info = client.get_recent_jobs_by_status('FAILURE', 10)
            print("Last 10 Failed Jobs:")
            print("=" * 80)
            for i, job_info in enumerate(jobs_info, 1):
                print(f"{i}. {job_info['name']}")
                print(f"   URL: {job_info['url']}")
                if job_info.get('description'):
                    print(f"   Description: {job_info['description']}")
                print(f"   Buildable: {job_info.get('buildable', False)}")
                last_build = job_info.get('last_build', {})
                if last_build:
                    status = last_build['status']
                    # Colorize status
                    if status == 'SUCCESS':
                        status_display = f"\033[92m{status}\033[0m"  # Green
                    elif status == 'FAILURE':
                        status_display = f"\033[91m{status}\033[0m"  # Red
                    elif status == 'BUILDING':
                        status_display = f"\033[93m{status}\033[0m"  # Yellow
                    else:
                        status_display = status

                    print(f"   Last Build: #{last_build.get('number', 'N/A')} - {status_display}")
                    print(f"   Build Time: {last_build.get('start_time', 'N/A')}")
                    print(f"   Duration: {last_build.get('duration', 'N/A')}")
                print()
            if not jobs_info:
                print("No failed jobs found.")
            sys.exit(0)

        # Default behavior: get specific job
        if not args:
            print("Error: job name required or use --last-success/--last-failure", file=sys.stderr)
            print("Usage: japi job <name>", file=sys.stderr)
            print("       japi job --last-success", file=sys.stderr)
            print("       japi job --last-failure", file=sys.stderr)
            sys.exit(1)

        job_name = args[0]
        client = JenkinsClient()
        job_info = client.get_job(job_name)
        print(f"Job: {job_info['name']}")
        print(f"URL: {job_info['url']}")
        if job_info.get('description'):
            print(f"Description: {job_info['description']}")
        print(f"Buildable: {job_info.get('buildable', False)}")

        # Display recent builds
        recent_builds = job_info.get('recent_builds', [])
        if recent_builds:
            print("\nRecent Builds:")
            print("-" * 70)
            print(f"{'Build #':<10} {'Status':<12} {'Start Time':<20} {'Duration':<15}")
            print("-" * 70)
            for build in recent_builds:
                status = build['status']
                # Colorize status
                if status == 'SUCCESS':
                    status_display = f"\033[92m{status}\033[0m"  # Green
                elif status == 'FAILURE':
                    status_display = f"\033[91m{status}\033[0m"  # Red
                elif status == 'BUILDING':
                    status_display = f"\033[93m{status}\033[0m"  # Yellow
                else:
                    status_display = status

                print(f"{build['number']:<10} {status_display:<12} {build['start_time']:<20} {build['duration']:<15}")
        else:
            print("\nNo recent builds found.")

        sys.exit(0)

    # Handle build command
    if command == "build":
        # Parse arguments for --param flags
        args = sys.argv[2:]
        parameters = {}

        # Extract --param KEY=VALUE arguments
        filtered_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '--param':
                # Handle --param KEY1=VALUE1 KEY2=VALUE2 format (can have multiple parameters)
                i += 1
                # Collect all following arguments that contain '=' until we hit another flag or job name
                while i < len(args):
                    next_arg = args[i]
                    if next_arg.startswith('--') or '=' not in next_arg:
                        # Stop if we hit another flag or argument without '='
                        break
                    if '=' in next_arg:
                        key, value = next_arg.split('=', 1)
                        parameters[key] = value
                    i += 1
                continue
            elif arg.startswith('--param='):
                # Parse --param=KEY=VALUE format
                param_str = arg[8:]  # Remove '--param=' prefix
                if '=' in param_str:
                    key, value = param_str.split('=', 1)
                    parameters[key] = value
                else:
                    print(f"Error: Invalid parameter format '{arg}'. Use --param=KEY=VALUE", file=sys.stderr)
                    sys.exit(1)
            else:
                filtered_args.append(arg)
            i += 1

        if len(filtered_args) != 1:
            print("Usage: japi build <job-name> [--param KEY1=VALUE1 KEY2=VALUE2 ...] or [--param=KEY=VALUE ...]", file=sys.stderr)
            print("  --param KEY=VALUE ...  Pass multiple build parameters after single --param flag", file=sys.stderr)
            print("  --param=KEY=VALUE      Alternative format for build parameters", file=sys.stderr)
            sys.exit(1)

        job_name = filtered_args[0]
        client = JenkinsClient()
        build_info = client.trigger_build(job_name, parameters if parameters else None)

        print(f"Build triggered for job: {job_name}")
        if parameters:
            print("Parameters:")
            for key, value in parameters.items():
                print(f"  {key}={value}")
        print(f"Queue ID: {build_info['queue_id']}")
        print(f"Queue URL: {build_info['url']}")
        sys.exit(0)

    # Handle create command
    if command == "create":
        # Parse arguments for --force flag
        force = False
        args = sys.argv[2:]

        if '--force' in args:
            force = True
            args.remove('--force')

        if len(args) != 2:
            print("Usage: japi create <job-name> <xml-file> [--force]", file=sys.stderr)
            print("  --force    Skip confirmation when updating existing job", file=sys.stderr)
            sys.exit(1)

        job_name = args[0]
        xml_file = args[1]

        # Read XML file
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        except FileNotFoundError:
            print(f"Error: XML file '{xml_file}' not found", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading XML file: {e}", file=sys.stderr)
            sys.exit(1)

        # Create/update job
        client = JenkinsClient()
        result = client.create_job_from_xml(job_name, xml_content, force)

        if result['status'] == 'success':
            print(f"✅ Job '{job_name}' {result['action']} successfully!")
            print(f"   URL: {result['url']}")
        elif result['status'] == 'cancelled':
            print(f"ℹ️  {result['message']}")
        else:
            print(f"❌ Failed to create/update job: {result.get('error', 'Unknown error')}")
            sys.exit(1)

        sys.exit(0)

    # Handle delete command
    if command == "delete":
        # Parse arguments for --force flag
        force = False
        args = sys.argv[2:]

        if '--force' in args:
            force = True
            args.remove('--force')

        if len(args) != 1:
            print("Usage: japi delete <job-name> [--force]", file=sys.stderr)
            print("  --force    Skip confirmation before deleting job", file=sys.stderr)
            sys.exit(1)

        job_name = args[0]

        # Delete job
        client = JenkinsClient()
        result = client.delete_job(job_name, force)

        if result['status'] == 'success':
            print(f"✅ Job '{job_name}' deleted successfully!")
        elif result['status'] == 'cancelled':
            print(f"ℹ️  {result['message']}")
        else:
            print(f"❌ Failed to delete job: {result.get('error', 'Unknown error')}")

        sys.exit(0)

    # Handle get-xml command
    if command == "get-xml":
        if len(sys.argv) < 3:
            print("Error: job name required", file=sys.stderr)
            print("Usage: japi get-xml <job-name>", file=sys.stderr)
            sys.exit(1)
        job_name = sys.argv[2]
        client = JenkinsClient()
        xml_content = client.get_job_xml(job_name)
        print(xml_content)
        sys.exit(0)

    # Handle log command
    if command == "log":
        if len(sys.argv) < 4:
            print("Error: job name and build number required", file=sys.stderr)
            print("Usage: japi log <job-name> <build-number>", file=sys.stderr)
            sys.exit(1)
        job_name = sys.argv[2]
        try:
            build_number = int(sys.argv[3])
        except ValueError:
            print("Error: build number must be an integer", file=sys.stderr)
            sys.exit(1)

        client = JenkinsClient()
        logs = client.get_build_logs(job_name, build_number)
        print(f"Console output for {job_name} build #{build_number}:")
        print("=" * 80)
        print(logs)
        sys.exit(0)

    # Handle cred command
    if command == "cred":
        if len(sys.argv) < 3:
            print("Error: cred subcommand required", file=sys.stderr)
            print("Usage: japi cred <list|create|delete> [args...]", file=sys.stderr)
            print("\nCredential management commands:", file=sys.stderr)
            print("  list                    List all credentials", file=sys.stderr)
            print("  create                  Create a new credential (interactive)", file=sys.stderr)
            print("  delete <id>             Delete a credential", file=sys.stderr)
            print("  backup                  Backup all credentials to JSON", file=sys.stderr)
            print("  restore                 Restore credentials from JSON", file=sys.stderr)
            print("\nBackup/Restore options:", file=sys.stderr)
            print("  --file <file>           Backup file path (default: jenkins_credentials_backup.json)", file=sys.stderr)
            print("  --force                (Restore only) Overwrite existing credentials", file=sys.stderr)
            print("\nCreate credential options (non-interactive):", file=sys.stderr)
            print("  --type <type>           Credential type: username_password, secret_text, ssh_key", file=sys.stderr)
            print("  --id <id>               Credential ID", file=sys.stderr)
            print("  --description <desc>   Description", file=sys.stderr)
            print("  --username <user>      Username (for username_password, ssh_key)", file=sys.stderr)
            print("  --password <pass>      Password (for username_password)", file=sys.stderr)
            print("  --secret <secret>      Secret text (for secret_text)", file=sys.stderr)
            print("  --private-key <key>   Private key content (for ssh_key)", file=sys.stderr)
            print("  --private-key-file <file>  Private key file path (for ssh_key)", file=sys.stderr)
            print("  --passphrase <phrase>  Passphrase for encrypted private key (for ssh_key)", file=sys.stderr)
            print("  --force                Overwrite existing credential", file=sys.stderr)
            sys.exit(1)

        subcommand = sys.argv[2]
        client = JenkinsClient()

        if subcommand == "list":
            credentials = client.list_credentials()
            
            if credentials:
                print("Jenkins Credentials:")
                print("=" * 100)
                print(f"{'ID':<30} {'Type':<25} {'Description':<40} {'Scope':<10}")
                print("=" * 100)
                for cred in credentials:
                    cred_id = cred.get('id', 'N/A')
                    cred_type = cred.get('type', 'N/A')
                    # Extract readable type name
                    if 'UsernamePassword' in cred_type:
                        cred_type = 'Username/Password'
                    elif 'StringCredentials' in cred_type:
                        cred_type = 'Secret Text'
                    elif 'SSHUserPrivateKey' in cred_type or 'BasicSSH' in cred_type:
                        cred_type = 'SSH Key'
                    else:
                        cred_type = cred_type.split('.')[-1] if '.' in cred_type else cred_type
                    
                    description = cred.get('description', '')
                    if len(description) > 38:
                        description = description[:35] + "..."
                    scope = cred.get('scope', 'GLOBAL')
                    
                    print(f"{cred_id:<30} {cred_type:<25} {description:<40} {scope:<10}")
            else:
                print("No credentials found.")
            sys.exit(0)

        elif subcommand == "create":
            args = sys.argv[3:]
            
            # Check if non-interactive mode (has --type and --id)
            is_interactive = True
            if '--type' in args and '--id' in args:
                is_interactive = False
            
            if is_interactive:
                # Interactive mode
                import getpass
                
                print("Create Jenkins Credential (Interactive Mode)")
                print("=" * 50)
                
                print("\nSelect credential type:")
                print("1. Username/Password")
                print("2. Secret Text")
                print("3. SSH Username with Private Key")
                
                type_choice = input("Choice [1-3]: ").strip()
                
                cred_type_map = {
                    '1': 'username_password',
                    '2': 'secret_text',
                    '3': 'ssh_key'
                }
                
                if type_choice not in cred_type_map:
                    print("Error: Invalid choice", file=sys.stderr)
                    sys.exit(1)
                
                cred_type = cred_type_map[type_choice]
                
                cred_id = input("Credential ID: ").strip()
                if not cred_id:
                    print("Error: Credential ID is required", file=sys.stderr)
                    sys.exit(1)
                
                description = input("Description (optional): ").strip()
                
                username = None
                password = None
                secret = None
                private_key = None
                private_key_file = None
                passphrase = None
                
                if cred_type == 'username_password':
                    username = input("Username: ").strip()
                    password = getpass.getpass("Password: ")
                    if not username or not password:
                        print("Error: Username and password are required", file=sys.stderr)
                        sys.exit(1)
                
                elif cred_type == 'secret_text':
                    secret = getpass.getpass("Secret text: ")
                    if not secret:
                        print("Error: Secret text is required", file=sys.stderr)
                        sys.exit(1)
                
                elif cred_type == 'ssh_key':
                    username = input("Username: ").strip()
                    key_source = input("Private key from [1] string or [2] file? [1]: ").strip() or '1'
                    
                    if key_source == '2':
                        private_key_file = input("Private key file path: ").strip()
                        if not private_key_file:
                            print("Error: Private key file path is required", file=sys.stderr)
                            sys.exit(1)
                    else:
                        print("Paste private key (end with empty line or Ctrl+D):")
                        private_key_lines = []
                        try:
                            while True:
                                line = input()
                                if not line:
                                    break
                                private_key_lines.append(line)
                        except EOFError:
                            pass
                        private_key = '\n'.join(private_key_lines)
                        if not private_key:
                            print("Error: Private key is required", file=sys.stderr)
                            sys.exit(1)
                    
                    passphrase_input = getpass.getpass("Passphrase (optional, press Enter to skip): ").strip()
                    if passphrase_input:
                        passphrase = passphrase_input
                    
                    if not username:
                        print("Error: Username is required", file=sys.stderr)
                        sys.exit(1)
                
                # Check if credential exists
                existing_creds = client.list_credentials()
                cred_exists = any(c.get('id') == cred_id for c in existing_creds)
                
                force = False
                if cred_exists:
                    response = input(f"Credential '{cred_id}' already exists. Overwrite? (y/N): ").strip().lower()
                    if response in ['y', 'yes']:
                        force = True
                    else:
                        print("Credential creation cancelled.")
                        sys.exit(0)
                
                result = client.create_credential(
                    cred_type=cred_type,
                    cred_id=cred_id,
                    description=description,
                    username=username,
                    password=password,
                    secret=secret,
                    private_key=private_key,
                    private_key_file=private_key_file,
                    passphrase=passphrase,
                    force=force
                )
                
            else:
                # Non-interactive mode
                # Parse arguments
                cred_type = None
                cred_id = None
                description = ""
                username = None
                password = None
                secret = None
                private_key = None
                private_key_file = None
                passphrase = None
                force = False
                
                i = 0
                while i < len(args):
                    arg = args[i]
                    if arg == '--type' and i + 1 < len(args):
                        cred_type = args[i + 1]
                        i += 2
                    elif arg == '--id' and i + 1 < len(args):
                        cred_id = args[i + 1]
                        i += 2
                    elif arg == '--description' and i + 1 < len(args):
                        description = args[i + 1]
                        i += 2
                    elif arg == '--username' and i + 1 < len(args):
                        username = args[i + 1]
                        i += 2
                    elif arg == '--password' and i + 1 < len(args):
                        password = args[i + 1]
                        i += 2
                    elif arg == '--secret' and i + 1 < len(args):
                        secret = args[i + 1]
                        i += 2
                    elif arg == '--private-key' and i + 1 < len(args):
                        private_key = args[i + 1]
                        i += 2
                    elif arg == '--private-key-file' and i + 1 < len(args):
                        private_key_file = args[i + 1]
                        i += 2
                    elif arg == '--passphrase' and i + 1 < len(args):
                        passphrase = args[i + 1]
                        i += 2
                    elif arg == '--force':
                        force = True
                        i += 1
                    else:
                        print(f"Error: Unknown argument '{arg}'", file=sys.stderr)
                        sys.exit(1)
                
                # Validate required fields
                if not cred_type:
                    print("Error: --type is required", file=sys.stderr)
                    sys.exit(1)
                
                if not cred_id:
                    print("Error: --id is required", file=sys.stderr)
                    sys.exit(1)
                
                # Normalize credential type
                type_map = {
                    'username_password': 'username_password',
                    'username-password': 'username_password',
                    'secret_text': 'secret_text',
                    'secret-text': 'secret_text',
                    'ssh_key': 'ssh_key',
                    'ssh-key': 'ssh_key'
                }
                cred_type = type_map.get(cred_type.lower(), cred_type)
                
                # Validate type-specific fields
                if cred_type == 'username_password':
                    if not username or not password:
                        print("Error: --username and --password are required for username_password type", file=sys.stderr)
                        sys.exit(1)
                elif cred_type == 'secret_text':
                    if not secret:
                        print("Error: --secret is required for secret_text type", file=sys.stderr)
                        sys.exit(1)
                elif cred_type == 'ssh_key':
                    if not username:
                        print("Error: --username is required for ssh_key type", file=sys.stderr)
                        sys.exit(1)
                    if not private_key and not private_key_file:
                        print("Error: --private-key or --private-key-file is required for ssh_key type", file=sys.stderr)
                        sys.exit(1)
                
                result = client.create_credential(
                    cred_type=cred_type,
                    cred_id=cred_id,
                    description=description,
                    username=username,
                    password=password,
                    secret=secret,
                    private_key=private_key,
                    private_key_file=private_key_file,
                    passphrase=passphrase,
                    force=force
                )
            
            if result.get('status') == 'success':
                print(f"✅ {result.get('message', 'Credential created successfully')}")
            elif result.get('status') == 'exists':
                print(f"⚠️  {result.get('message', 'Credential already exists')}")
                print("Use --force to overwrite", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"❌ Failed to create credential: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "delete":
            if len(sys.argv) < 4:
                print("Error: credential ID required", file=sys.stderr)
                print("Usage: japi cred delete <credential-id> [--force]", file=sys.stderr)
                sys.exit(1)
            
            cred_id = sys.argv[3]
            force = '--force' in sys.argv
            
            if not force:
                response = input(f"Are you sure you want to delete credential '{cred_id}'? (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    print("Credential deletion cancelled.")
                    sys.exit(0)
            
            result = client.delete_credential(cred_id, force=force)
            
            if result.get('status') == 'success':
                print(f"✅ {result.get('message', 'Credential deleted successfully')}")
            else:
                print(f"❌ Failed to delete credential: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "backup":
            args = sys.argv[3:]
            output_file = "jenkins_credentials_backup.json"
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
                else:
                    print("Error: --file requires a filename", file=sys.stderr)
                    sys.exit(1)
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
                else:
                    print("Error: -f requires a filename", file=sys.stderr)
                    sys.exit(1)
            
            result = client.backup_credentials(output_file)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
            else:
                print(f"❌ Backup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "restore":
            args = sys.argv[3:]
            input_file = None
            force = "--force" in args
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            
            if not input_file:
                # Try to find default backup file in current dir
                if os.path.exists("jenkins_credentials_backup.json"):
                    input_file = "jenkins_credentials_backup.json"
                else:
                    print("Error: Backup file required. Use --file <filename>", file=sys.stderr)
                    sys.exit(1)
            
            if not force:
                response = input(f"Are you sure you want to restore credentials from '{input_file}'? This may skip existing ones unless you use --force. (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    print("Restore cancelled.")
                    sys.exit(0)
                    
            result = client.restore_credentials(input_file, force=force)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                if result.get('failed_count', 0) > 0:
                    print(f"⚠️  {result['failed_count']} credentials failed to restore.")
                if result.get('skipped_count', 0) > 0:
                    print(f"ℹ️  {result['skipped_count']} credentials skipped (already exist). Use --force to overwrite.")
            else:
                print(f"❌ Restore failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        else:
            print(f"Error: Unknown cred subcommand '{subcommand}'", file=sys.stderr)
            print("Usage: japi cred <list|create|delete> [args...]", file=sys.stderr)
            sys.exit(1)

    # Handle user command
    if command == "user":
        if len(sys.argv) < 3:
            print("Error: user subcommand required", file=sys.stderr)
            print("Usage: japi user <list|backup|restore> [args...]", file=sys.stderr)
            print("\nUser management commands:", file=sys.stderr)
            print("  list                    List all users", file=sys.stderr)
            print("  backup                  Backup all users to JSON", file=sys.stderr)
            print("  restore                 Restore users from JSON", file=sys.stderr)
            print("\nBackup/Restore options:", file=sys.stderr)
            print("  --file <file>           Backup file path (default: jenkins_users_backup.json)", file=sys.stderr)
            print("  --password <pass>       (Restore only) Default password for restored users", file=sys.stderr)
            print("  --force                 (Restore only) Overwrite existing users", file=sys.stderr)
            sys.exit(1)

        subcommand = sys.argv[2]
        client = JenkinsClient()

        if subcommand == "list":
            users = client.list_users()
            
            if users:
                print("Jenkins Users:")
                print("=" * 80)
                print(f"{'ID':<25} {'Full Name':<30} {'Email':<25}")
                print("=" * 80)
                for user in users:
                    user_id = user.get('id', 'N/A')
                    full_name = user.get('fullName', 'N/A')
                    if len(full_name) > 28:
                        full_name = full_name[:25] + "..."
                    email = user.get('email', '')
                    if len(email) > 23:
                        email = email[:20] + "..."
                    print(f"{user_id:<25} {full_name:<30} {email:<25}")
                print(f"\nTotal: {len(users)} users")
            else:
                print("No users found.")
            sys.exit(0)

        elif subcommand == "backup":
            args = sys.argv[3:]
            output_file = "jenkins_users_backup.json"
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
                else:
                    print("Error: --file requires a filename", file=sys.stderr)
                    sys.exit(1)
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
                else:
                    print("Error: -f requires a filename", file=sys.stderr)
                    sys.exit(1)
            
            result = client.backup_users(output_file)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
            else:
                print(f"❌ Backup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "restore":
            args = sys.argv[3:]
            input_file = None
            force = "--force" in args
            default_password = "changeme"
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            
            if "--password" in args:
                idx = args.index("--password")
                if idx + 1 < len(args):
                    default_password = args[idx + 1]
            
            if not input_file:
                # Try to find default backup file in current dir
                if os.path.exists("jenkins_users_backup.json"):
                    input_file = "jenkins_users_backup.json"
                else:
                    print("Error: Backup file required. Use --file <filename>", file=sys.stderr)
                    sys.exit(1)
            
            if not force:
                response = input(f"Are you sure you want to restore users from '{input_file}'? (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    print("Restore cancelled.")
                    sys.exit(0)
                    
            result = client.restore_users(input_file, default_password=default_password, force=force)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                if result.get('failed_count', 0) > 0:
                    print(f"⚠️  {result['failed_count']} users failed to restore.")
                if result.get('skipped_count', 0) > 0:
                    print(f"ℹ️  {result['skipped_count']} users skipped (already exist). Use --force to overwrite.")
                print(f"\n💡 Note: Restored users have default password '{default_password}'. Please change it.")
            else:
                print(f"❌ Restore failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        else:
            print(f"Error: Unknown user subcommand '{subcommand}'", file=sys.stderr)
            print("Usage: japi user <list|backup|restore> [args...]", file=sys.stderr)
            sys.exit(1)

    # Handle plugin command
    if command == "plugin":
        if len(sys.argv) < 3:
            print("Error: plugin subcommand required", file=sys.stderr)
            print("Usage: japi plugin <list|install|uninstall|backup|restore> [args...]", file=sys.stderr)
            print("\nPlugin list options:", file=sys.stderr)
            print("  --format <json|csv|txt>  Export format (default: table)", file=sys.stderr)
            print("                           txt = plugins.txt format (name:version) for Docker builds", file=sys.stderr)
            print("  --output <file>          Output file (optional, defaults to stdout)", file=sys.stderr)
            print("\nPlugin backup/restore options:", file=sys.stderr)
            print("  backup --file <file>     Backup plugins (default: plugins_backup.json)", file=sys.stderr)
            print("         --format txt      Use plugins.txt format instead of JSON", file=sys.stderr)
            print("  restore --file <file>    Restore/install plugins from backup file", file=sys.stderr)
            sys.exit(1)

        subcommand = sys.argv[2]
        client = JenkinsClient()

        if subcommand == "list":
            # Parse format option
            args = sys.argv[3:]
            output_format = None
            output_file = None

            if '--format' in args:
                format_idx = args.index('--format')
                if format_idx + 1 < len(args):
                    output_format = args[format_idx + 1].lower()
                    args = args[:format_idx] + args[format_idx + 2:]
                else:
                    print("Error: --format requires a value (json, csv, or txt)", file=sys.stderr)
                    sys.exit(1)

            if '--output' in args or '-o' in args:
                output_flag = '--output' if '--output' in args else '-o'
                output_idx = args.index(output_flag)
                if output_idx + 1 < len(args):
                    output_file = args[output_idx + 1]
                    args = args[:output_idx] + args[output_idx + 2:]
                else:
                    print("Error: --output requires a filename", file=sys.stderr)
                    sys.exit(1)

            plugins = client.list_plugins()
            
            if output_format == 'json':
                import json
                output_data = json.dumps(plugins, indent=2)
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(output_data)
                    print(f"✅ Plugins exported to {output_file} (JSON format)")
                else:
                    print(output_data)
                sys.exit(0)
            elif output_format == 'csv':
                import csv
                if not plugins:
                    print("No plugins found.")
                    sys.exit(0)
                
                # Get all possible fields from plugins
                fieldnames = ['name', 'version', 'enabled', 'display_name', 'description', 'url']
                
                if output_file:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for plugin in plugins:
                            row = {field: plugin.get(field, '') for field in fieldnames}
                            row['enabled'] = 'Yes' if row.get('enabled', True) else 'No'
                            writer.writerow(row)
                    print(f"✅ Plugins exported to {output_file} (CSV format)")
                else:
                    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                    writer.writeheader()
                    for plugin in plugins:
                        row = {field: plugin.get(field, '') for field in fieldnames}
                        row['enabled'] = 'Yes' if row.get('enabled', True) else 'No'
                        writer.writerow(row)
                sys.exit(0)
            elif output_format == 'txt':
                # plugins.txt format: name:version per line
                if not plugins:
                    print("No plugins found.")
                    sys.exit(0)
                
                lines = []
                for plugin in plugins:
                    name = plugin.get('name', '')
                    version = plugin.get('version', '')
                    if name:
                        lines.append(f"{name}:{version}")
                
                output_data = '\n'.join(sorted(lines))
                if output_file:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(output_data)
                    print(f"✅ Plugins exported to {output_file} (plugins.txt format)")
                else:
                    print(output_data)
                sys.exit(0)
            else:
                # Default table format
                if plugins:
                    print("Installed Jenkins Plugins:")
                    print("=" * 100)
                    print(f"{'Name':<30} {'Version':<20} {'Enabled':<10} {'Display Name':<40}")
                    print("=" * 100)
                    for plugin in plugins:
                        enabled = "Yes" if plugin.get('enabled', True) else "No"
                        display_name = plugin.get('display_name', plugin.get('name', 'N/A'))
                        if len(display_name) > 38:
                            display_name = display_name[:35] + "..."
                        print(f"{plugin.get('name', 'N/A'):<30} {plugin.get('version', 'N/A'):<20} {enabled:<10} {display_name:<40}")
                else:
                    print("No plugins found.")
                sys.exit(0)

        elif subcommand == "install":
            if len(sys.argv) < 4:
                print("Error: plugin name(s) required", file=sys.stderr)
                print("Usage: japi plugin install <plugin1> [plugin2] ...", file=sys.stderr)
                sys.exit(1)

            plugin_names = sys.argv[3:]
            result = client.install_plugins(plugin_names, block=False)

            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                print("Note: Plugin installation may take some time. Check Jenkins for installation status.")
            else:
                print(f"❌ Failed to install plugins: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "uninstall":
            if len(sys.argv) < 4:
                print("Error: plugin name(s) required", file=sys.stderr)
                print("Usage: japi plugin uninstall <plugin1> [plugin2] ...", file=sys.stderr)
                sys.exit(1)

            plugin_names = sys.argv[3:]
            result = client.uninstall_plugins(plugin_names)

            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                print("Note: Jenkins restart may be required for uninstallation to complete.")
            else:
                print(f"❌ Failed to uninstall plugins: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "backup":
            args = sys.argv[3:]
            output_file = "plugins_backup.json"
            format_type = "json"
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    output_file = args[idx + 1]
            
            if "--format" in args:
                idx = args.index("--format")
                if idx + 1 < len(args):
                    format_type = args[idx + 1].lower()
                    if format_type == 'txt':
                        if not output_file.endswith('.txt'):
                            output_file = output_file.replace('.json', '.txt') if output_file.endswith('.json') else output_file + '.txt'
            
            result = client.backup_plugins(output_file, format_type)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                if format_type == 'txt':
                    print(f"💡 This file can be used with jenkins-plugin-cli or in Dockerfile:")
                    print(f"   jenkins-plugin-cli --plugin-file {output_file}")
            else:
                print(f"❌ Backup failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        elif subcommand == "restore":
            args = sys.argv[3:]
            input_file = None
            block = "--wait" in args or "--block" in args
            
            if "--file" in args:
                idx = args.index("--file")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            elif "-f" in args:
                idx = args.index("-f")
                if idx + 1 < len(args):
                    input_file = args[idx + 1]
            
            if not input_file:
                # Try to find default backup files
                for default_file in ["plugins_backup.json", "plugins.txt", "plugins_backup.txt"]:
                    if os.path.exists(default_file):
                        input_file = default_file
                        break
                
                if not input_file:
                    print("Error: Backup file required. Use --file <filename>", file=sys.stderr)
                    sys.exit(1)
            
            result = client.restore_plugins(input_file, block=block)
            if result['status'] == 'success':
                print(f"✅ {result['message']}")
                print("💡 Note: Jenkins restart may be required to complete plugin installation.")
            else:
                print(f"❌ Restore failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            sys.exit(0)

        else:
            print(f"Error: Unknown plugin subcommand '{subcommand}'", file=sys.stderr)
            print("Usage: japi plugin <list|install|uninstall|backup|restore> [args...]", file=sys.stderr)
            sys.exit(1)

    # Try to find and execute script
    args = sys.argv[2:]
    script_path = find_script(command)
    
    if script_path is not None:
        exit_code = execute_script(script_path, args)
        sys.exit(exit_code)
    
    # Command not found
    print(f"Error: command '{command}' not found", file=sys.stderr)
    print(f"Expected bundled script: japi-{command}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
