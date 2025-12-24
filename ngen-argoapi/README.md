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

## Features

- **Insecure by Default**: Automatically handles SSL verification for internal ArgoCD instances.
- **Token Management**: Auto-renews or manages session tokens.
- **Easy CLI**: Simple command structure.
- **Diff Support**: View resource differences in compact or inline format.
