# Prometheus metrics and Grafana

`GET /metrics` exposes Prometheus text format 0.0.4 on the same HTTP port as the
application. It reads an in-memory snapshot of discovery and completed checks.
A scrape never reads the URLs file, calls Kubernetes, starts a check, or performs
Swagger or TLS discovery. Prometheus, VictoriaMetrics and Grafana are optional.
No new Python dependency, persistent metric registry or alerting service is needed.

## Scraping

Example Prometheus configuration (replace the target with your service address):

```yaml
scrape_configs:
  - job_name: portal-checker
    scrape_interval: 30s
    honor_labels: true
    metrics_path: /metrics
    static_configs:
      - targets: ['portal-checker.monitoring.svc:80']
```

Preserve the exported `namespace` label with `honor_labels: true` when Kubernetes
service discovery attaches its own namespace label. Otherwise Prometheus renames
the application label to `exported_namespace`, which will not match the dashboard.
Scrape only trusted instances. The endpoint has the same access boundary as the
existing unauthenticated dashboard; keep it on a private service or behind your
existing access control. Resource names and hostnames are operational metadata.
Do not put secrets or personal identifiers in Kubernetes resource names/hostnames.

The chart renders no monitoring resources by default. If Prometheus Operator is
already installed, enable `serviceMonitor.enabled` and set `serviceMonitor.labels`
to match your Prometheus selector (for example `release: monitoring`). Its scrape
interval and timeout are configurable, and it preserves application labels.
Enabling it requires the `monitoring.coreos.com/v1` ServiceMonitor CRD; ordinary
Helm installations do not require that CRD or Prometheus Operator.

## Labels and aggregation

An endpoint group is `(namespace, resource, resource_type, host)`, where resource
is the Kubernetes name and resource_type is `ingress`, `httproute` or `unknown`.
Host is parsed from the original URL, lowercased and stripped of credentials,
port, path, query and fragment. Invalid identifiers become `unknown`. Arbitrary
Kubernetes labels, annotations, errors, certificate subjects, Swagger findings,
PII and detected secrets are never exported. Only fixed `state` enums add series.

Paths sharing the same labels are combined deterministically, regardless of
input order. Duplicate inventory entries are collapsed. Each group produces at
most 13 series, independent of its number of paths, plus four global state
counts. Cardinality scales with discovered resource/host groups, not requests,
paths, status codes or findings. Removed resources disappear on the next inventory
publication. No registry accumulates historical series.

All paths must have a completed result before a group is considered tested.
Its HTTP state is the worst result (`failed` > `warning` > `healthy`); latency is
the maximum of all paths. If any path is untested, the group state is `unknown`,
`tested=0`, timestamp is 0, and up/latency are omitted.

Final HTTP responses are classified as:

| Response | State | up |
| --- | --- | --- |
| 200–399 | healthy | 1 |
| 401, 403, 405, 429 | warning | 1 |
| Other statuses, including 404 and 5xx | failed | 0 |
| Missing result | unknown | absent |

Redirects are followed by the existing checker: usually the final response is
classified. Synthetic statuses 408 (timeout), 495 (TLS error) and 503 (connection
error) are failed. `up` means healthy or warning, not necessarily HTTP 200. The
Grafana dashboard uses these metric states; the existing web UI keeps its HTTP
status filters.

## Metric contract

Every metric below is a **gauge**, including state counts. Do not use `rate()` on
these metrics. Names have the `portal_checker_` prefix.

| Suffix | Meaning |
| --- | --- |
| `endpoints{state}` | Current count of groups in each healthy/warning/failed/unknown state; four zeros for an empty inventory |
| `endpoint_state{…,state}` | Four one-hot samples per group |
| `endpoint_up` | 1 healthy/warning, 0 failed; omitted until fully tested |
| `endpoint_tested` | 1 if all paths have a completed check, otherwise 0 |
| `endpoint_last_check_timestamp_seconds` | Unix seconds of the last completed check batch; 0 until fully tested |
| `endpoint_stale` | 1 if last check is older than CACHE_TTL_SECONDS; 0 for fresh or never tested (use tested to distinguish) |
| `endpoint_response_time_seconds` | Maximum response time across paths; omitted if any value is missing or invalid |
| `endpoint_tls_state{…,state}` | Three one-hot samples: known, unknown, http_only |
| `endpoint_tls_expiry_timestamp_seconds` | Earliest TLS expiry across HTTPS paths; absent if any HTTPS path lacks expiry |

The snapshot is published under a lock, while rendering runs outside the lock.
New inventory is visible before its first check completes. Before the first
inventory load, only the four zero global counts exist. A failed or stopped
refresh preserves the last observations; their age increases and stale becomes
1. These states do not silently become healthy or disappear when old. Concurrent
checks publish only the newest-started pass, preventing an older pass from
replacing a newer inventory/result pair. Check timestamps use explicit UTC.

TLS is independent of HTTP state. All HTTPS paths must have an expiry for the
group to be `known`; then the earliest expiry wins. HTTP paths do not contribute
to expiry, and groups containing only HTTP paths are `http_only`. Missing TLS,
including a failed certificate verification, is `unknown`, never zero days or a
claim that a certificate is valid. The collector may fail to retrieve an expired
certificate: expired panels count only *known* expirations. Expiry dates originate
from the existing TLS cache (SSL_CACHE_TTL_SECONDS); days remaining are calculated
by Grafana with `(portal_checker_endpoint_tls_expiry_timestamp_seconds - time()) / 86400`, so they continue decreasing between checks. Certificate counts
in the dashboard are resource/host groups, not unique certificate fingerprints.

## Optional Grafana dashboard

Import [`grafana/portal-checker.json`](../grafana/portal-checker.json) using
Grafana's dashboard import, or place it in your existing dashboard provisioning
directory. Select a Prometheus-compatible datasource and a Portal Checker instance.
The datasource variable avoids fixed datasource names or UIDs. Namespace filtering
is available; select one instance to avoid counting independently checked replicas
twice. The dashboard requires no custom plugin.

Panels cover current states, namespace distribution, resource types, last-check
age, untested/stale groups, latency and its history, unavailable TLS, known expired
certificates, and disjoint 0–7 / 7–30 day expiry buckets. History comes from your
metrics backend, not Portal Checker. A missing latency/expiry means unavailable
information; panels do not convert that absence to zero or a healthy state.

Format references: [Prometheus text exposition](https://prometheus.io/docs/instrumenting/exposition_formats/)
and [Grafana variables](https://grafana.com/docs/grafana/latest/visualizations/dashboards/variables/add-template-variables/).
