# Security Policy

## Supported versions

The latest released minor version receives fixes. Older versions are upgraded
rather than patched.

## Reporting a vulnerability

Please report vulnerabilities through
[GitHub Security Advisories](https://github.com/didlawowo/portal-checker/security/advisories/new)
for this repository. Do not open a public issue for a security report.

Include the affected version, the deployment mode (Helm chart, container image,
local run), and the smallest reproduction you can share. We aim to acknowledge
reports within 72 hours and to agree on a disclosure timeline with you.

## Scope worth knowing

Portal Checker is a read-mostly monitoring tool, but some of its behaviour is
security sensitive by design. When reporting, consider whether the issue
involves:

- **Discovery scope**: the shipped `ClusterRole` grants `get`/`list` on
  `ingresses`, `httproutes`, `gateways` and `namespaces` cluster-wide.
- **Active probing**: URL health checks and Autoswagger discovery send requests
  to every discovered host, including well-known API documentation paths.
- **Unauthenticated dashboard**: `/`, `/metrics` and the JSON API expose
  discovered hostnames, response details and any Swagger findings, with no
  built-in authentication.
- **Cached findings**: detected PII and secrets from third-party API schemas are
  kept in process memory and rendered in the dashboard.
- **Template or API input handling**: values coming from Kubernetes resources
  (names, namespaces, annotations, URLs) reach the HTML dashboard and the
  Prometheus exporter.

## Hardening expectations

The README documents the recommended hardening: disable Autoswagger in shared
clusters, put the dashboard behind authentication, restrict network access, and
keep the non-root security context. A report that only restates those documented
trade-offs is not a vulnerability, but a report showing they can be bypassed is.
