#!/usr/bin/env python3
"""CLI dispatcher for ngenctl command wrapper."""

import sys
import os
import subprocess
import json
from pathlib import Path


def get_alias_file_path() -> Path:
    """
    Get the path to the alias configuration file.
    
    Returns:
        Path to $HOME/.ngenctl/alias.json
    """
    home = Path.home()
    alias_dir = home / ".ngenctl"
    alias_file = alias_dir / "alias.json"
    return alias_file


def load_aliases() -> dict:
    """
    Load aliases from $HOME/.ngenctl/alias.json.
    Creates directory and file if they don't exist.
    
    Returns:
        Dictionary of aliases (empty dict if file doesn't exist or is invalid)
    """
    alias_file = get_alias_file_path()
    
    # Create directory if it doesn't exist
    alias_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create empty JSON file if it doesn't exist
    if not alias_file.exists():
        try:
            with open(alias_file, 'w') as f:
                json.dump({}, f)
            return {}
        except Exception as e:
            print(f"Warning: Could not create alias file {alias_file}: {e}", file=sys.stderr)
            return {}
    
    # Load existing aliases
    try:
        with open(alias_file, 'r') as f:
            aliases = json.load(f)
            if not isinstance(aliases, dict):
                print(f"Warning: Invalid alias file format in {alias_file}", file=sys.stderr)
                return {}
            return aliases
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in alias file {alias_file}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Warning: Could not read alias file {alias_file}: {e}", file=sys.stderr)
        return {}


def save_aliases(aliases: dict) -> bool:
    """
    Save aliases to $HOME/.ngenctl/alias.json.
    
    Args:
        aliases: Dictionary of aliases to save
        
    Returns:
        True if saved successfully, False otherwise
    """
    alias_file = get_alias_file_path()
    
    try:
        # Ensure directory exists
        alias_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(alias_file, 'w') as f:
            json.dump(aliases, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving aliases to {alias_file}: {e}", file=sys.stderr)
        return False


def resolve_alias(command: str, aliases: dict, visited: set = None) -> str:
    """
    Resolve alias to actual command, handling nested aliases and recursion.
    
    Args:
        command: The command to resolve
        aliases: Dictionary of aliases
        visited: Set of already visited commands (to detect recursion)
        
    Returns:
        Resolved command string, or original command if not an alias
    """
    if visited is None:
        visited = set()
    
    # Check if this command is an alias
    if command not in aliases:
        return command
    
    # Detect recursion
    if command in visited:
        print(f"Error: Circular alias detected involving '{command}'", file=sys.stderr)
        return command
    
    # Resolve the alias
    visited.add(command)
    expanded = aliases[command]
    
    # If expanded command is also an alias, resolve recursively
    if isinstance(expanded, str):
        parts = expanded.split(None, 1)
        if parts and parts[0] in aliases:
            resolved = resolve_alias(parts[0], aliases, visited)
            if len(parts) > 1:
                return f"{resolved} {parts[1]}"
            return resolved
    
    return expanded


def find_script(command: str) -> Path:
    """
    Find the script wrapper for the given command.
    
    Priority:
    1. /usr/local/bin/ngenctl-{command}
    2. Scripts bundled in the package
    
    Args:
        command: The subcommand (e.g., "rancher", "git")
        
    Returns:
        Path to the script, or None if not found
    """
    # Check in /usr/local/bin first
    system_script = Path(f"/usr/local/bin/ngenctl-{command}")
    if system_script.exists() and system_script.is_file():
        return system_script
    
    # Check in bundled scripts
    package_dir = Path(__file__).parent
    bundled_script = package_dir / "scripts" / f"ngenctl-{command}"
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


def main():
    """Main entry point for ngenctl command."""
    # Load aliases
    aliases = load_aliases()
    
    if len(sys.argv) < 2:
        print("Usage: ngenctl <command> [args...]", file=sys.stderr)
        print("\nAvailable commands:")
        # List available commands
        commands_found = set()
        # Check /usr/local/bin
        system_bin = Path("/usr/local/bin")
        if system_bin.exists():
            for script in system_bin.glob("ngenctl-*"):
                if script.is_file():
                    command = script.name.replace("ngenctl-", "", 1)
                    commands_found.add(command)
        # Check bundled scripts
        package_dir = Path(__file__).parent
        bundled_dir = package_dir / "scripts"
        if bundled_dir.exists():
            for script in bundled_dir.glob("ngenctl-*"):
                if script.is_file():
                    command = script.name.replace("ngenctl-", "", 1)
                    commands_found.add(command)
        # Add aliases to the list
        for alias_name in aliases.keys():
            commands_found.add(alias_name)
        # Print commands
        for cmd in sorted(commands_found):
            if cmd in aliases:
                print(f"  {cmd} (alias: {aliases[cmd]})")
            else:
                print(f"  {cmd}")
        if not commands_found:
            print("  (no commands found)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Handle help flags
    if command in ("-h", "--help", "help"):
        print("Usage: ngenctl <command> [args...]", file=sys.stderr)
        print("\nngenctl is a universal command wrapper that dispatches to scripts at /usr/local/bin/ngenctl-*")
        print("\nExamples:")
        print("  ngenctl rancher --help")
        print("  ngenctl git clone <repo>")
        sys.exit(0)
    
    # Check if command is an alias and resolve it
    if command in aliases:
        expanded = resolve_alias(command, aliases)
        # Split expanded command into command and remaining args
        expanded_parts = expanded.split()
        if expanded_parts:
            command = expanded_parts[0]
            # Prepend any additional args from the alias expansion
            existing_args = sys.argv[2:]
            args = expanded_parts[1:] + existing_args
        else:
            args = sys.argv[2:]
    else:
        args = sys.argv[2:]
    
    script_path = find_script(command)
    
    if script_path is None:
        print(f"Error: command '{command}' not found", file=sys.stderr)
        print(f"Expected script at: /usr/local/bin/ngenctl-{command}", file=sys.stderr)
        sys.exit(1)
    
    exit_code = execute_script(script_path, args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

