# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Essential Task Commands
```bash
# Development and testing
task run-dev                # Start development server on port 5001
task validate-yaml          # Validate YAML configuration files
task test-exclusions        # Test URL exclusion logic with real patterns
task ci-test               # Run all CI validation tests

# Build and deployment
task build                 # Build Docker image with git SHA tag
task push                  # Push to fizzbuzz2 registry
task helm-dry-run          # Validate Helm deployment without applying
task deploy-full           # Complete build + push + deploy workflow

# Operations and debugging
task logs                  # Stream application logs from Kubernetes
task status                # Show pod/service status and current config
task port-forward          # Local access via kubectl port-forward
task shell                 # Interactive shell in running pod
task refresh-urls          # Force URL discovery refresh via API
```

### Python Testing
```bash
# Run pytest suite (exclusion logic tests)
python -m pytest tests/ -v

# Run linting
ruff check .
```

## Application Architecture

### Core Application (app.py)
- **Flask + Hypercorn ASGI**: Async-capable web server for production
- **Kubernetes Discovery**: Automatically scans all namespaces for Ingress/HTTPRoute resources
- **Concurrent URL Testing**: Uses aiohttp with configurable semaphore (default: 10 concurrent)
- **Smart URL Exclusions**: YAML patterns, Kubernetes annotations, and fnmatch support
- **Auto-Discovery**: Creates URLs file on startup if missing

### Key Configuration Patterns

#### URL Exclusion Methods
1. **YAML file patterns** (`config/excluded-urls.yaml`):
   - Exact matches: `infisical.dc-tech.work/ss-webhook`
   - Domain wildcards: `monitoring.*`
   - Path patterns: `*.internal/*`
   - Complex patterns using fnmatch

2. **Kubernetes annotations**: `portal-checker.io/exclude: "true"`

3. **URL normalization**: Trailing slashes automatically handled

#### Environment Variables
```bash
# Core settings
URLS_FILE=/app/data/urls.yaml                    # Writable location for discovered URLs
EXCLUDED_URLS_FILE=/app/config/excluded-urls.yaml  # Read-only exclusion patterns
REQUEST_TIMEOUT=5                                # HTTP request timeout
MAX_CONCURRENT_REQUESTS=10                       # Async concurrency limit

# Development mode
FLASK_ENV=development                            # Enables debug mode, changes file paths
LOG_FORMAT=json|text                            # Production uses JSON, dev uses text
LOG_LEVEL=DEBUG|INFO|WARN|ERROR

# Optional features
ENABLE_SLACK_NOTIFICATIONS=true|false
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
CUSTOM_CERT=/path/to/custom-ca.pem
```

### Deployment Architecture

#### Helm Chart Structure
- **ConfigMap**: Contains excluded-urls.yaml patterns
- **Volume Mounts**: 
  - `/app/config` (read-only): ConfigMap with exclusion patterns
  - `/app/data` (writable): EmptyDir for runtime URLs cache
- **RBAC**: Cluster-wide read permissions for Ingress/HTTPRoute discovery
- **Security**: Non-root user (1000:1000), security context enforced

#### Version Management
- Version defined in `pyproject.toml`
- CI builds Docker tags: `{version}`, `{git-sha}`, `latest`
- Helm values automatically updated with semantic version
- HTML template displays version from `pyproject.toml` via `tomllib`

### Testing Strategy

#### Exclusion Logic Tests (`tests/test_excluded_urls.py`)
- Parametrized tests with real-world patterns
- URL normalization validation
- Wildcard and fnmatch pattern testing
- YAML configuration loading tests

#### Development Testing
```bash
# Test exclusion patterns against real config
task test-exclusions

# Validate YAML syntax and structure
task validate-yaml
```

## Important Implementation Details

### File System Layout in Container
```
/app/
├── app.py                    # Main application
├── pyproject.toml           # Version source (copied by Dockerfile)
├── config/                  # Read-only ConfigMap mount
│   └── excluded-urls.yaml   # Exclusion patterns
├── data/                    # Writable EmptyDir mount
│   └── urls.yaml           # Auto-generated discovered URLs
├── templates/               # Jinja2 templates
└── static/                  # CSS/JS assets
```

### Security Considerations
- HTML template uses safe data attributes instead of `| safe` filter for XSS prevention
- All file paths configurable for development vs production
- SSL verification configurable with custom CA support
- Non-root container execution enforced

### Kubernetes Integration
- **Discovery scope**: All namespaces, both Ingress and HTTPRoute resources
- **Resource types**: `networking.k8s.io/v1/Ingress`, `gateway.networking.k8s.io/v1beta1/HTTPRoute`
- **Metadata preservation**: Full annotations, labels, namespace, and resource details stored
- **Performance**: Async Kubernetes API calls with connection pooling

### CI/CD Pipeline Notes
- GitHub Actions automatically builds multi-arch images (AMD64/ARM64)
- Version extracted from `pyproject.toml` using grep/sed
- Helm values updated with semantic version (not git SHA)
- SonarQube integration available but configurable