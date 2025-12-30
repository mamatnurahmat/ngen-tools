"""Docker Buildx command builder for ngen-buildx."""
import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, Optional, List

from .config import load_config, load_build_args, get_teams_webhook


class BuildxError(Exception):
    """Exception raised for buildx errors."""
    pass


def send_teams_notification(
    image_tag: str,
    repo: str,
    ref: str,
    success: bool,
    message: str = "",
    cicd_config: Optional[Dict[str, Any]] = None
) -> bool:
    """Send notification to Microsoft Teams webhook.
    
    Args:
        image_tag: Docker image tag that was built
        repo: Repository name
        ref: Branch or tag reference
        success: Whether build was successful
        message: Additional message to include
        cicd_config: CICD configuration dict
    
    Returns:
        bool: True if notification sent successfully
    """
    webhook_url = get_teams_webhook()
    
    if not webhook_url:
        return False
    
    # Create Teams MessageCard
    status_emoji = "✅" if success else "❌"
    status_text = "Build Successful" if success else "Build Failed"
    theme_color = "00FF00" if success else "FF0000"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build facts list (limit to essential info to avoid 400 errors)
    facts = [
        {"name": "Repository", "value": repo},
        {"name": "Reference", "value": ref},
        {"name": "Image", "value": image_tag or "N/A"},
        {"name": "Timestamp", "value": timestamp},
    ]
    
    # Add only key CICD config fields
    if cicd_config:
        if cicd_config.get("PROJECT"):
            facts.append({"name": "Project", "value": str(cicd_config.get("PROJECT"))})
        if cicd_config.get("CLUSTER"):
            facts.append({"name": "Cluster", "value": str(cicd_config.get("CLUSTER"))})
    
    # MessageCard payload (Office 365 Connector format)
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": theme_color,
        "summary": f"{status_emoji} ngen-buildx: {status_text}",
        "sections": [{
            "activityTitle": f"{status_emoji} Docker Build {status_text}",
            "activitySubtitle": f"Repository: {repo} | Ref: {ref}",
            "facts": facts,
            "markdown": True
        }]
    }
    
    if message:
        payload["text"] = message
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"⚠️  Failed to send Teams notification: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Failed to send Teams notification: {e}")
        return False


