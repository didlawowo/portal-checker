# Portal Checker

Monitor HTTP URLs by parsing ingress rules and httproute in your kubernetes cluster for availability and provide a little dashboard to show that.

![alt text](assets/image.png)

## Features

- **Automatic Discovery**: Scans Kubernetes Ingress and HTTPRoute resources across all namespaces
- **Real-time Monitoring**: Concurrent health checks with configurable timeout and parallelism
- **Periodic Checking**: Automated background tests with configurable intervals
- **Web Dashboard**: Clean, responsive interface with search, sorting, and auto-refresh
- **Smart Exclusions**: Flexible URL filtering via YAML patterns, wildcards, and Kubernetes annotations
- **Ingress Class Support**: Displays Ingress Class and Gateway information for better visibility
- **Responsive Design**: Optimized for mobile, tablet, and desktop viewing
- **Performance Optimized**: Smart caching and efficient resource usage
- **Multi-architecture**: Supports AMD64 and ARM64 platforms
- **Slack Integration**: Optional notifications for failed endpoints (beta)

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
    value: "5"                  # Request timeout in seconds
  - name: MAX_CONCURRENT_REQUESTS
    value: "3"                  # Number of concurrent checks
  - name: LOG_LEVEL
    value: "INFO"              # Log level (DEBUG, INFO, WARNING, ERROR)
  - name: CHECK_INTERVAL
    value: "300"               # Interval between checks in seconds (5 minutes)
  - name: CACHE_TTL_SECONDS
    value: "900"               # Cache TTL in seconds (15 minutes)
  - name: KUBERNETES_POLL_INTERVAL
    value: "1800"              # K8s resource polling interval (30 minutes)
```

#### Performance Tuning
For large clusters, consider adjusting these values:

```yaml
# Reduce CPU usage
env:
  - name: CHECK_INTERVAL
    value: "600"               # Check every 10 minutes
  - name: MAX_CONCURRENT_REQUESTS
    value: "2"                 # Reduce concurrent load
  - name: CACHE_TTL_SECONDS
    value: "1800"              # Cache for 30 minutes

# Increase resource limits
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 128Mi
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
task push                 # Push to registry
task deploy-full          # Complete deployment workflow
task logs                 # Stream application logs
task status              # Show pod status
task memory-check        # Check memory usage
```

#### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Run specific test file
python -m pytest tests/test_excluded_urls.py -v
```

## Architecture

### Components

1. **Flask Application**: Main web server with async support via Hypercorn
2. **Kubernetes Client**: Discovers Ingress and HTTPRoute resources
3. **Async HTTP Client**: Performs concurrent health checks using aiohttp
4. **Background Worker**: Periodic URL checking via threading
5. **Cache Layer**: Reduces Kubernetes API calls and improves performance

### Data Flow

```
Kubernetes API → Resource Discovery → URL Generation → Exclusion Filtering
                                                           ↓
Dashboard ← Results Aggregation ← Health Checks ← Concurrent Testing
```

## Deployment

### Production Deployment

1. **Update values for production**:
   ```yaml
   # values-prod.yaml
   ingress:
     enabled: true
     domainName: portal-checker.example.com
     tls:
       enabled: true
   
   resources:
     limits:
       cpu: 500m
       memory: 512Mi
   
   replicas: 2
   ```

2. **Deploy with production values**:
   ```bash
   helm upgrade --install portal-checker helm/ \
     -f values-prod.yaml \
     --namespace monitoring
   ```

### CI/CD

The project includes automated CI/CD pipelines:

- **Build Pipeline**: Runs on every push, builds multi-arch Docker images
- **Release Pipeline**: Runs on main branch merges, creates releases with semantic versioning
- **Helm Release**: Automatically packages and publishes Helm charts

## Monitoring

### Health Endpoints

- `/health` - Application health check
- `/ready` - Readiness check (includes K8s connectivity)
- `/memory` - Memory usage statistics
- `/cache` - Cache status and statistics

### Metrics

Key metrics to monitor:
- URL check success rate
- Response times per endpoint
- Cache hit ratio
- Memory usage
- CPU utilization

## Troubleshooting

### Common Issues

1. **High CPU Usage**
   - Increase `CHECK_INTERVAL` to reduce frequency
   - Reduce `MAX_CONCURRENT_REQUESTS`
   - Check for large number of URLs being monitored

2. **403 Forbidden Errors**
   - Verify RBAC permissions for ServiceAccount
   - Check ClusterRole and ClusterRoleBinding

3. **URLs Not Discovered**
   - Check namespace permissions
   - Verify Ingress/HTTPRoute resources have proper annotations
   - Review exclusion patterns

4. **Memory Issues**
   - Enable memory profiling: `task memory-profile`
   - Reduce cache size or TTL
   - Check for memory leaks in long-running deployments

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.