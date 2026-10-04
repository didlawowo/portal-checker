# Helm values overrides

`docker.yaml` provides optional development settings and always pulls the image.
It inherits the chart's published image version unless you override `image.tag`.
It contains no fixed branch, commit, build timestamp, or organization-specific domain.

## Development branch image

The workflow `.github/workflows/docker-build-on-branch-push.yml` publishes branch
images as `{branch}-{sha8}` and PR images as `pr-{number}` and `pr-{number}-{sha8}`.
Use an existing tag from Docker Hub; the workflow does not rewrite this values file.

```bash
helm upgrade --install portal-checker-dev ./helm --namespace portal-checker-dev --create-namespace --values helm/values/docker.yaml --set image.tag=pr-123-abcdef12
```

Replace the example tag with the image for your branch or PR. Development mode
disables TLS verification when no custom CA is configured; use the default chart
settings for production.

## Published chart defaults

```bash
helm upgrade --install portal-checker ./helm --namespace monitoring --create-namespace
```

Set `excludedUrls`, ingress settings, and optional custom CA mounts in your own
values file. The chart has no domain-specific exclusions by default.
