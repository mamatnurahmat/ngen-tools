"""Configuration management for ngen-gitops."""
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
            "default_org": os.getenv("GIT_DEFAULT_ORG", "loyaltoid")
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


def get_bitbucket_credentials() -> Dict[str, str]:
    """Get Bitbucket credentials from config.
    
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
    
    if not username or not app_password:
        raise ValueError(
            "Bitbucket credentials not configured. "
            f"Please update {ENV_FILE} or set BITBUCKET_USER and BITBUCKET_APP_PASSWORD environment variables."
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
