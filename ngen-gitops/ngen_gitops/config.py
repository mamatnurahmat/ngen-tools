"""Configuration management for ngen-gitops."""
import netrc
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


CONFIG_DIR = Path.home() / ".ngen-gitops"
ENV_FILE = CONFIG_DIR / ".env"


def ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_default_env():
    """Create default .env file with commented sample values."""
    ensure_config_dir()
    default_content = """# ngen-gitops Configuration
# Uncomment and fill in the values below

# Bitbucket Credentials
# BITBUCKET_USER=your-username
# BITBUCKET_APP_PASSWORD=your-app-password
# BITBUCKET_ORG=loyaltoid

# Server Settings
# SERVER_HOST=0.0.0.0
# SERVER_PORT=8080

# Git Settings
# GIT_DEFAULT_REMOTE=bitbucket.org
# GIT_DEFAULT_ORG=loyaltoid
# DEFAULT_IMAGE_REGISTRY=loyaltolpi

# Notifications (Microsoft Teams)
# TEAMS_WEBHOOK=https://your-org.webhook.office.com/webhookb2/...
"""
    with open(ENV_FILE, 'w') as f:
        f.write(default_content)
    ENV_FILE.chmod(0o600)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables and ~/.ngen-gitops/.env.
    
    Prioritizes environment variables over .env file.
    Creates default .env sample file if it doesn't exist.
    
    Returns:
        dict: Configuration dictionary
    """
    ensure_config_dir()
    
    # Create default .env if it doesn't exist
    if not ENV_FILE.exists():
        create_default_env()
        print(f"ℹ️  Created sample config at {ENV_FILE}")
        print(f"   Please update with your credentials")
    
    # Load .env file into environment
    load_dotenv(dotenv_path=ENV_FILE)
    
    # Build config dictionary from environment variables
    config = {
        "bitbucket": {
            "username": os.getenv("BITBUCKET_USER", ""),
            "app_password": os.getenv("BITBUCKET_APP_PASSWORD", ""),
            "organization": os.getenv("BITBUCKET_ORG", "loyaltoid")
        },
        "server": {
            "host": os.getenv("SERVER_HOST", "0.0.0.0"),
            "port": int(os.getenv("SERVER_PORT", "8080"))
        },
        "git": {
            "default_remote": os.getenv("GIT_DEFAULT_REMOTE", "bitbucket.org"),
            "default_org": os.getenv("GIT_DEFAULT_ORG", "loyaltoid"),
            "default_image_registry": os.getenv("DEFAULT_IMAGE_REGISTRY", "loyaltolpi")
        },
        "notifications": {
            "teams_webhook": os.getenv("TEAMS_WEBHOOK", "")
        }
    }
    
    return config


def get_config_file_path() -> str:
    """Get the config file path.
    
    Returns:
        str: Absolute path to config file (.env)
    """
    return str(ENV_FILE)


def config_exists() -> bool:
    """Check if config file exists.
    
    Returns:
        bool: True if config exists
    """
    return ENV_FILE.exists()


def get_netrc_credentials(machine: str = "bitbucket.org") -> Optional[Dict[str, str]]:
    """Get credentials from ~/.netrc file.
    
    Args:
        machine: Machine name to look up (default: bitbucket.org)
    
    Returns:
        dict: Dictionary with username and password, or None if not found
    """
    netrc_path = Path.home() / ".netrc"
    
    if not netrc_path.exists():
        return None
    
    try:
        nrc = netrc.netrc(str(netrc_path))
        auth = nrc.authenticators(machine)
        
        if auth:
            username, _, password = auth
            return {
                'username': username,
                'password': password
            }
    except (netrc.NetrcParseError, OSError) as e:
        # Silently ignore netrc errors
        pass
    
    return None


def get_bitbucket_credentials() -> Dict[str, str]:
    """Get Bitbucket credentials from config.
    
    Priority:
    1. Environment variables (BITBUCKET_USER, BITBUCKET_APP_PASSWORD)
    2. .env file (~/.ngen-gitops/.env)
    3. ~/.netrc file (machine bitbucket.org)
    
    Returns:
        dict: Dictionary with username, app_password, and organization
    
    Raises:
        ValueError: If credentials are not configured
    """
    config = load_config()
    bitbucket = config.get('bitbucket', {})
    
    username = bitbucket.get('username', '')
    app_password = bitbucket.get('app_password', '')
    organization = bitbucket.get('organization', 'loyaltoid')
    
    # Fallback to netrc if credentials not in config
    if not username or not app_password:
        netrc_creds = get_netrc_credentials('bitbucket.org')
        if netrc_creds:
            username = username or netrc_creds['username']
            app_password = app_password or netrc_creds['password']
    
    if not username or not app_password:
        raise ValueError(
            "Bitbucket credentials not configured. "
            f"Please update {ENV_FILE}, set BITBUCKET_USER/BITBUCKET_APP_PASSWORD environment variables, "
            "or configure ~/.netrc with 'machine bitbucket.org'."
        )
    
    return {
        'username': username,
        'app_password': app_password,
        'organization': organization
    }


def get_server_config() -> Dict[str, Any]:
    """Get server configuration.
    
    Returns:
        dict: Dictionary with host and port
    """
    config = load_config()
    return config.get('server', {"host": "0.0.0.0", "port": 8080})


def get_git_config() -> Dict[str, str]:
    """Get git configuration.
    
    Returns:
        dict: Dictionary with default_remote and default_org
    """
    config = load_config()
    git_config = config.get('git', {})
    return {
        'default_remote': git_config.get('default_remote', 'bitbucket.org'),
        'default_org': git_config.get('default_org', 'loyaltoid')
    }


def get_default_remote() -> str:
    """Get default git remote.
    
    Returns:
        str: Default remote (e.g., 'bitbucket.org', 'github.com', 'gitlab.com')
    """
    git_config = get_git_config()
    return git_config['default_remote']


def get_default_org() -> str:
    """Get default organization.
    
    Returns:
        str: Default organization name
    """
    git_config = get_git_config()
    return git_config['default_org']


def get_teams_webhook() -> Optional[str]:
    """Get Teams webhook URL.
    
    Returns:
        Optional[str]: Teams webhook URL if configured, None otherwise
    """
    config = load_config()
    notifications = config.get('notifications', {})
    webhook = notifications.get('teams_webhook', '')
    return webhook if webhook else None


def get_current_user() -> str:
    """Get current user for attribution.
    
    Returns:
        str: User name (from git config or system user)
    """
    # Try git config first
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'config', 'user.name'], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
        
    # Fallback to system user
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return "unknown"


def get_default_image_registry() -> str:
    """Get default image registry.
    
    Returns:
        str: Default image registry (default: loyaltolpi)
    """
    config = load_config()
    return config.get('git', {}).get('default_image_registry', 'loyaltolpi')