def get_git_info() -> Dict[str, str]:
    """Get current git repository info (repo name and branch/ref).
    
    Returns:
        dict: Dictionary with 'repo' and 'ref' keys
    
    Raises:
        BuildxError: If not in a git repository or git command fails
    """
    # Get current branch or tag
    try:
        # Try to get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        ref = result.stdout.strip()
        
        # If HEAD (detached), try to get tag name
        if ref == "HEAD":
            result = subprocess.run(
                ["git", "describe", "--tags", "--exact-match"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                ref = result.stdout.strip()
            else:
                # Fallback to short commit hash
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                ref = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise BuildxError(f"Not in a git repository or git command failed: {e.stderr}")
    
    # Get repository name from remote URL
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        remote_url = result.stdout.strip()
        
        # Extract repo name from URL
        # Supports: https://bitbucket.org/org/repo.git or git@bitbucket.org:org/repo.git
        if remote_url.endswith('.git'):
            remote_url = remote_url[:-4]
        
        # Get last part of URL as repo name
        repo = remote_url.split('/')[-1]
        
    except subprocess.CalledProcessError:
        # Fallback: use current directory name
        import os
        repo = os.path.basename(os.getcwd())
    
    return {
        "repo": repo,
        "ref": ref
    }


def fetch_cicd_config(repo: str, ref: str, org: Optional[str] = None) -> Dict[str, Any]:
    """Fetch cicd/cicd.json from repository using gitops get-file.
    
    Args:
        repo: Repository name
        ref: Branch or tag reference
        org: Organization (optional, uses default)
    
    Returns:
        dict: Parsed cicd.json content
    
    Raises:
        BuildxError: If fetching fails
    """
    cmd = ["gitops", "get-file", repo, ref, "cicd/cicd.json"]
    
    if org:
        cmd.extend(["--org", org])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise BuildxError(f"Failed to fetch cicd.json: {e.stderr}")
    except json.JSONDecodeError as e:
        raise BuildxError(f"Invalid JSON in cicd.json: {e}")


def load_local_cicd_config(cicd_path: str = "cicd/cicd.json") -> Dict[str, Any]:
    """Load cicd.json from local file path.
    
    Args:
        cicd_path: Path to cicd.json file (default: cicd/cicd.json)
    
    Returns:
        dict: Parsed cicd.json content
    
    Raises:
        BuildxError: If loading fails
    """
    from pathlib import Path
    
    path = Path(cicd_path)
    
    if not path.exists():
        raise BuildxError(f"CICD config file not found: {cicd_path}")
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise BuildxError(f"Invalid JSON in {cicd_path}: {e}")
    except Exception as e:
        raise BuildxError(f"Failed to read {cicd_path}: {e}")


def get_short_commit_id(repo: str, ref: str, org: Optional[str] = None) -> str:
    """Get short commit ID (6 characters) for a branch/tag.
    
    Args:
        repo: Repository name
        ref: Branch or tag reference
        org: Organization (optional)
    
    Returns:
        str: 6-character short commit ID
    
    Raises:
        BuildxError: If fetching fails
    """
    cmd = ["gitops", "logs", repo, ref, "--last", "--version"]
    
    if org:
        cmd.extend(["--org", org])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        # Get first 6 characters of commit hash
        commit_hash = result.stdout.strip()
        return commit_hash[:6] if commit_hash else ref
    except subprocess.CalledProcessError:
        # Fallback to ref if can't get commit
        return ref


def get_local_short_commit_id() -> str:
    """Get short commit ID (6 characters) from local git repository.
    
    Returns:
        str: 6-character short commit ID
    
    Raises:
        BuildxError: If not in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=6", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise BuildxError(f"Failed to get local commit ID: {e.stderr}")


def is_tag_ref(ref: str) -> bool:
    """Check if ref looks like a version tag (e.g., v1.0.0, 1.2.3).
    
    Args:
        ref: Branch or tag reference
    
    Returns:
        bool: True if ref looks like a tag
    """
    import re
    # Match common tag patterns: v1.0.0, 1.2.3, release-1.0, etc.
    tag_patterns = [
        r'^v?\d+\.\d+\.\d+',  # v1.0.0 or 1.0.0
        r'^v?\d+\.\d+',       # v1.0 or 1.0
        r'^release[-_]',      # release-xxx
        r'^tag[-_]',          # tag-xxx
    ]
    for pattern in tag_patterns:
        if re.match(pattern, ref, re.IGNORECASE):
            return True
    return False


def get_env_from_ref(ref: str) -> str:
    """Get environment name from git reference.
    
    Args:
        ref: Branch or tag reference
    
    Returns:
        str: Environment name (develop, staging, or production)
    """
    # Check if ref starts with v or V (version tag = production)
    if ref.lower().startswith('v'):
        return "production"
    
    # Map common branch names to environments
    ref_lower = ref.lower()
    if ref_lower in ['develop', 'development', 'dev']:
        return "develop"
    elif ref_lower in ['staging', 'stage']:
        return "staging"
    elif ref_lower in ['master', 'main', 'production', 'prod']:
        return "production"
    
    # Default to the ref itself (for custom branches like 'develop', 'staging')
    return ref


def check_image_exists(image_tag: str) -> bool:
    """Check if Docker image already exists in registry.
    
    Args:
        image_tag: Full image tag (e.g., registry/image:tag)
    
    Returns:
        bool: True if image exists
    """
    try:
        result = subprocess.run(
            ["docker", "manifest", "inspect", image_tag],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_build_arg_value(value: str, cicd_config: Dict[str, Any], 
                            refs: str, env_config: Dict[str, Any]) -> str:
    """Resolve build argument value by substituting variables.
    
    Args:
        value: The value template (e.g., "$IMAGE", "$REGISTRY01_URL")
        cicd_config: Configuration from cicd.json
        refs: The git reference (branch/tag)
        env_config: Environment configuration
    
    Returns:
        str: Resolved value
    """
    # Map of variable substitutions
    # Note: Keys are sorted by length (longest first) to prevent partial matches
    # e.g., $PORT2 should be replaced before $PORT
    substitutions = {
        "$REGISTRY01_URL": env_config.get("registry", {}).get("registry01_url", ""),
        "$DEPLOYMENT": cicd_config.get("DEPLOYMENT", ""),
        "$NODETYPE": cicd_config.get("NODETYPE", ""),
        "$PROJECT": cicd_config.get("PROJECT", ""),
        "$CLUSTER": cicd_config.get("CLUSTER", ""),
        "$IMAGE": cicd_config.get("IMAGE", ""),
        "$PORT2": cicd_config.get("PORT2", ""),
        "$PORT": cicd_config.get("PORT", ""),
        "$REFS": refs,
    }
    
    result = value
    # Sort by key length (longest first) to prevent partial matches
    for var in sorted(substitutions.keys(), key=len, reverse=True):
        result = result.replace(var, str(substitutions[var]))
    
    return result


def get_netrc_credentials(machine: str = "bitbucket.org") -> Dict[str, str]:
    """Get credentials from ~/.netrc file.
    
    Args:
        machine: Machine name to look up
    
    Returns:
        dict: Dictionary with username and password
    
    Raises:
        BuildxError: If credentials not found
    """
    import netrc
    from pathlib import Path
    
    netrc_path = Path.home() / ".netrc"
    
    if not netrc_path.exists():
        raise BuildxError(f"~/.netrc file not found. Please create it with {machine} credentials.")
    
    try:
        nrc = netrc.netrc(str(netrc_path))
        auth = nrc.authenticators(machine)
        
        if auth:
            username, _, password = auth
            return {
                'username': username,
                'password': password
            }
        else:
            raise BuildxError(f"No credentials found for {machine} in ~/.netrc")
    except netrc.NetrcParseError as e:
        raise BuildxError(f"Error parsing ~/.netrc: {e}")


def build_docker_command(
    repo: str,
    ref: str,
    context_path: Optional[str] = None,
    dockerfile: str = "Dockerfile",
    tag: Optional[str] = None,
    push: bool = False,
    platform: Optional[str] = None,
    org: Optional[str] = None,
    remote: bool = True,
    cicd_path: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    json_mode: bool = False
) -> Dict[str, Any]:
    """Build docker buildx command with all arguments.
    
    Args:
        repo: Repository name
        ref: Branch or tag reference
        context_path: Build context path (default: remote git URL)
        dockerfile: Dockerfile path (default: "Dockerfile")
        tag: Image tag (optional, uses IMAGE from cicd.json if not specified)
        push: Whether to push the image
        platform: Target platform (e.g., "linux/amd64,linux/arm64")
        org: Organization (optional)
        remote: If True, build from remote git URL (default: True)
        cicd_path: Local path to cicd.json (if provided, uses local file instead of fetching from repo)
        extra_args: Additional build arguments
        json_mode: If True, suppress non-JSON output for piping to jq
    
    Returns:
        dict: Result with 'command' list and 'command_str' string
    
    Raises:
        BuildxError: If building command fails
    """
    # Load configurations
    env_config = load_config()
    build_args = load_build_args()
    builder_config = env_config.get("builder", {})
    gitops_config = env_config.get("gitops", {})
    
    # Load cicd.json - either from local file or from remote repository
    if cicd_path:
        cicd_config = load_local_cicd_config(cicd_path)
        if not json_mode:
            print(f"📋 Using local CICD config: {cicd_path}")
    else:
        cicd_config = fetch_cicd_config(repo, ref, org)
    
    # Determine context path
    if context_path is None and remote:
        # Use remote git URL as context
        creds = get_netrc_credentials("bitbucket.org")
        git_org = org or gitops_config.get("org", "loyaltoid")
        context_path = f"https://{creds['username']}:{creds['password']}@bitbucket.org/{git_org}/{repo}.git#{ref}"
    elif context_path is None:
        context_path = "."
    
    # Start building command
    cmd = ["docker", "buildx", "build"]
    
    # Builder name
    builder_name = builder_config.get("name", "container-builder")
    cmd.extend(["--builder", builder_name])
    
    # SBOM and attestation
    cmd.append("--sbom=true")
    cmd.append("--no-cache")
    cmd.append("--attest")
    cmd.append("type=provenance,mode=max")
    
    # Resource limits
    memory = builder_config.get("memory", "4g")
    cpu_period = builder_config.get("cpu_period", "100000")
    cpu_quota = builder_config.get("cpu_quota", "200000")
    
    cmd.extend(["--memory", memory])
    cmd.extend(["--cpu-period", cpu_period])
    cmd.extend(["--cpu-quota", cpu_quota])
    
    # Progress
    cmd.append("--progress=plain")
    
    # Build arguments from arg.json
    for arg_name, arg_value in build_args.items():
        resolved_value = resolve_build_arg_value(arg_value, cicd_config, ref, env_config)
        cmd.extend(["--build-arg", f"{arg_name}={resolved_value}"])
    
    # Platform
    if platform:
        cmd.extend(["--platform", platform])
    
    # Tag
    if tag:
        cmd.extend(["-t", tag])
    elif cicd_config.get("IMAGE"):
        registry_url = env_config.get("registry", {}).get("registry01_url", "")
        image_name = cicd_config.get("IMAGE", "")
        
        # Determine image tag: use commit ID for branches, keep tag name for version tags
        if is_tag_ref(ref):
            image_tag = ref
        elif cicd_path:
            # Local build: use local git commit ID
            image_tag = get_local_short_commit_id()
        else:
            # Remote build: get commit ID from remote repo
            image_tag = get_short_commit_id(repo, ref, org)
        
        if registry_url:
            cmd.extend(["-t", f"{registry_url}/{image_name}:{image_tag}"])
        else:
            cmd.extend(["-t", f"{image_name}:{image_tag}"])
    
    # Push (default True for remote builds)
    if push or remote:
        cmd.append("--push")
    
    # Dockerfile (only for local builds)
    if not remote and not context_path.startswith("https://"):
        cmd.extend(["-f", dockerfile])
    
    # Extra arguments
    if extra_args:
        cmd.extend(extra_args)
    
    # Context path
    cmd.append(context_path)
    
    # Format command string for display (mask credentials)
    display_cmd = cmd.copy()
    if remote and context_path and "@bitbucket.org" in context_path:
        # Mask credentials in context for display
        masked_context = context_path.split("@")[1] if "@" in context_path else context_path
        display_cmd[-1] = f"https://***:***@{masked_context}"
    
    command_str = format_command_for_display(display_cmd)
    
    return {
        "command": cmd,
        "command_str": command_str,
        "cicd_config": cicd_config,
        "builder_config": builder_config
    }


def format_command_for_display(cmd: List[str]) -> str:
    """Format command list as a readable multi-line string.
    
    Args:
        cmd: Command as list of strings
    
    Returns:
        str: Formatted command string
    """
    lines = []
    current_line = ""
    
    for i, part in enumerate(cmd):
        if part.startswith("--") or part.startswith("-f") or part.startswith("-t"):
            if current_line:
                lines.append(current_line)
            current_line = f"  {part}"
        elif current_line.startswith("  --") or current_line.startswith("  -"):
            current_line += f" {part}"
        else:
            if current_line:
                current_line += f" {part}"
            else:
                current_line = part
    
    if current_line:
        lines.append(current_line)
    
    return " \\\n".join(lines)


def execute_build(
    repo: str,
    ref: str,
    context_path: Optional[str] = None,
    dockerfile: str = "Dockerfile",
    tag: Optional[str] = None,
    push: bool = False,
    platform: Optional[str] = None,
    org: Optional[str] = None,
    dry_run: bool = False,
    remote: bool = True,
    rebuild: bool = False,
    cicd_path: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    json_mode: bool = False
) -> Dict[str, Any]:
    """Execute docker buildx build command.
    
    Args:
        repo: Repository name
        ref: Branch or tag reference
        context_path: Build context path (None = auto-detect based on remote flag)
        dockerfile: Dockerfile path
        tag: Image tag
        push: Whether to push the image
        platform: Target platform
        org: Organization
        dry_run: If True, only show command without executing
        remote: If True, build from remote git URL (default: True)
        rebuild: If True, force rebuild even if image exists
        cicd_path: Local path to cicd.json (for local builds)
        extra_args: Additional build arguments
        json_mode: If True, suppress non-JSON output for piping to jq
    
    Returns:
        dict: Result with success status and output
    """
    try:
        build_result = build_docker_command(
            repo=repo,
            ref=ref,
            context_path=context_path,
            dockerfile=dockerfile,
            tag=tag,
            push=push,
            platform=platform,
            org=org,
            remote=remote,
            cicd_path=cicd_path,
            extra_args=extra_args,
            json_mode=json_mode
        )
        
        cmd = build_result["command"]
        command_str = build_result["command_str"]
        cicd_config = build_result["cicd_config"]
        
        # Extract image tag from command to check if exists
        image_tag = None
        for i, arg in enumerate(cmd):
            if arg == "-t" and i + 1 < len(cmd):
                image_tag = cmd[i + 1]
                break
        
        # Calculate IMAGE, DEPLOY, and NS for JSON output
        image_name = cicd_config.get("IMAGE", "")
        deploy_name = cicd_config.get("DEPLOYMENT", "")
        project_name = cicd_config.get("PROJECT", "")
        env_name = get_env_from_ref(ref)
        namespace = f"{env_name}-{project_name}" if project_name else env_name
        
        if dry_run:
            # Check image existence for dry run info
            image_exists = check_image_exists(image_tag) if image_tag else False
            return {
                "success": True,
                "dry_run": True,
                "command": command_str,
                "IMAGE": image_name,
                "DEPLOY": deploy_name,
                "NS": namespace,
                "cicd_config": cicd_config,
                "image_tag": image_tag,
                "image_exists": image_exists,
                "message": "Dry run - command not executed"
            }
        
        # Check if image already exists (unless rebuild is forced)
        if not rebuild and image_tag:
            if not json_mode:
                print(f"🔍 Checking if image exists: {image_tag}")
            if check_image_exists(image_tag):
                return {
                    "success": True,
                    "skipped": True,
                    "IMAGE": image_name,
                    "DEPLOY": deploy_name,
                    "NS": namespace,
                    "image_tag": image_tag,
                    "cicd_config": cicd_config,
                    "message": f"Image already exists: {image_tag}. Use --rebuild to force rebuild."
                }
            else:
                if not json_mode:
                    print(f"   Image not found, proceeding with build...")
        elif rebuild:
            if not json_mode:
                print(f"🔄 Rebuild mode enabled, skipping image check")
        
        # Execute the command
        if not json_mode:
            print(f"🚀 Executing build command...")
            print(f"{'=' * 60}")
            print(command_str)
            print(f"{'=' * 60}")
        
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            # Send success notification
            send_teams_notification(
                image_tag=image_tag,
                repo=repo,
                ref=ref,
                success=True,
                cicd_config=build_result["cicd_config"]
            )
            return {
                "success": True,
                "command": command_str,
                "IMAGE": image_name,
                "DEPLOY": deploy_name,
                "NS": namespace,
                "image_tag": image_tag,
                "cicd_config": cicd_config,
                "message": "Build completed successfully"
            }
        else:
            # Send failure notification
            send_teams_notification(
                image_tag=image_tag,
                repo=repo,
                ref=ref,
                success=False,
                message=f"Exit code: {result.returncode}",
                cicd_config=build_result["cicd_config"]
            )
            return {
                "success": False,
                "command": command_str,
                "IMAGE": image_name,
                "DEPLOY": deploy_name,
                "NS": namespace,
                "image_tag": image_tag,
                "cicd_config": cicd_config,
                "message": f"Build failed with exit code {result.returncode}"
            }
            
    except BuildxError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Build error: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Unexpected error: {e}"
        }


