# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Version Information

**Current Version**: 3.0.0 (feat/autoswagger branch)

### Major Changes in v3.0.0

1. **Modular Architecture**: Complete refactoring from monolithic `app.py` to `src/` module structure
2. **Autoswagger Integration**: Automated Swagger/OpenAPI discovery with PII and secrets detection (regex-based)
3. **Enhanced Configuration**: Centralized config management in `src/config.py`
4. **Improved Resource Usage**: Optimized memory limits (256Mi) and requests (64Mi)
5. **Better Testing**: Modular structure enables isolated unit testing
6. **Type Safety**: Full type hints throughout codebase
7. **Async Patterns**: Consistent async/await for I/O operations

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

# Memory monitoring and optimization
task memory-check          # Check current memory usage via /memory endpoint
task memory-profile        # Profile memory usage during URL refresh
task memory-stress-test    # Run stress test with multiple concurrent refreshes
```

### Python Testing

```bash
# Run pytest suite (all tests)
uv run --extra dev pytest tests/ -v

# Run tests with coverage
task test-coverage

# Run specific test files
python -m pytest tests/test_excluded_urls.py -v
python -m pytest tests/test_autoswagger.py -v  # If autoswagger tests exist

# Run linting (if configured)
ruff check .
```

### Cache Management Commands (v3.0.0+)

```bash
# Cache status and health
task cache-status              # Check cache health and statistics

# Force operations
task cache-force-refresh       # Force immediate cache refresh
task cache-clear              # Clear cache for debugging

