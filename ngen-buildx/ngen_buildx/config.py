"""Configuration management for ngen-buildx."""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


CONFIG_DIR = Path.home() / ".ngen-buildx"
ENV_FILE = CONFIG_DIR / ".env"
ARG_FILE = CONFIG_DIR / "arg.json"


def ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_default_env():
    """Create default .env file with sample values."""
    ensure_config_dir()
    default_content = """# ngen-buildx Configuration
# Uncomment and fill in the values below

# Builder Configuration
BUILDER_NAME=mybuilder
DEFAULT_MEMORY=4g
DEFAULT_CPU_PERIOD=100000
DEFAULT_CPU_QUOTA=200000

# Registry Configuration
REGISTRY01_URL=registry.example.com

# GitOps Settings (optional, uses ngen-gitops defaults if not set)
# BITBUCKET_ORG=loyaltoid

# Notifications (Microsoft Teams)
# TEAMS_WEBHOOK=https://your-org.webhook.office.com/webhookb2/...
"""
    with open(ENV_FILE, 'w') as f:
        f.write(default_content)
    ENV_FILE.chmod(0o600)


def create_default_arg_json():
    """Create default arg.json file with build arguments."""
    ensure_config_dir()
    default_args = {
        "REGISTRY01": "$REGISTRY01_URL",
        "BRANCH": "$REFS",
        "PROJECT": "$IMAGE",
        "PORT": "$PORT",
        "PORT2": "$PORT2"
    }
    with open(ARG_FILE, 'w') as f:
        json.dump(default_args, f, indent=4)
    ARG_FILE.chmod(0o600)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables and ~/.ngen-buildx/.env.
    
    Prioritizes environment variables over .env file.
    Creates default files if they don't exist.
    
    Returns:
        dict: Configuration dictionary
    """
    ensure_config_dir()
    
    # Create default .env if it doesn't exist
    if not ENV_FILE.exists():
        create_default_env()
        print(f"ℹ️  Created sample config at {ENV_FILE}")
        print(f"   Please update with your settings")
    
    # Create default arg.json if it doesn't exist
    if not ARG_FILE.exists():
        create_default_arg_json()
        print(f"ℹ️  Created default build args at {ARG_FILE}")
    
    # Load .env file into environment
    load_dotenv(dotenv_path=ENV_FILE)
    
    # Build config dictionary from environment variables
    config = {
        "builder": {
            "name": os.getenv("BUILDER_NAME", "mybuilder"),
            "memory": os.getenv("DEFAULT_MEMORY", "4g"),
            "cpu_period": os.getenv("DEFAULT_CPU_PERIOD", "100000"),
            "cpu_quota": os.getenv("DEFAULT_CPU_QUOTA", "200000"),
        },
        "registry": {
            "registry01_url": os.getenv("REGISTRY01_URL", ""),
        },
        "gitops": {
            "org": os.getenv("BITBUCKET_ORG", "loyaltoid"),
        },
        "notifications": {
            "teams_webhook": os.getenv("TEAMS_WEBHOOK", ""),
        }
    }
    
    return config


def load_build_args() -> Dict[str, str]:
    """Load build arguments from arg.json.
    
    Returns:
        dict: Build arguments as key-value pairs
    """
    ensure_config_dir()
    
    if not ARG_FILE.exists():
        create_default_arg_json()
    
    try:
        with open(ARG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️  Invalid JSON in {ARG_FILE}, using defaults")
        create_default_arg_json()
        with open(ARG_FILE, 'r') as f:
            return json.load(f)


def get_config_file_path() -> str:
    """Get the config file path.
    
    Returns:
        str: Absolute path to config file (.env)
    """
    return str(ENV_FILE)


def get_arg_file_path() -> str:
    """Get the arg.json file path.
    
    Returns:
        str: Absolute path to arg.json file
    """
    return str(ARG_FILE)


def config_exists() -> bool:
    """Check if config files exist.
    
    Returns:
        bool: True if both config files exist
    """
    return ENV_FILE.exists() and ARG_FILE.exists()


def get_builder_config() -> Dict[str, str]:
    """Get builder configuration.
    
    Returns:
        dict: Dictionary with builder settings
    """
    config = load_config()
    return config.get('builder', {})


def get_registry_config() -> Dict[str, str]:
    """Get registry configuration.
    
    Returns:
        dict: Dictionary with registry settings
    """
    config = load_config()
    return config.get('registry', {})


def get_teams_webhook() -> Optional[str]:
    """Get Teams webhook URL.
    
    Returns:
        Optional[str]: Teams webhook URL if configured, None otherwise
    """
    config = load_config()
    webhook = config.get('notifications', {}).get('teams_webhook', '')
    return webhook if webhook else None

