# ngen-buildx

Docker Buildx CLI wrapper with GitOps integration.

## Overview

`ngen-buildx` is a CLI tool that simplifies Docker image building using `docker buildx`. It integrates with `ngen-gitops` to automatically fetch CI/CD configuration from repositories.

## Features

- 🚀 **GitOps Integration**: Fetches `cicd/cicd.json` from repositories using `gitops get-file`
- 🔧 **Configurable Build Args**: Template-based build arguments with variable substitution
- 📦 **Resource Management**: Configurable memory and CPU limits for builds
- 🏗️ **Multi-platform Support**: Build for multiple architectures

## Installation

```bash
pip install ngen-buildx
```

## Prerequisites

- Docker with buildx plugin installed
- `ngen-gitops` installed and configured with Bitbucket credentials

## Quick Start

1. **Initialize configuration:**
   ```bash
   buildx init
   ```

2. **Edit configuration files:**
   ```bash
   # Edit ~/.ngen-buildx/.env for environment variables
   # Edit ~/.ngen-buildx/arg.json for build arguments
   ```

3. **Build an image:**
   ```bash
   buildx build saas-apigateway develop
   ```

## Configuration

### Environment Variables (`~/.ngen-buildx/.env`)

```bash
# Builder Configuration
BUILDER_NAME=mybuilder
DEFAULT_MEMORY=4g
DEFAULT_CPU_PERIOD=100000
DEFAULT_CPU_QUOTA=200000

# Registry Configuration
REGISTRY01_URL=registry.example.com
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

### Build Command

```bash
# Basic build
buildx build <repo> <ref>

# Examples
buildx build saas-apigateway develop
buildx build saas-apigateway develop --dry-run
buildx build saas-apigateway develop --push
buildx build myrepo main --tag myregistry/myapp:v1.0.0
buildx build myrepo main --platform linux/amd64,linux/arm64
```

### Options

| Option | Description |
|--------|-------------|
| `--context` | Build context path (default: `.`) |
| `--dockerfile`, `-f` | Dockerfile path (default: `Dockerfile`) |
| `--tag`, `-t` | Image tag |
| `--push` | Push image after build |
| `--platform` | Target platform(s) |
| `--org` | Organization name |
| `--dry-run` | Show command without executing |
| `--json` | Output as JSON |

### Configuration Command

```bash
# Show configuration
buildx config

# Show as JSON
buildx config --json
```

### Initialize Command

```bash
# Create config files
buildx init

# Recreate config files
buildx init --force
```

## Generated Build Command

The tool generates a command like:

```bash
docker buildx build \
  --builder mybuilder \
  --sbom=true \
  --no-cache \
  --attest type=provenance,mode=max \
  --memory 4g \
  --cpu-period 100000 \
  --cpu-quota 200000 \
  --progress=plain \
  --build-arg REGISTRY01=registry.example.com \
  --build-arg BRANCH=develop \
  --build-arg PROJECT=saas-apigateway \
  --build-arg PORT=8005 \
  --build-arg PORT2=8080 \
  -f Dockerfile \
  .
```

## License

MIT