# Performance monitoring
task cpu-optimization-check    # Check CPU optimization effectiveness
```

## Application Architecture

### Core Application (Modular Structure)

Portal Checker v3.0.0 uses a modular architecture with dedicated modules in the `src/` directory:

#### Module Structure
- **src/main.py**: Application entry point, Hypercorn ASGI server configuration, logging setup
- **src/api.py**: Flask API routes, request handlers, Swagger discovery integration
- **src/config.py**: Centralized configuration management with environment variables
- **src/kubernetes_client.py**: Kubernetes resource discovery, caching, and URL extraction
- **src/utils.py**: Utility functions for URL testing, version management
- **src/autoswagger_integration.py**: Swagger/OpenAPI discovery, PII detection, security scanning
- **app.py**: Legacy compatibility wrapper (imports from src modules)

#### Core Features
- **Flask + Hypercorn ASGI**: Async-capable web server for production
- **Kubernetes Discovery**: Automatically scans all namespaces for Ingress/HTTPRoute resources
- **Concurrent URL Testing**: Uses aiohttp with configurable semaphore (default: 10 concurrent)
- **Smart URL Exclusions**: YAML patterns, Kubernetes annotations, and fnmatch support
- **Auto-Discovery**: Creates URLs file on startup if missing
- **Swagger/OpenAPI Discovery**: Automated API documentation discovery with 13+ common endpoints
- **PII Detection**: Regex-based pattern detection for emails, phones, SSN, credit cards
- **Security Scanning**: Detects API keys, JWT tokens, AWS keys, database URLs, private keys

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

# Autoswagger integration (API discovery)
ENABLE_AUTOSWAGGER=true|false                   # Enable Swagger/OpenAPI discovery
AUTOSWAGGER_RATE_LIMIT=30                       # Max requests per second (0=unlimited)
AUTOSWAGGER_TIMEOUT=3                           # HTTP request timeout for Swagger discovery (default: 3s)
AUTOSWAGGER_MAX_CONCURRENT=5                    # Max concurrent Swagger discovery requests
AUTOSWAGGER_BRUTE_FORCE=false                   # Enable brute force parameter testing
AUTOSWAGGER_INCLUDE_NON_GET=false               # Include POST/PUT/DELETE methods in analysis
SWAGGER_DISCOVERY_INTERVAL=3600                 # Swagger discovery interval in seconds (default: 1 hour)

# Caching configuration
CACHE_TTL_SECONDS=300                           # Cache TTL for URL test results (5 minutes)
KUBERNETES_POLL_INTERVAL=600                    # Kubernetes discovery interval (10 minutes)
CHECK_INTERVAL=30                               # Periodic URL testing interval (30 seconds)
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
├── src/                     # Modular source code
│   ├── main.py              # Entry point
│   ├── api.py               # Flask routes
│   ├── config.py            # Configuration
│   ├── kubernetes_client.py # K8s integration
│   ├── utils.py             # Utilities
│   └── autoswagger_integration.py  # Swagger discovery
├── app.py                   # Legacy compatibility wrapper
├── pyproject.toml          # Version source (copied by Dockerfile)
├── config/                 # Read-only ConfigMap mount
│   └── excluded-urls.yaml  # Exclusion patterns
├── data/                   # Writable EmptyDir mount
│   └── urls.yaml          # Auto-generated discovered URLs
├── templates/              # Jinja2 templates
└── static/                 # CSS/JS assets
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

## Memory Optimization Features

### Memory Monitoring

- **Endpoint**: `/memory` - Returns RSS/VMS memory usage and percentage
- **Dependencies**: Uses `psutil` library for accurate memory tracking
- **Monitoring Tasks**: `task memory-check`, `task memory-profile`, `task memory-stress-test`

### Memory Optimizations Implemented

1. **URL Deduplication**: Removes duplicate URLs based on (url, namespace, name) triplet
2. **Essential Annotations Filtering**:
   - Keeps only important annotations (cert-manager, ingress configs, portal-checker directives)
   - Filters annotations with values > 50 characters (except essential ones)
   - Limits to maximum 10 annotations per resource
   - Prioritizes essential annotations when hitting the limit
3. **Reduced Data Structure**: Stores minimal metadata instead of full Kubernetes resource definitions

### Memory Usage Guidelines

- **Container Limits**: 256Mi memory, 600m CPU (updated for v3.0.0)
- **Container Requests**: 64Mi memory, 100m CPU
- **Expected Memory Usage**: ~50-150MB depending on cluster size
- **Memory Monitoring**: Use `/memory` endpoint and `task memory-check` for tracking

## Autoswagger Integration (API Discovery)

### Overview

Portal Checker v3.0.0 includes automated Swagger/OpenAPI discovery capabilities to identify and analyze API documentation exposed by your Kubernetes services.

### Discovery Process

#### 1. Common Swagger Endpoints Checked

The integration automatically tests 13+ common Swagger/OpenAPI paths:
- `/swagger.json`, `/swagger.yaml`, `/swagger.yml`
- `/openapi.json`, `/openapi.yaml`, `/openapi.yml`
- `/api-docs`, `/api-docs.json`
- `/v1/swagger.json`, `/v2/swagger.json`, `/v3/swagger.json`
- `/docs/swagger.json`, `/api/swagger.json`, `/api/openapi.json`
- `/swagger-ui.html`, `/docs`, `/redoc`

#### 2. Discovery Features

- **URL Deduplication**: Groups URLs by host to avoid duplicate checks
- **Multiple Formats**: Supports JSON, YAML, and HTML-embedded Swagger specs
- **Async Processing**: Concurrent discovery with configurable rate limiting
- **Security Scanning**: Automatic PII and secrets detection
- **Endpoint Analysis**: Extracts paths, methods, parameters, tags, and security requirements

### PII Detection

Uses regex patterns to detect sensitive data in API specifications:

- **EMAIL_ADDRESS**: Email patterns
- **PHONE_NUMBER**: Phone number formats
- **PERSON**: Name patterns (First Last)
- **SSN**: Social Security Number patterns
- **CREDIT_CARD**: Credit card number patterns

### Secrets Detection

Automatically scans for exposed secrets in API specifications:

- **API Keys**: Pattern-based detection for API key formats
- **JWT Tokens**: eyJ... Bearer token patterns
- **AWS Access Keys**: AKIA[0-9A-Z]{16} patterns
- **Database URLs**: MongoDB, MySQL, PostgreSQL connection strings
- **Private Keys**: PEM-formatted private keys (RSA, EC)
- **Bearer Tokens**: Authorization header patterns
- **Basic Auth**: Base64-encoded credentials

### Configuration

#### Environment Variables

```bash
# Enable/disable Autoswagger
ENABLE_AUTOSWAGGER=true

# Rate limiting (requests per second, 0=unlimited)
AUTOSWAGGER_RATE_LIMIT=30

# HTTP timeout for Swagger discovery
AUTOSWAGGER_TIMEOUT=10

# Max concurrent Swagger discovery requests
AUTOSWAGGER_MAX_CONCURRENT=5

# Advanced features (experimental)
AUTOSWAGGER_BRUTE_FORCE=false        # Parameter brute-forcing
AUTOSWAGGER_INCLUDE_NON_GET=false    # Include POST/PUT/DELETE methods
SWAGGER_DISCOVERY_INTERVAL=3600      # Discovery interval (1 hour default)
```

#### Helm Configuration

```yaml
autoswagger:
  enabled: true
  rateLimit: 30
  timeout: 10
  maxConcurrent: 5
  bruteForce: false
  includeNonGet: false
  discoveryInterval: 3600
