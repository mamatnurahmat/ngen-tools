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
ngen-j job --last-success       # Get last 10 successful jobs
ngen-j job --last-failure       # Get last 10 failed jobs
ngen-j build my-job             # Trigger build
ngen-j build my-job --param REF_NAME=develop REF_TYPE=branch  # Build with parameters
ngen-j build my-job --param=REF_NAME=develop --param=REF_TYPE=branch  # Alternative format
ngen-j get-xml my-job           # Get job XML config
ngen-j create my-job job.xml    # Create job from XML
ngen-j create my-job job.xml --force  # Update existing job
ngen-j delete my-job            # Delete job (with confirmation)
ngen-j delete my-job --force    # Delete job without confirmation
ngen-j plugin list              # List all installed plugins
ngen-j plugin list --format json --output plugins.json  # Export to JSON
ngen-j plugin list --format csv --output plugins.csv   # Export to CSV
ngen-j plugin install git      # Install git plugin
ngen-j plugin uninstall git    # Uninstall git plugin
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

**Get last 10 successful jobs:**
```bash
ngen-j job --last-success
```

**Get last 10 failed jobs:**
```bash
ngen-j job --last-failure
```

**Trigger a build:**
```bash
ngen-j build <job-name> [--param KEY=VALUE ...] or [--param=KEY=VALUE ...]
```

Options:
- `--param KEY=VALUE` - Pass build parameters (can be used multiple times)
- `--param=KEY=VALUE` - Alternative format for build parameters

Examples:
```bash
ngen-j build my-job
ngen-j build my-job --param REF_NAME=develop REF_TYPE=branch
ngen-j build my-job --param=REF_NAME=develop --param=REF_TYPE=branch
ngen-j build my-job --param REF_NAME=develop --param=REF_TYPE=branch --param DEPLOY_ENV=staging
```

**Get build console output:**
```bash
ngen-j log <job-name> <build-number>
```

**Get job XML configuration:**
```bash
ngen-j get-xml <job-name>
```

**Create or update job from XML:**
```bash
ngen-j create <job-name> <xml-file> [--force]
```

Options:
- `--force` - Skip confirmation when updating existing job

**Delete a job:**
```bash
ngen-j delete <job-name> [--force]
```

Options:
- `--force` - Skip confirmation before deleting job

**Note:** Requires Jenkins permissions: Job/Create, Job/Update, Job/Configure, Job/Delete

**List installed plugins:**
```bash
ngen-j plugin list [--format json|csv] [--output <file>]
```

Options:
- `--format json|csv` - Export format (default: table)
- `--output <file>` - Output file (optional, defaults to stdout)

Examples:
```bash
ngen-j plugin list
ngen-j plugin list --format json
ngen-j plugin list --format json --output plugins.json
ngen-j plugin list --format csv --output plugins.csv
```

**Install plugin(s):**
```bash
ngen-j plugin install <plugin1> [plugin2] ...
```

Examples:
```bash
ngen-j plugin install git
ngen-j plugin install git docker-workflow
```

**Uninstall plugin(s):**
```bash
ngen-j plugin uninstall <plugin1> [plugin2] ...
```

Examples:
```bash
ngen-j plugin uninstall git
ngen-j plugin uninstall git docker-workflow
```

**Note:** Plugin operations require Jenkins permissions: Overall/Administer or Plugin/Install and Plugin/Uninstall

### Credential Management

Manage Jenkins credentials stored in the global credentials store.

**List all credentials:**
```bash
ngen-j cred list
```

**Create a credential (interactive mode):**
```bash
ngen-j cred create
```

The interactive mode will prompt you to:
- Select credential type (Username/Password, Secret Text, SSH Key)
- Enter credential ID
- Enter description
- Enter type-specific fields (username, password, secret, private key, etc.)

**Create a credential (non-interactive mode):**
```bash
ngen-j cred create --type <type> --id <id> [options...]
```

Supported credential types:
- `username_password` or `username-password` - Username and password credentials
- `secret_text` or `secret-text` - Secret text credentials
- `ssh_key` or `ssh-key` - SSH username with private key

Options for `username_password`:
- `--id <id>` - Credential ID (required)
- `--description <desc>` - Description (optional)
- `--username <user>` - Username (required)
- `--password <pass>` - Password (required)
- `--force` - Overwrite existing credential

Options for `secret_text`:
- `--id <id>` - Credential ID (required)
- `--description <desc>` - Description (optional)
- `--secret <secret>` - Secret text (required)
- `--force` - Overwrite existing credential

Options for `ssh_key`:
- `--id <id>` - Credential ID (required)
- `--description <desc>` - Description (optional)
- `--username <user>` - Username (required)
- `--private-key <key>` - Private key content (required if not using file)
- `--private-key-file <file>` - Private key file path (required if not using key)
- `--passphrase <phrase>` - Passphrase for encrypted private key (optional)
- `--force` - Overwrite existing credential

Examples:
```bash
# Interactive mode
ngen-j cred create

# Non-interactive: Username/Password
ngen-j cred create --type username_password --id my-git-cred --username myuser --password mypass --description "Git credentials"

# Non-interactive: Secret Text
ngen-j cred create --type secret_text --id my-token --secret "my-secret-token" --description "API token"

# Non-interactive: SSH Key
ngen-j cred create --type ssh_key --id my-ssh-cred --username deploy --private-key-file ~/.ssh/id_rsa --description "Deployment SSH key"

# Overwrite existing credential
ngen-j cred create --type username_password --id my-cred --username newuser --password newpass --force
```

**Delete a credential:**
```bash
ngen-j cred delete <credential-id> [--force]
```

Options:
- `--force` - Skip confirmation before deleting credential

Examples:
```bash
ngen-j cred delete my-cred
ngen-j cred delete my-cred --force
```

**Note:** Credential operations require Jenkins permissions: Credentials/View, Credentials/Create, Credentials/Delete, or Overall/Administer

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
