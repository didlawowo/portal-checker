# Portal Checker

[![Version](https://img.shields.io/badge/version-3.0.17-blue.svg)](https://github.com/didlawowo/portal-checker/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-multi--arch-blue.svg)](https://hub.docker.com/r/fizzbuzz2/portal-checker)
[![Helm](https://img.shields.io/badge/helm-OCI-blue.svg)](https://github.com/didlawowo/portal-checker/pkgs/container/charts%2Fportal-checker)

**Monitor your Kubernetes endpoints with a beautiful, real-time dashboard.** Portal Checker automatically discovers Ingress and HTTPRoute resources across your cluster and provides instant visibility into endpoint health.

## Dashboard

![Portal Checker Dashboard](assets/dashboard.png)

The dashboard provides a clean overview of all your Kubernetes endpoints with:

- **Namespace & Name**: Quick identification of resources
- **Info Column**: Compact badges showing type (`ing`/`http`), ingress class, and annotation count
- **Swagger Discovery**: Automatic API documentation detection with security analysis
- **SSL Monitoring**: Certificate expiration tracking with color-coded warnings
- **Status & Response Time**: Real-time health checks with latency metrics

## Swagger/OpenAPI Discovery

![Swagger Modal](assets/swagger-modal.png)

Automatically discovers and analyzes API documentation:

- Scans 13+ common Swagger endpoint paths
- Displays all endpoints with methods (GET, POST, PUT, DELETE)
- Shows security status for each endpoint (protected/unprotected)
- Detects PII exposure and secrets in API schemas

## Key Features

### Automatic Discovery

Scans all namespaces for **Ingress** and **HTTPRoute** resources, extracting URLs with full metadata including namespace, resource name, ingress class, and annotations.

### Real-time Health Monitoring

| Feature | Description |
| ------- | ----------- |
| **Concurrent Checks** | Parallel health checks with configurable concurrency (default: 10) |
| **Smart Caching** | Reduces API calls with configurable TTL |
| **Background Testing** | Periodic automated tests at configurable intervals |
| **Response Times** | Track latency for each endpoint |

### Interactive Dashboard

- **Search & Filter**: Quickly find endpoints by namespace, name, or URL
- **Sortable Columns**: Sort by any column including status, response time, or namespace
- **Status Overview**: Quick stats showing healthy, warning, and failed counts
- **Auto-refresh**: Configurable automatic refresh (default: 30 seconds)
- **Mobile Responsive**: Works on desktop, tablet, and mobile devices

### Smart URL Exclusions

Exclude URLs using multiple methods:

```yaml
# YAML patterns with wildcards
excludedUrls:
  - "monitoring.*"           # Exclude all monitoring subdomains
  - "*.internal/*"           # Exclude internal paths
  - "grafana.*/api/health"   # Exclude specific health endpoints
  - "*.example.com/api"      # Exclude API paths on specific domain
```

Or use Kubernetes annotations:

```yaml
metadata:
  annotations:
    portal-checker.io/exclude: "true"
```

### API Discovery (Autoswagger)

- Scans 13+ common Swagger endpoint paths
- Detects PII exposure in API schemas
- Identifies exposed secrets (API keys, JWT tokens, AWS credentials)
- Groups findings by security severity

## Getting Started

### Published Artifacts

| Artifact | Registry | Address |
| -------- | -------- | ------- |
| Container image (multi-arch `amd64`/`arm64`) | Docker Hub | [`fizzbuzz2/portal-checker`](https://hub.docker.com/r/fizzbuzz2/portal-checker) |
| Helm chart (OCI) | GHCR | `oci://ghcr.io/didlawowo/charts/portal-checker` |
| Helm chart (OCI) | Docker Hub | `oci://registry-1.docker.io/fizzbuzz2/portal-checker-chart` |

Latest version: **3.0.17**

### Prerequisites

- Kubernetes cluster with RBAC enabled
- Helm 3.8+ (for OCI registry support)
- kubectl configured for your cluster

### Install the Helm Chart

**From GHCR (recommended)**

```bash
helm install portal-checker \
  oci://ghcr.io/didlawowo/charts/portal-checker \
  --version 3.0.17 \
  --namespace monitoring \
  --create-namespace
```

**From Docker Hub**

```bash
helm install portal-checker \
  oci://registry-1.docker.io/fizzbuzz2/portal-checker-chart \
  --version 3.0.17 \
  --namespace monitoring \
  --create-namespace
```

**From local source (for development)**

```bash
git clone https://github.com/didlawowo/portal-checker.git
cd portal-checker
helm install portal-checker helm/ \
  --namespace monitoring \
  --create-namespace
```

### Pull the Container Image

```bash
docker pull fizzbuzz2/portal-checker:3.0.17
docker pull fizzbuzz2/portal-checker:latest
```

### Access the Dashboard

```bash
# Port forward to access locally
kubectl port-forward svc/portal-checker 8080:80 -n monitoring

# Open in browser
open http://localhost:8080
```

## Discovered Resources

Portal Checker watches all namespaces and extracts URLs from two Kubernetes resource types.

### Ingress (`networking.k8s.io/v1`)

For each `Ingress` rule, one URL is generated per `host` / `path` combination. The chosen ingress class is read from `spec.ingressClassName` (preferred) or the legacy `kubernetes.io/ingress.class` annotation (fallback to `nginx`).

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: apps
spec:
  ingressClassName: traefik
  rules:
    - host: my-app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app
                port:
                  number: 80
```

→ produces `https://my-app.example.com`

### HTTPRoute (`gateway.networking.k8s.io/v1beta1`)

For each `HTTPRoute`, one URL is generated per `hostname` × `rules[].matches[].path.value`. The ingress class is reported as `gateway/<parentRef.name>` in the dashboard.

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: HTTPRoute
metadata:
  name: my-app
  namespace: apps
spec:
  parentRefs:
    - name: external-gateway
  hostnames:
    - my-app.example.com
  rules:
    - matches:
        - path:
            value: /api
      backendRefs:
        - name: my-app
          port: 80
```

→ produces `https://my-app.example.com/api`

### Excluding a resource from discovery

Add the annotation directly on the `Ingress` or `HTTPRoute` (no chart change required):

```yaml
metadata:
  annotations:
    portal-checker.io/exclude: "true"
```

Or define URL patterns in `values.yaml` (`excludedUrls`) — see [URL Exclusions](#url-exclusions).

### Required RBAC

The chart ships a `ClusterRole` granting read-only access to the resources it discovers:

```yaml
rules:
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list"]
  - apiGroups: ["gateway.networking.k8s.io"]
    resources: ["httproutes", "gateways"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list"]
```

## Configuration

### Environment Variables

#### Core

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `PORT` | `5000` | Listening port |
| `FLASK_ENV` | `production` | `production` or `development` (toggles paths & debug) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARN` / `ERROR` |
| `LOG_FORMAT` | `text` | `json` for log shippers (Loki/ELK), `text` for human-readable |
| `REQUEST_TIMEOUT` | `10` | HTTP request timeout when health-checking URLs (seconds) |
| `MAX_CONCURRENT_REQUESTS` | `10` | Concurrent health checks (semaphore) |
| `EXCLUDE_SELF` | `true` | Auto-exclude portal-checker's own Ingress/HTTPRoute from its URL list (uses downward API `POD_NAME` / `POD_NAMESPACE`) |

#### Polling cadences

Four independent timers control how often each background task runs. Tune them to your cluster size.

| Variable | Default | Controls |
| -------- | ------- | -------- |
| `KUBERNETES_POLL_INTERVAL` | `600` | How often the K8s API is queried to refresh the list of Ingress/HTTPRoute resources |
| `DISCOVERY_INTERVAL` | `600` | Re-discovery cadence triggered by the background task (kept in sync with the above for most setups) |
| `CHECK_INTERVAL` | `30` | How often discovered URLs are health-checked |
| `CACHE_TTL_SECONDS` | `300` | TTL of cached URL test results — shorter = fresher dashboard, more load |
| `SSL_CACHE_TTL_SECONDS` | `3600` | TTL of cached SSL certificate metadata (certs change rarely) |

#### Custom CA / Enterprise proxy

If your cluster sits behind an enterprise TLS-inspecting proxy (Zscaler, Netskope, corporate CA), mount the CA bundle and point these variables to it. They are honored by both `aiohttp` (URL health checks) and `requests`/`urllib3` (Autoswagger).

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `CUSTOM_CERT` | `zscalerroot.crt` | Path to a PEM-encoded CA bundle inside the container |
| `SSL_CERT_FILE` | _(unset)_ | Mirror of `CUSTOM_CERT` for libraries reading this env var |
| `REQUESTS_CA_BUNDLE` | _(unset)_ | Same, for the `requests` library |

Example values to mount your own CA:

```yaml
# values.yaml
volumeMounts:
  - name: custom-ca
    mountPath: /etc/ssl/custom
    readOnly: true
volumes:
  - name: custom-ca
    secret:
      secretName: corp-ca-bundle    # PEM file under key ca.crt
      items:
        - key: ca.crt
          path: ca.crt
env:
  - name: CUSTOM_CERT
    value: /etc/ssl/custom/ca.crt
  - name: SSL_CERT_FILE
    value: /etc/ssl/custom/ca.crt
  - name: REQUESTS_CA_BUNDLE
    value: /etc/ssl/custom/ca.crt
```

In development (`FLASK_ENV=development`), SSL verification falls back to disabled if the CA cannot be loaded — never run with `development` in production.

#### Autoswagger (API discovery)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `ENABLE_AUTOSWAGGER` | `true` | Master switch. **Disable** if you don't want portal-checker to probe APIs (see [Security Considerations](#security-considerations)) |
| `SWAGGER_DISCOVERY_INTERVAL` | `3600` | How often (seconds) the Swagger probe runs, independently of URL health checks |
| `AUTOSWAGGER_RATE_LIMIT` | `30` | Max requests/second across the whole probe — `0` = unlimited |
| `AUTOSWAGGER_TIMEOUT` | `3` | HTTP timeout per Swagger probe request (seconds) |
| `AUTOSWAGGER_MAX_CONCURRENT` | `5` | Parallel probes (semaphore) |
| `AUTOSWAGGER_BRUTE_FORCE` | `false` | Experimental parameter brute-forcing — leave off in shared clusters |
| `AUTOSWAGGER_INCLUDE_NON_GET` | `false` | Include POST/PUT/PATCH/DELETE endpoints in the dashboard listing (reads the spec only, never executes mutating calls) |

Per discovery cycle, portal-checker hits 13+ well-known paths (`/openapi.json`, `/swagger.json`, `/api-docs`, `/docs`, `/redoc`, versioned variants, YAML variants, `/swagger-ui.html`) on each discovered host. With 100 ingresses that's ~1300 requests per `SWAGGER_DISCOVERY_INTERVAL` — see [Security Considerations](#security-considerations) before enabling at large scale.

### Helm Values

```yaml
# values.yaml
resources:
  limits:
    cpu: 600m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 64Mi

ingress:
  enabled: true
  domainName: portal-checker.example.com
  tls:
    enabled: true

env:
  - name: CHECK_INTERVAL
    value: "60"
  - name: MAX_CONCURRENT_REQUESTS
    value: "5"
```

### URL Exclusions

Configure exclusions in `values.yaml`:

```yaml
excludedUrls:
  - "argocd.*/api/*"
  - "monitoring.*"
  - "*.internal/*"
  - "infisical.*/ss-webhook"
```

## Architecture

```text
                    ┌─────────────────────────────────────────────┐
                    │              Kubernetes Cluster             │
                    │  ┌─────────┐  ┌─────────┐  ┌─────────────┐ │
                    │  │ Ingress │  │ Ingress │  │  HTTPRoute  │ │
                    │  └────┬────┘  └────┬────┘  └──────┬──────┘ │
                    └───────┼────────────┼──────────────┼────────┘
                            │            │              │
                            └────────────┼──────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │           Portal Checker                 │
                    │  ┌──────────────────────────────────┐   │
                    │  │      Resource Discovery          │   │
                    │  │   • Ingress (networking.k8s.io)  │   │
                    │  │   • HTTPRoute (gateway API)      │   │
                    │  └──────────────┬───────────────────┘   │
                    │                 │                        │
                    │  ┌──────────────▼───────────────────┐   │
                    │  │      URL Extraction & Filtering  │   │
                    │  │   • Exclusion patterns           │   │
                    │  │   • Annotation checks            │   │
                    │  └──────────────┬───────────────────┘   │
                    │                 │                        │
                    │  ┌──────────────▼───────────────────┐   │
                    │  │      Concurrent Health Checks    │   │
                    │  │   • aiohttp async client         │   │
                    │  │   • Configurable parallelism     │   │
                    │  └──────────────┬───────────────────┘   │
                    │                 │                        │
                    │  ┌──────────────▼───────────────────┐   │
                    │  │      Web Dashboard (Flask)       │   │
                    │  │   • Real-time status             │   │
                    │  │   • Search & sorting             │   │
                    │  └──────────────────────────────────┘   │
                    └─────────────────────────────────────────┘
```

### Module Structure (v3.0.0+)

```text
src/
├── main.py                    # Entry point, server configuration
├── api.py                     # Flask routes and handlers
├── config.py                  # Centralized configuration
├── kubernetes_client.py       # K8s resource discovery
├── utils.py                   # URL testing utilities
└── autoswagger_integration.py # API documentation discovery
```

## Development

### Local Development

```bash
# Install dependencies with uv
uv sync

# Run development server
task run-dev

# Or manually
FLASK_ENV=development PORT=5001 python -m src.main
```

### Task Commands

```bash
task run-dev          # Start development server
task test-coverage    # Run tests with coverage
task validate-yaml    # Validate configuration files
task build            # Build Docker image
task push             # Push to registry
task deploy-full      # Complete deployment workflow
task logs             # Stream application logs
task status           # Show pod status
task memory-check     # Check memory usage
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
task test-coverage

# Run specific test
pytest tests/test_excluded_urls.py -v
```

## API Endpoints

| Endpoint | Method | Description |
| -------- | ------ | ----------- |
| `/` | GET | Main dashboard |
| `/api/test` | GET | Run health checks |
| `/api/refresh` | POST | Force URL rediscovery |
| `/api/swagger` | GET | Get Swagger discovery results |
| `/health` | GET | Application health |
| `/ready` | GET | Readiness check |
| `/memory` | GET | Memory statistics |

## Security Considerations

Portal Checker is designed to run in trusted networks. Be aware of the following before deploying it on shared / production clusters.

### 1. Autoswagger probes look like reconnaissance

By default Autoswagger fetches 13+ well-known paths (`/swagger.json`, `/openapi.json`, `/api-docs`, `/docs`, `/redoc`, …) on **every** discovered host, every `SWAGGER_DISCOVERY_INTERVAL`. WAFs, IDS, and SIEMs will frequently flag this as a scanner. Coordinate with your security team or set `ENABLE_AUTOSWAGGER=false`.

### 2. Cluster-wide read scope

The shipped `ClusterRole` grants `get`/`list` on `ingresses`, `httproutes`, `gateways`, and `namespaces` cluster-wide. In a multi-tenant cluster, portal-checker will discover and probe every team's APIs. If that's not acceptable:

- Reduce scope by replacing the `ClusterRole` with a namespaced `Role` (chart change required)
- Or restrict via `excludedUrls` patterns
- Or use the `portal-checker.io/exclude: "true"` annotation on resources you don't want probed

### 3. Dashboard has no built-in authentication

The Flask dashboard exposes results to anyone who can reach the service. If Autoswagger is enabled, that includes PII / secrets / API keys it detected in third-party Swagger specs. Always front the Ingress with auth (oauth2-proxy, basic auth, OIDC, NetworkPolicy, …) before exposing it.

### 4. Detected PII and secrets are cached in memory

Findings are kept in the in-process `_swagger_cache` and surfaced on the dashboard. A memory dump, a debug log, or an unauthenticated dashboard exposes them. Limit container memory dump access and treat the pod as sensitive.

### 5. `AUTOSWAGGER_INCLUDE_NON_GET` is read-only — but listed methods may surprise auditors

The flag only enables **listing** POST/PUT/PATCH/DELETE endpoints from the parsed spec; portal-checker never executes mutating calls. That said, the dashboard now displays them, which may trigger compliance questions ("why does this monitoring tool know about our DELETE endpoints?"). Leave it `false` unless you specifically need the visibility.

### 6. No circuit-breaker on probed services

If a probed service starts erroring or slowing down, Autoswagger keeps hitting it at the same rate until the next cycle. For fragile services, lower `AUTOSWAGGER_RATE_LIMIT` and `AUTOSWAGGER_MAX_CONCURRENT`, or exclude them.

### Recommended hardening defaults

- Disable Autoswagger in untrusted / multi-tenant clusters (`ENABLE_AUTOSWAGGER=false`)
- Front the dashboard with authentication
- Use `NetworkPolicy` to restrict ingress to the dashboard
- Pod already runs as non-root (`runAsUser: 1000`) with `runAsNonRoot: true` — don't override

## Troubleshooting

### High CPU Usage

- Increase `CHECK_INTERVAL` to reduce frequency
- Reduce `MAX_CONCURRENT_REQUESTS`
- Review number of monitored URLs

### URLs Not Discovered

- Verify RBAC permissions (ClusterRole needs list/watch on Ingress and HTTPRoute)
- Check namespace permissions
- Review exclusion patterns

### Memory Issues

- Check with `task memory-check`
- Reduce cache TTL if needed
- Consider disabling Autoswagger if not needed

### SSL Certificate Errors

```yaml
env:
  - name: CUSTOM_CERT
    value: "/path/to/ca-bundle.crt"
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
