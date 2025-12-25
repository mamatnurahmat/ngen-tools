import os

# Default version, can be overridden by ARGOAPI_VERSION environment variable
_DEFAULT_VERSION = "0.1.9"

def _get_version():
    """Get version from environment variable or use default."""
    return os.environ.get("ARGOAPI_VERSION", _DEFAULT_VERSION)

__version__ = _get_version()
