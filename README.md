# ngenctl

[![GitHub](https://img.shields.io/badge/GitHub-mamatnurahmat%2Fngenctl-blue)](https://github.com/mamatnurahmat/ngenctl)
[![PyPI](https://img.shields.io/pypi/v/ngenctl)](https://pypi.org/project/ngenctl/)

Universal command wrapper package that dispatches to `/usr/local/bin/ngenctl-*` scripts, environment commands, and supports aliases for quick access.

## Installation

Install from PyPI:

```bash
pip install ngenctl
```

Or install from source:

```bash
pip install .
```

**Note:** Installation to `/usr/local/bin` requires sudo/root permissions. The package will automatically install bundled scripts to `/usr/local/bin/ngenctl-*` during installation.

## Usage

The `ngenctl` command provides a unified interface for executing:
- Scripts from `/usr/local/bin/ngenctl-{command}`
- Environment commands available in PATH (configured via `config.json`)
- Aliases for quick command shortcuts (configured via `alias.json`)

### Command Resolution Priority

1. **Aliases** - Commands defined in `$HOME/.ngenctl/alias.json`
2. **Scripts** - Scripts from `/usr/local/bin/ngenctl-{command}` or bundled scripts
3. **Environment Commands** - Commands from `$HOME/.ngenctl/config.json` available in PATH

### Examples

#### Scripts

If you have a script at `/usr/local/bin/ngenctl-rancher`, you can use it as:

```bash
ngenctl rancher --help
ngenctl rancher version
```

#### Aliases

Create aliases in `$HOME/.ngenctl/alias.json`:

```json
{
  "login": "rancher login",
  "clusters": "rancher clusters",
  "ci": "devops-ci",
  "gn": "kubectl get nodes"
}
```

Then use the aliases:

```bash
ngenctl login           # Executes: ngenctl rancher login
ngenctl clusters        # Executes: ngenctl rancher clusters
ngenctl ci saas-app develop  # Executes: ngenctl devops-ci saas-app develop
ngenctl gn              # Executes: ngenctl kubectl get nodes
```

#### Environment Commands

Configure environment commands in `$HOME/.ngenctl/config.json`:

```json
{
  "doq": "doq",
  "kubectl": "kubectl"
}
```

Then use them directly:

```bash
ngenctl doq ns develop-saas    # Executes: doq ns develop-saas
ngenctl kubectl get nodes      # Executes: kubectl get nodes
```

## How It Works

1. When you run `ngenctl {command}`, the CLI dispatcher checks in this order:
   - **Aliases**: Checks if the command is defined in `$HOME/.ngenctl/alias.json` and resolves it
   - **Scripts**: Looks for a script at `/usr/local/bin/ngenctl-{command}` or bundled scripts
   - **Environment Commands**: Checks `$HOME/.ngenctl/config.json` and verifies the command is available in PATH
2. If found, it executes the command with any additional arguments passed
3. Scripts can be any executable file (bash, sh, Python, or binary)
4. Aliases support recursive resolution and circular reference detection

## Configuration

### Aliases (`$HOME/.ngenctl/alias.json`)

Create command aliases to shorten frequently used commands:

```json
{
  "login": "rancher login",
  "clusters": "rancher clusters",
  "ci": "devops-ci",
  "gn": "kubectl get nodes"
}
```

Aliases can reference other commands (scripts, environment commands, or other aliases). Circular references are automatically detected.

### Environment Commands (`$HOME/.ngenctl/config.json`)

Map `ngenctl` commands to executables available in your PATH:

```json
{
  "doq": "doq",
  "kubectl": "kubectl",
  "docker": "docker"
}
```

Commands in `config.json` will only work if the actual executable is available in your PATH.

## Adding New Commands

### Method 1: Scripts

1. Place a script at `/usr/local/bin/ngenctl-{your-command}`
2. Make sure it's executable: `chmod +x /usr/local/bin/ngenctl-{your-command}`
3. Use it with: `ngenctl {your-command}`

### Method 2: Aliases

1. Edit `$HOME/.ngenctl/alias.json`
2. Add your alias: `"{short-name}": "{full-command}"`
3. Use it with: `ngenctl {short-name}`

Example:
```json
{
  "login": "rancher login"
}
```
Then use: `ngenctl login`

### Method 3: Environment Commands

1. Edit `$HOME/.ngenctl/config.json`
2. Add your command: `"{ngenctl-command}": "{actual-command-in-path}"`
3. Ensure the actual command is available in your PATH
4. Use it with: `ngenctl {ngenctl-command}`

Example:
```json
{
  "doq": "doq"
}
```
Then use: `ngenctl doq` (if `doq` is in PATH)

## Development

### Building the Package

```bash
python -m build
```

### Publishing to PyPI

Menggunakan script otomatis:

```bash
./publish.sh --test      # Publish ke Test PyPI
./publish.sh --publish   # Publish ke PyPI production
```

Atau manual:

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Untuk panduan lengkap, lihat [PUBLISH.md](PUBLISH.md).

## Repository

- **GitHub**: https://github.com/mamatnurahmat/ngenctl
- **PyPI**: https://pypi.org/project/ngenctl/

## License

MIT

