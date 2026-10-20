# Contributing to Portal Checker

Thanks for taking the time to contribute. This project is a small, opinionated
tool: it prefers explicit configuration and readable code over clever
abstractions. Please keep changes focused and consistent with the existing
structure.

## Ways to contribute

- Report a bug or a documentation error with the bug report template.
- Propose a feature by opening an issue first, so the design can be discussed.
- Send a pull request for a discussed issue, a typo, or a documentation fix.

## Development setup

Requirements:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (dashboard tests only)
- [Task](https://taskfile.dev/) (optional, convenience commands)
- Helm 3.8+ (chart changes only)

```bash
git clone https://github.com/didlawowo/portal-checker.git
cd portal-checker
uv sync --extra dev
task run-dev          # or: FLASK_ENV=development PORT=5001 uv run python -m src.main
```

The development server listens on port 5001 and reads `config/*.yaml`. It does
not need a Kubernetes cluster to start; discovery simply returns no resource
until a cluster is reachable.

## Before opening a pull request

Run the same gates as CI:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/ -v --cov=src --cov-report=term-missing
node --test tests/dashboard.test.cjs
helm lint helm
```

`uv run ruff format .` fixes formatting. Coverage must not decrease: the
`coverage-regression` workflow compares your branch with `main` and fails on any
regression.

If you change the version, run `task version:sync` (or
`uv run python scripts/sync_version.py`) so the lockfile, README examples and
Helm metadata stay aligned.

## Commit messages

The release workflow derives the next version from commit subjects, so commits
must follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(metrics): expose cached checks
fix(api): handle empty discovery result
docs(readme): clarify OCI install
```

`feat` bumps the minor version, `fix`/`chore`/`docs`/`refactor`/`test`/`ci`/`build`
bump the patch version, and `BREAKING CHANGE` or a `!` after the type bumps the
major version. `commitlint` validates the format locally if you install the
Git hook.

## Code guidelines

- Keep the module boundaries: `src/api.py` (routes), `src/config.py`
  (configuration), `src/kubernetes_client.py` (discovery), `src/utils.py`
  (URL checks), `src/autoswagger_integration.py` (API discovery),
  `src/metrics.py` (Prometheus rendering).
- Read configuration through `src/config.py`; do not call `os.getenv` from
  route handlers.
- Add or update tests in `tests/` next to the behaviour you change.
- The dashboard has no authentication. Do not add a feature that widens what an
  unauthenticated caller can read without documenting it in the README security
  section.
- Prometheus scrapes must never trigger network checks or discovery; keep the
  cache lock and generation guard in `src/metrics.py`.

## Pull request process

1. Open the pull request against `main` and describe the problem, not only the
   solution.
2. Keep the diff scoped; unrelated refactors belong in their own pull request.
3. A maintainer reviews the change and the CI result before merging.

## Continuous integration and external contributors

CI runs on self-hosted runners owned by the project; no GitHub-hosted runner is
used. Two consequences for a pull request opened from a fork:

- The run waits for a maintainer to approve it, because the runners are private
  infrastructure.
- Publishing secrets (`DOCKER_USERNAME`, `DOCKER_PASSWORD`) are not exposed to
  fork pull requests, so image jobs build without pushing.

What this means in practice:

1. Open the pull request as usual.
2. If the checks stay queued, a maintainer approves the run. Nothing is missing
   on your side.
3. If you cannot wait, or cannot run the project locally, send a patch instead:
   `git format-patch -1` and attach it to the issue or pull request. A
   maintainer applies it and runs the checks for you.

Please run the checks locally before asking for a run: the runners are a shared
resource and every queue entry costs time for everyone.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contribution is licensed under the MIT
License, as described in [LICENSE](LICENSE).