```

### SSL Certificate Handling

Autoswagger respects custom SSL certificates for enterprise environments:

```bash
# Set custom CA certificate
CUSTOM_CERT=zscalerroot.crt
SSL_CERT_FILE=zscalerroot.crt
REQUESTS_CA_BUNDLE=zscalerroot.crt
```

The integration automatically configures SSL for:
- aiohttp client sessions
- External API requests

### API Endpoints

Portal Checker exposes Swagger discovery results via the main interface:

- **Dashboard**: Shows API count and security issues in status cards
- **Cache Data**: Swagger results stored in `_swagger_cache` dict
- **Auto-Refresh**: Runs during periodic URL tests if enabled

### Dependencies

Additional packages for Autoswagger (in pyproject.toml):

```
bs4>=0.0.2               # HTML parsing for Swagger UI pages (BeautifulSoup4)
```

### Performance Considerations

- **Concurrency Control**: Semaphore limits parallel requests
- **Host Deduplication**: Only scans each unique host once
- **Rate Limiting**: Configurable to respect API rate limits
- **Async Operations**: Non-blocking discovery during URL tests
- **Caching**: Results cached with configurable TTL

### Troubleshooting

#### SSL Certificate Errors

**Symptoms:**
```
⚠️ SSL certificate verification failed
```

**Solutions:**
1. Set `CUSTOM_CERT` to your enterprise CA certificate
2. Ensure certificate file is mounted in container
3. Development mode: SSL verification disabled automatically

#### No Swagger Found

**Logs:**
```
🔍 No Swagger found for https://example.com
```

**Normal Behavior**: Not all services expose Swagger documentation

### Best Practices

1. **Rate Limiting**:
   - Set `AUTOSWAGGER_RATE_LIMIT` based on your cluster size
   - Lower values for large clusters (100+ services)
   - Higher values for smaller environments

2. **Discovery Interval**:
   - Default 3600s (1 hour) balances freshness vs. load
   - Increase for stable environments
   - Decrease for development/testing

## Code Organization and Refactoring (v3.0.0)

### Modular Architecture

Version 3.0.0 introduces a complete refactoring from monolithic `app.py` to a modular structure:

#### Module Responsibilities

**src/config.py**
- Centralized configuration management
- Environment variable parsing with defaults
- Type hints for configuration values
- Clear separation of development vs production settings

**src/main.py**
- Application entry point
- Logger configuration (JSON/text formats)
- Background task management
- Hypercorn/Flask server initialization

**src/api.py**
- Flask route definitions
- Request/response handling
- Cache management for URL tests and Swagger results
- Template data preparation

**src/kubernetes_client.py**
- Kubernetes API client initialization
- Ingress/HTTPRoute resource discovery
- URL extraction and metadata preservation
- Annotation filtering and optimization

**src/utils.py**
- URL testing with aiohttp
- Version management (reads from pyproject.toml)
- YAML file operations
- Common utility functions

**src/autoswagger_integration.py**
- Swagger/OpenAPI discovery logic
- PII detection (regex-based)
- Secrets scanning
- SSL certificate configuration

#### Migration Benefits

1. **Improved Maintainability**:
   - Single responsibility per module
   - Easier to locate and modify specific functionality
   - Reduced cognitive load when working on features

2. **Better Testing**:
   - Modules can be tested in isolation
   - Mock dependencies more easily
   - Clearer test organization mirrors code structure

3. **Enhanced Scalability**:
   - Add new features without touching core modules
   - Plugin-style architecture for integrations
   - Easier to onboard new developers

4. **Backward Compatibility**:
   - `app.py` remains as compatibility wrapper
   - Existing imports continue to work
   - Gradual migration path for external consumers

### Code Quality Improvements

#### Type Hints
All modules use Python type hints for better IDE support and documentation:

```python
def check_urls_async(
    urls: List[Dict[str, Any]],
    update_cache: bool = True,
    is_url_excluded_fn: Optional[Callable[[str], bool]] = None
) -> List[Dict[str, Any]]:
```

#### Dataclasses
Structured data using dataclasses for clarity:

```python
@dataclass
class SwaggerEndpoint:
    url: str
    method: str
    path: str
    parameters: List[Dict[str, Any]]
    description: str = ""
    tags: List[str] = None
    security: List[Dict[str, Any]] = None
