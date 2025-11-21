# ngen-j

[![GitHub](https://img.shields.io/badge/GitHub-mamatnurahmat%2Fngen-j-blue)](https://github.com/mamatnurahmat/ngen-j)
[![PyPI](https://img.shields.io/pypi/v/ngen-j)](https://pypi.org/project/ngen-j/)

Jenkins API management CLI tool that also supports executing scripts from `/usr/local/bin/ngen-j-*`.

## Installation

Install from PyPI:

```bash
pip install ngen-j
```

Or install from source:

```bash
pip install .
```

## Usage

The `ngen-j` command provides:
- Jenkins API management commands
- Script execution from bundled scripts

### Version

Check the version:

```bash
ngen-j --version
# or
ngen-j -V
```

### Login

Save Jenkins credentials for easy access:

```bash
ngen-j login
```

The login command will:
- Prompt for Jenkins URL
- Ask for authentication method (username+token, username+password, or base64)
- Save credentials to `~/.ngen-j/.env`
- Test the connection

After login, you can use Jenkins commands without setting environment variables each time.

### Check Connection

Validate your Jenkins access and credentials:

```bash
ngen-j check
```

The check command will:
- Test connection to Jenkins server
- Verify authentication credentials
- Display Jenkins version and basic info
- Show troubleshooting tips if connection fails

**Examples:**
```bash
ngen-j login                    # Setup Jenkins credentials
ngen-j check                    # Validate connection
ngen-j --version               # Check version
ngen-j jobs                     # List all jobs
ngen-j job my-job               # Get job details
ngen-j build my-job             # Trigger build
```

### Jenkins API Management

Manage Jenkins jobs and builds using environment variables for authentication.

#### Environment Variables

Set the following environment variables for Jenkins authentication:

```bash
export JENKINS_URL="https://jenkins.example.com"
export JENKINS_USER="your-username"
export JENKINS_TOKEN="your-api-token"
```

Alternatively, you can use base64 encoded authentication:

```bash
export JENKINS_URL="https://jenkins.example.com"
export JENKINS_AUTH="base64-encoded-user:token"
```

#### Jenkins Commands

**List all jobs:**
```bash
ngen-j jobs
```

**Get job details:**
```bash
ngen-j job <job-name>
```

**Trigger a build:**
```bash
ngen-j build <job-name>
```

### Script Execution

If you have a bundled script, you can execute it directly:

```bash
ngen-j rancher --help
ngen-j rancher version
```

The CLI will look for scripts in the bundled scripts directory.

## How It Works

1. When you run `ngen-j {command}`, the CLI dispatcher checks in this order:
   - **Built-in commands**: Jenkins management commands
   - **Scripts**: Looks for a script at `/usr/local/bin/ngen-j-{command}` or bundled scripts
2. If found, it executes the command with any additional arguments passed
3. Scripts can be any executable file (bash, sh, Python, or binary)

## Adding New Commands

### Scripts

1. Place a script in the `ngen_j/scripts/` directory with name `ngen-j-{your-command}`
2. Make sure it's executable: `chmod +x ngen_j/scripts/ngen-j-{your-command}`
3. Use it with: `ngen-j {your-command}`

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

- **GitHub**: https://github.com/mamatnurahmat/ngen-j
- **PyPI**: https://pypi.org/project/ngen-j/

## License

MIT
