# ngen-apigw

GitOps-friendly API Gateway Configuration Tool.

## Description

`ngen-apigw` is a CLI and web server tool designed to manage API Gateway configurations in a GitOps workflow. It supports migrating monolithic `apigateway.json` files into manageable partial configurations, serving a local development environment to visualize changes, and checking KrakenD configurations.

## Features

-   **Migrate**: Convert monolithic configuration to host-grouped partials.
-   **Server**: Local web interface to view and manage endpoints.
-   **Check**: Validate KrakenD configurations.
-   **GitOps**: Built for version control and automated deployments.

## Installation

```bash
pip install ngen-apigw
```

## Usage

```bash
apigw --help
```

### Commands

-   `apigw migrate`: Migrate `apigateway.json` to partials.
-   `apigw server`: Start the web interface.
-   `apigw check`: Validate configuration logic.
-   `apigw merge`: Merge partials back into a single JSON file.