```

#### Async/Await Patterns
Consistent async patterns throughout:
- aiohttp for HTTP requests
- Kubernetes async API calls
- Background task management
- Concurrent URL testing

#### Error Handling
Robust error handling with fallbacks:
- SSL certificate errors → development mode fallback
- Kubernetes API errors → graceful degradation

### Configuration Management

Centralized in `src/config.py`:

```python
# File Paths - Environment-aware
URLS_FILE = os.getenv(
    "URLS_FILE",
    "config/urls.yaml" if FLASK_ENV == "development" else "/app/data/urls.yaml",
)

# Feature Flags
ENABLE_AUTOSWAGGER = os.getenv("ENABLE_AUTOSWAGGER", "true").lower() == "true"
AUTO_REFRESH_ON_START = os.getenv("AUTO_REFRESH_ON_START", "true").lower() == "true"

# Performance Tuning
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
```

### Dependency Injection Pattern

Functions accept dependencies as parameters for better testing:

```python
# Before (tightly coupled)
def run_tests():
    results = check_urls(load_urls())
    return results

# After (dependency injection)
async def _run_url_tests(
    update_cache: bool = True,
    is_url_excluded_fn: Optional[Callable[[str], bool]] = None
) -> List[Dict[str, Any]]:
    data_urls = load_urls_from_file(URLS_FILE)
    results = await check_urls_async(data_urls, update_cache, is_url_excluded_fn)
    return results
```

### Logging Enhancements

Structured logging with loguru:

```python
# JSON format for production
{
  "level": "INFO",
  "message": "Swagger discovery completed",
  "timestamp": "2025-10-24T12:00:00.000Z",
  "host": "example.com",
  "apis_found": 3
}

# Human-readable for development
2025-10-24 12:00:00.000 | INFO     | autoswagger:discover:290 | 📋 Found Swagger at /swagger.json
```

### Version Management

Version now centralized in `pyproject.toml`:

```toml
[project]
name = "portal-checker"
version = "3.0.0"
```

Read at runtime via `tomllib`:

```python
def get_app_version() -> str:
    """Get application version from pyproject.toml"""
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"
```

## Development Guidelines

### Adding New Features

1. **Identify Module**: Determine which module owns the feature
2. **Update Config**: Add configuration to `src/config.py`
3. **Implement Logic**: Add feature logic to appropriate module
4. **Update API**: Add routes/endpoints in `src/api.py` if needed
5. **Write Tests**: Add tests in `tests/test_<module>.py`
6. **Update Docs**: Document in CLAUDE.md

### Testing New Code

```bash
# Run tests for specific module
pytest tests/test_config.py -v

# Run with coverage for specific file
pytest tests/test_autoswagger.py --cov=src/autoswagger_integration --cov-report=term-missing

# Full test suite with coverage
task test-coverage
```

### Common Patterns

#### Adding Configuration

```python
# 1. Add to src/config.py
NEW_FEATURE_ENABLED = os.getenv("NEW_FEATURE_ENABLED", "false").lower() == "true"
NEW_FEATURE_TIMEOUT = int(os.getenv("NEW_FEATURE_TIMEOUT", "30"))

# 2. Add to helm/values.yaml
env:
  - name: NEW_FEATURE_ENABLED
    value: "{{ .Values.newFeature.enabled }}"
  - name: NEW_FEATURE_TIMEOUT
    value: "{{ .Values.newFeature.timeout }}"

# 3. Add default values
newFeature:
  enabled: false
  timeout: 30
```

#### Adding API Endpoint

```python
# In src/api.py
@app.route('/api/new-endpoint')
def new_endpoint():
    try:
        # Implementation
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error in new endpoint: {e}")
        return jsonify({"error": str(e)}), 500
```

#### Adding Kubernetes Discovery

```python
# In src/kubernetes_client.py
def discover_new_resource_type():
    """Discover new Kubernetes resource type"""
    try:
        api = client.CustomObjectsApi()
        resources = api.list_cluster_custom_object(
            group="example.io",
            version="v1",
            plural="newresources"
        )
        return process_resources(resources)
    except Exception as e:
        logger.error(f"Failed to discover resources: {e}")
        return []
