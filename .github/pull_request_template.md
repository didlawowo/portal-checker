## What changed

<!-- Describe the problem and the approach, not only the files touched. -->

## Why

<!-- Link the issue or explain the need. -->

## How it was verified

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run pytest tests/ -v`
- [ ] `node --test tests/dashboard.test.cjs` (dashboard changes)
- [ ] `helm lint helm` (chart changes)

## Checklist

- [ ] The change is scoped and does not include unrelated refactors
- [ ] Configuration is read through `src/config.py`
- [ ] Tests cover the new behaviour
- [ ] Documentation is updated when behaviour or configuration changes
- [ ] No credentials, internal hostnames or customer data are included
