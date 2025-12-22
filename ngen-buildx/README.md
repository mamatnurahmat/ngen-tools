# ngen-buildx

Docker Buildx CLI wrapper with GitOps integration.

## Overview

`ngen-buildx` is a CLI tool that simplifies Docker image building using `docker buildx`. It integrates with `ngen-gitops` to automatically fetch CI/CD configuration from repositories and supports both remote and local builds.

## Features

- 🚀 **Remote Build**: Build directly from remote Git repositories (default)
- 📁 **Local Build**: Build from local source directory with `--local` flag (auto-detects repo and branch)
- 🔧 **GitOps Integration**: Fetches `cicd/cicd.json` from repositories using `gitops get-file`
- 📦 **Resource Management**: Configurable memory and CPU limits for builds
- 🏗️ **Multi-platform Support**: Build for multiple architectures
- 🔄 **Smart Image Check**: Skip build if image already exists (use `--rebuild` to force)
- 📣 **Teams Notification**: Send build notifications to Microsoft Teams
- 🏷️ **Smart Tagging**: Uses local/remote commit ID for branches, tag name for version tags

## Installation

```bash
pip install ngen-buildx
```

## Prerequisites

- Docker with buildx plugin installed
- `ngen-gitops` installed and configured with Bitbucket credentials
- `~/.netrc` configured with Bitbucket credentials (for remote builds)

### Create Docker Buildx Builder

Before using `ngen-buildx`, you need to create a Docker Buildx builder instance:

```bash
# Create a new builder (replace 'container-builder' with your preferred name)
docker buildx create --name container-builder --driver docker-container --use

# Verify the builder is active
docker buildx ls

# Bootstrap the builder (optional, but recommended)
docker buildx inspect --bootstrap
```

> **Note**: Make sure the builder name matches `BUILDER_NAME` in your `~/.ngen-buildx/.env` configuration.

## Quick Start

1. **Initialize configuration:**
   ```bash
   buildx --init
   ```

2. **Edit configuration files:**
   ```bash
   # Edit ~/.ngen-buildx/.env for environment variables
   # Edit ~/.ngen-buildx/arg.json for build arguments
   ```

3. **Build an image:**
   ```bash
   # Remote build (from Git repository)
   buildx saas-apigateway develop
   
   # Local build (from current directory, auto-detects repo and branch)
   cd /path/to/project
   buildx --local
   ```

## Configuration

### Environment Variables (`~/.ngen-buildx/.env`)

```bash
# Builder Configuration
BUILDER_NAME=container-builder
DEFAULT_MEMORY=4g
DEFAULT_CPU_PERIOD=100000
DEFAULT_CPU_QUOTA=200000

# Registry Configuration
REGISTRY01_URL=myregistry

# GitOps Settings
BITBUCKET_ORG=myorg

# Notifications (Microsoft Teams)
TEAMS_WEBHOOK=https://your-org.webhook.office.com/webhookb2/...
```

### Build Arguments (`~/.ngen-buildx/arg.json`)

```json
{
    "REGISTRY01": "$REGISTRY01_URL",
    "BRANCH": "$REFS",
    "PROJECT": "$IMAGE",
    "PORT": "$PORT",
    "PORT2": "$PORT2"
}
```

### CICD Configuration (`cicd/cicd.json` in repository)

```json
{
    "IMAGE": "saas-apigateway",
    "CLUSTER": "qoin",
    "PROJECT": "saas",
    "DEPLOYMENT": "saas-apigateway",
    "NODETYPE": "front",
    "PORT": "8005"
}
```

## Usage

### Remote Build (Default)

Build directly from remote Git repository:

```bash
# Basic build
buildx <repo> <ref>

# Examples
buildx saas-apigateway develop
buildx saas-apigateway develop --dry-run
buildx myrepo v1.0.0
```

### Local Build

Build from local source directory (auto-detects repo and branch from git):

```bash
# Auto-detect repo and branch from current git directory
cd /path/to/project
buildx --local
buildx --local --dry-run

# Explicit repo and ref
buildx myrepo develop --local

# Build with custom cicd.json path
buildx --local --cicd config/cicd.json

# Build with custom context
buildx myrepo develop --local --context ./src

# Local build with push
buildx --local --push
```

### Build Options

| Option | Description |
|--------|-------------|
| `--local` | Build from local directory instead of remote repo |
| `--rebuild` | Force rebuild even if image already exists |
| `--cicd PATH` | Path to local cicd.json (default: `cicd/cicd.json`) |
| `--context PATH` | Build context path (default: `.`) |
| `--dockerfile`, `-f` | Dockerfile path (default: `Dockerfile`) |
| `--tag`, `-t` | Image tag (default: from cicd.json) |
| `--push` | Push image after build (default for remote builds) |
| `--platform` | Target platform(s) (e.g., `linux/amd64,linux/arm64`) |
| `--org` | Organization name |
| `--build-arg KEY=VALUE` | Set build argument (can be used multiple times) |
| `--dry-run` | Show command without executing |
| `--json` | Output as JSON |

### Configuration Commands

```bash
# Show configuration
buildx --config

# Show as JSON
buildx --config --json
```

### Initialize Command

```bash
# Create config files
buildx --init

# Recreate config files
buildx --init --force
```

## Image Tagging

The tool uses smart tagging based on the build mode and reference type:

| Build Mode | Reference Type | Tag Source |
|------------|----------------|------------|
| Remote | Branch (`develop`, `main`) | Commit ID from remote repo |
| Local | Branch (`develop`, `main`) | Commit ID from local git |
| Any | Version tag (`v1.0.0`) | Tag name as-is |

Example tags:
- Branch build: `myregistry/app:f51df9` (6-char commit ID)
- Tag build: `myregistry/app:v1.0.0` (tag name)

## Generated Build Command

### Remote Build

```bash
docker buildx build \
  --builder container-builder \
  --sbom=true \
  --no-cache \
  --attest type=provenance,mode=max \
  --memory 4g \
  --cpu-period 100000 \
  --cpu-quota 200000 \
  --progress=plain \
  --build-arg REGISTRY01=myregistry \
  --build-arg BRANCH=develop \
  --build-arg PROJECT=saas-apigateway \
  --build-arg PORT=8005 \
  -t myregistry/saas-apigateway:2195e0 \
  --push \
  https://***:***@bitbucket.org/myorg/saas-apigateway.git#develop
```

### Local Build

```bash
docker buildx build \
  --builder container-builder \
  --sbom=true \
  --no-cache \
  --attest type=provenance,mode=max \
  --memory 4g \
  --cpu-period 100000 \
  --cpu-quota 200000 \
  --progress=plain \
  --build-arg REGISTRY01=myregistry \
  --build-arg BRANCH=master \
  --build-arg PROJECT=myapp \
  --build-arg PORT=8080 \
  -t myregistry/myapp:f51df9 \
  -f Dockerfile .
```

## Teams Notification

When `TEAMS_WEBHOOK` is configured in `.env`, build notifications are sent to Microsoft Teams:

- ✅ Success notification with image details
- ❌ Failure notification with error info

## Troubleshooting

### Builder not found

If you get "no builder 'mybuilder' found" error:

```bash
# Create the builder
docker buildx create --name mybuilder --driver docker-container --use
```

### Authentication issues for remote builds

Ensure `~/.netrc` is configured:

```
machine bitbucket.org
  login your-username
  password your-app-password
```

## Related Tools

- [ngen-gitops](https://pypi.org/project/ngen-gitops/) - GitOps CLI for repository management

## License

MIT
