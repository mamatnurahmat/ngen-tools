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
        print("\nngen-j is a Jenkins API management CLI tool.", file=sys.stderr)
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
        print("\nScript commands:", file=sys.stderr)
        print("  <script-name>     Execute bundled script", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  ngen-j --version", file=sys.stderr)
        print("  ngen-j jobs", file=sys.stderr)
        print("  ngen-j job my-job", file=sys.stderr)
        print("  ngen-j job --last-success", file=sys.stderr)
        print("  ngen-j job --last-failure", file=sys.stderr)
        print("  ngen-j build my-job", file=sys.stderr)
        print("  ngen-j build my-job --param REF_NAME=develop", file=sys.stderr)
        print("  ngen-j build my-job --param=REF_NAME=develop", file=sys.stderr)
        print("  ngen-j log my-job 42", file=sys.stderr)
        print("  ngen-j get-xml my-job", file=sys.stderr)
        print("  ngen-j create my-job job.xml", file=sys.stderr)
        print("  ngen-j delete my-job", file=sys.stderr)
        print("  ngen-j delete my-job --force", file=sys.stderr)
        sys.exit(0)
    
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
        print("  job --last-success Get last 10 successful jobs", file=sys.stderr)
        print("  job --last-failure Get last 10 failed jobs", file=sys.stderr)
        print("  build <job-name>  Trigger a build", file=sys.stderr)
        print("  log <name> <num>  Get build console output", file=sys.stderr)
        print("  get-xml <name>    Get job configuration XML", file=sys.stderr)
        print("  create <name> <xml> Create/update job from XML", file=sys.stderr)
        print("  delete <name>     Delete a job", file=sys.stderr)
        print("\nScript commands:", file=sys.stderr)
        print("  <script-name>     Execute bundled script", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  ngen-j --version", file=sys.stderr)
        print("  ngen-j jobs", file=sys.stderr)
        print("  ngen-j job my-job", file=sys.stderr)
        print("  ngen-j job --last-success", file=sys.stderr)
        print("  ngen-j job --last-failure", file=sys.stderr)
        print("  ngen-j build my-job", file=sys.stderr)
        print("  ngen-j build my-job --param REF_NAME=develop", file=sys.stderr)
        print("  ngen-j build my-job --param=REF_NAME=develop", file=sys.stderr)
        print("  ngen-j log my-job 42", file=sys.stderr)
        print("  ngen-j get-xml my-job", file=sys.stderr)
        print("  ngen-j create my-job job.xml", file=sys.stderr)
        print("  ngen-j delete my-job", file=sys.stderr)
        print("  ngen-j delete my-job --force", file=sys.stderr)
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
            print("Usage: ngen-j job <name>", file=sys.stderr)
            print("       ngen-j job --last-success", file=sys.stderr)
            print("       ngen-j job --last-failure", file=sys.stderr)
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
            print("Usage: ngen-j build <job-name> [--param KEY1=VALUE1 KEY2=VALUE2 ...] or [--param=KEY=VALUE ...]", file=sys.stderr)
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
            print("Usage: ngen-j create <job-name> <xml-file> [--force]", file=sys.stderr)
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
            print("Usage: ngen-j delete <job-name> [--force]", file=sys.stderr)
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
            print("Usage: ngen-j get-xml <job-name>", file=sys.stderr)
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
            print("Usage: ngen-j log <job-name> <build-number>", file=sys.stderr)
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