```

## Quick Reference

### Architecture at a Glance (v3.0.0)

```
Portal Checker v3.0.0
├── Core Components
│   ├── Flask + Hypercorn ASGI server
│   ├── Kubernetes discovery (Ingress/HTTPRoute)
│   ├── Concurrent URL testing (aiohttp)
│   └── Background periodic testing
│
├── Modules (src/)
│   ├── main.py          → Entry point & server
│   ├── api.py           → Routes & handlers
│   ├── config.py        → Configuration
│   ├── kubernetes_client.py → K8s integration
│   ├── utils.py         → URL testing utilities
│   └── autoswagger_integration.py → API discovery
│
├── Features
│   ├── URL exclusion (YAML patterns + annotations)
│   ├── Memory optimization (deduplication, filtering)
│   ├── Swagger/OpenAPI discovery (13+ endpoints)
│   ├── PII detection (regex-based)
│   └── Secrets scanning (API keys, tokens, etc.)
│
└── Deployment
    ├── Docker multi-arch (AMD64/ARM64)
    ├── Helm chart with ConfigMap
    └── RBAC for cluster-wide discovery
```

### Common Workflows

#### Development Cycle
```bash
# 1. Start development server
task run-dev

# 2. Make changes to src/ modules

# 3. Test changes
task test-coverage

# 4. Validate configuration
task validate-yaml

# 5. Check memory usage
task memory-check
```

#### Deployment Cycle
```bash
# 1. Validate Helm chart
task helm-dry-run

# 2. Build and push
task build
task push

# 3. Deploy
task helm-install

# 4. Monitor
task status
task logs
```

#### Troubleshooting
```bash
# Check pod status
task status

# View logs
task logs

# Interactive shell
task shell

# Check memory usage
task memory-check

# Force URL refresh
task refresh-urls

# Check cache health
task cache-status
```

### Key File Locations

**Development:**
- Config: `config/excluded-urls.yaml`, `config/urls.yaml`
- Source: `src/*.py`
- Tests: `tests/*.py`
- Tasks: `taskfile.yaml`

**Production (Container):**
- Config: `/app/config/excluded-urls.yaml` (read-only ConfigMap)
- Data: `/app/data/urls.yaml` (writable EmptyDir)
- Source: `/app/src/*.py`

### Environment Variable Quick Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLASK_ENV` | `production` | Development vs production mode |
| `PORT` | `5000` | Server port |
| `REQUEST_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `MAX_CONCURRENT_REQUESTS` | `10` | Concurrent URL tests |
| `ENABLE_AUTOSWAGGER` | `true` | Enable API discovery |
| `LOG_FORMAT` | `text` | `json` or `text` logging |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CUSTOM_CERT` | `zscalerroot.crt` | Custom CA certificate |

### Resource Limits

| Resource | Request | Limit |
|----------|---------|-------|
| **Memory** | 64Mi | 256Mi |
| **CPU** | 100m | 600m |

### Testing Quick Reference

```bash
# All tests with coverage
task test-coverage

# Specific test file
pytest tests/test_excluded_urls.py -v

# Watch mode during development
pytest tests/ -v --looponfail

# Coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Common Issues and Solutions

#### Issue: Module import errors after refactoring
**Solution**: Ensure you're importing from `src.module` not root `app`
```python
# Old (deprecated)
from app import check_urls

# New (correct)
from src.utils import check_urls_async
```

#### Issue: Autoswagger not discovering APIs
**Check:**
1. `ENABLE_AUTOSWAGGER=true` is set
2. Services actually expose Swagger endpoints
3. Check logs for SSL certificate errors
4. Verify rate limiting isn't too aggressive

#### Issue: High memory usage
**Solutions:**
1. Check annotation filtering is working: `task memory-check`
2. Verify URL deduplication: Check `_test_results_cache` size
3. Reduce `MAX_CONCURRENT_REQUESTS` if testing many URLs

#### Issue: Tests failing after modular refactor
**Solution**: Update test imports to use `src.` prefix
```python
# Old
from app import is_url_excluded

# New
from src.kubernetes_client import is_url_excluded
```

### Migration Notes from v2.x to v3.0.0

**Breaking Changes:**
- `app.py` is now a wrapper; direct imports may need updating
- Environment variable `ENABLE_AUTOSWAGGER` defaults to `true` (was `false`)
- Memory limits reduced from 512Mi to 256Mi (optimization)

**Compatibility:**
- Existing Helm deployments work with updated values.yaml
- Old `app.py` imports redirected to new modules
- API endpoints unchanged
- Configuration file formats unchanged

**Recommended Actions:**
1. Review and update any custom integrations importing from `app`
2. Test with Autoswagger enabled (or explicitly disable if not needed)
3. Monitor memory usage with new limits
4. Update CI/CD pipelines to use `task` commands
