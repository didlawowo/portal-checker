# AGENTS.md

Guidance for AI coding agents working on this repository. It is intentionally
short: the public documentation lives in `README.md` and `docs/`.

## What this project is

A Kubernetes monitoring tool. It discovers `Ingress` and `HTTPRoute` resources,
extracts URLs, health-checks them concurrently, optionally probes well-known
Swagger/OpenAPI paths, and renders a Flask dashboard plus Prometheus metrics.

## Layout

```text
src/main.py                    entry point, Hypercorn server, background tasks
src/api.py                     Flask routes and request handlers
src/config.py                  all environment parsing (single source of truth)
src/kubernetes_client.py       discovery, URL extraction, exclusions
src/utils.py                   aiohttp URL checks, YAML and version helpers
src/autoswagger_integration.py Swagger discovery, PII and secrets detection
src/metrics.py                 /metrics rendering from the in-memory snapshot
templates/, static/            dashboard markup, CSS, vanilla JS
helm/                          Helm chart (values, templates, artifacthub metadata)
```

## Commands

```bash
uv sync --extra dev                      # install
task run-dev                             # dev server on :5001
uv run pytest tests/ -v                  # tests
uv run ruff format --check . && uv run ruff check .
node --test tests/dashboard.test.cjs     # dashboard tests
helm lint helm                           # chart checks
task version:sync                        # after changing the version in pyproject.toml
```

## Invariants to preserve

- Configuration is read through `src/config.py`; route handlers do not call
  `os.getenv` directly.
- `pyproject.toml` is the only version source. `scripts/sync_version.py`
  propagates it to the lockfile, README examples and Helm metadata, and
  `task version:check` (used by CI) verifies consistency.
- `/metrics` must never trigger a network check, a Kubernetes call or a
  discovery. It renders the cached snapshot only; keep the cache lock and the
  check generation guard in `src/metrics.py`.
- The dashboard is unauthenticated by design. Do not add endpoints that widen
  what an anonymous caller can read without documenting it in the README
  security section.
- Detected PII and secrets stay in memory. Never log them or export them as
  Prometheus labels.
- Kubernetes-sourced values (names, namespaces, annotations, URLs) are
  untrusted input: keep escaping at the template and JS boundary.

## Conventions

- Commits follow Conventional Commits; the release workflow derives the version
  bump from commit subjects.
- Tests live in `tests/` and mirror the module they cover.
- Keep changes scoped; unrelated refactors belong in their own pull request.
