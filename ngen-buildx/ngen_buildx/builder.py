"""Docker Buildx command builder for ngen-buildx."""
import json
import os
import subprocess
from typing import Dict, Any, Optional, List

from .config import load_config, load_build_args


class BuildxError(Exception):
    """Exception raised for buildx errors."""
    pass


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
    extra_args: Optional[List[str]] = None
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
        extra_args: Additional build arguments
    
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
    
    # Fetch cicd.json from repository
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
        if registry_url:
            cmd.extend(["-t", f"{registry_url}/{image_name}:{ref}"])
        else:
            cmd.extend(["-t", f"{image_name}:{ref}"])
    
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
    extra_args: Optional[List[str]] = None
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
        extra_args: Additional build arguments
    
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
            extra_args=extra_args
        )
        
        cmd = build_result["command"]
        command_str = build_result["command_str"]
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "command": command_str,
                "cicd_config": build_result["cicd_config"],
                "message": "Dry run - command not executed"
            }
        
        # Execute the command
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
            return {
                "success": True,
                "command": command_str,
                "cicd_config": build_result["cicd_config"],
                "message": "Build completed successfully"
            }
        else:
            return {
                "success": False,
                "command": command_str,
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

