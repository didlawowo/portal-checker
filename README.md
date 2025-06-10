# Portal Checker

Monitor HTTP URLs by parsing ingress rules and httproute in your kubernetes cluster for availability and provide a little dashboard to show that.

![alt text](assets/image.png)

## Features

- **Automatic Discovery**: Scans Kubernetes Ingress and HTTPRoute resources across all namespaces
- **Real-time Monitoring**: Concurrent health checks with configurable timeout and parallelism
- **Web Dashboard**: Clean, responsive interface with search, sorting, and auto-refresh
- **Smart Exclusions**: Flexible URL filtering via YAML patterns, wildcards, and Kubernetes annotations
- **Slack Integration**: Optional notifications for failed endpoints (beta)
- **Multi-architecture**: Supports AMD64 and ARM64 platforms

## Getting Started

### Prerequisites

- Kubernetes cluster with RBAC enabled
- Helm 3.x
- kubectl configured for your cluster

### Quick Start

1. **Install with Helm**:
   ```bash
   helm install portal-checker helm/ \
     --namespace monitoring \
     --create-namespace
   ```

2. **Access the dashboard**:
   ```bash
   kubectl port-forward svc/portal-checker 8080:80 -n monitoring
   ```
   Open http://localhost:8080 in your browser

3. **View logs**:
   ```bash
   kubectl logs -f deployment/portal-checker -n monitoring
   ```

### Configuration

#### URL Exclusions
Create or modify the exclusion patterns in your values file:

```yaml
excludedUrls:
  - "monitoring.*"              # Exclude monitoring subdomains
  - "*.internal/*"             # Exclude internal paths
  - "grafana.*/api/health"     # Exclude specific endpoints
```

#### Environment Variables
```yaml
env:
  - name: REQUEST_TIMEOUT
    value: "10"                 # Increase timeout for slow endpoints
  - name: MAX_CONCURRENT_REQUESTS
    value: "5"                 # Reduce concurrency
  - name: LOG_LEVEL
    value: "DEBUG"             # Enable debug logging
```

### Development

#### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run in development mode
export FLASK_ENV=development
python app.py
```

#### Using Task Runner
```bash
# Install Task: https://taskfile.dev/#/installation
# Then run common tasks:

task run-dev              # Start development server
task validate-yaml        # Validate configuration
task test-exclusions      # Test URL exclusion logic
task build                # Build Docker image
task deploy-full          # Complete deployment workflow
```

## Installation

### Using Helm

```bash
helm install portal-checker helm \
  --namespace monitoring \
```

## Build

### Using Docker

```shell
docker compose build
```
