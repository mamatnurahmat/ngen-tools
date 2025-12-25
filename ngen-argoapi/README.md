# ngen-argoapi

ArgoCD API management CLI and wrapper package.
Designed to simplify ArgoCD interactions and CI/CD integration.

## Installation

```bash
pip install ngen-argoapi
```

## Usage

### Login

Login to your ArgoCD instance. This will save your credentials securely (insecure mode by default for internal instances).

```bash
argoapi login
```

### Application Management

List all applications with sync/health status:
```bash
argoapi app list
```

Get application details (JSON output):
```bash
argoapi app get <application-name>
```

Show diff for out-of-sync resources:
```bash
argoapi app diff <application-name>
argoapi app diff <application-name> --compact
argoapi app diff <application-name> --inline
```

Refresh an application:
```bash
argoapi app refresh <application-name>
argoapi app refresh <application-name> --hard
```

### Server Mode

Start the ArgoAPI server with Swagger UI:

```bash
argoapi server
argoapi server --host 0.0.0.0 --port 8899
```

API endpoints available at:
- **Swagger UI**: `http://localhost:8899/docs`
- **ReDoc**: `http://localhost:8899/redoc`
- **Health Check**: `http://localhost:8899/health`


### Health Check Endpoint

The `/health` endpoint returns:

```json
{
  "status": "healthy",
  "version": "0.1.8",
  "timestamp": "2024-12-25T10:30:00.000000Z",
  "service": "argoapi",
  "argocd_connected": true,
  "token": {
    "valid": true,
    "username": "admin",
    "error": null
  }
}
```

**Status values:**
- `healthy`: ArgoCD connected and token valid
- `degraded`: ArgoCD connected but token invalid/expired


## Environment Variables

| Variable | Description |
|----------|-------------|
| `ARGOAPI_VERSION` | Override version reported by API (optional) |

## Features

- **Insecure by Default**: Automatically handles SSL verification for internal ArgoCD instances.
- **Token Management**: Auto-renews or manages session tokens.
- **Easy CLI**: Simple command structure.
- **Diff Support**: View resource differences in compact or inline format.
- **Server Mode**: REST API with Swagger documentation.
- **Health Check**: Kubernetes-ready health check endpoint.

