"""Regression checks for synchronized metadata and release test failures."""

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sync_version", ROOT / "scripts/sync_version.py"
)
sync_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_version)


def test_current_release_metadata():
    sync_version.synchronize(ROOT, check=True)


def test_next_release_synchronizes_without_changing_dependencies(tmp_path):
    for filename in [
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "helm/values.yaml",
        "helm/Chart.yaml",
    ]:
        destination = tmp_path / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, destination)
    project = tmp_path / "pyproject.toml"
    original_version = sync_version.tomllib.loads(project.read_text())["project"][
        "version"
    ]
    next_version = f"{int(original_version.split('.')[0]) + 1}.0.0"
    project.write_text(
        project.read_text().replace(
            f'version = "{original_version}"', f'version = "{next_version}"', 1
        )
    )
    with pytest.raises(ValueError, match="Versions differ"):
        sync_version.synchronize(tmp_path, check=True)
    original_lock = (tmp_path / "uv.lock").read_text()
    sync_version.synchronize(tmp_path)
    sync_version.synchronize(tmp_path, check=True)
    assert (tmp_path / "uv.lock").read_text() == original_lock.replace(
        f'name = "portal-checker"\nversion = "{original_version}"',
        f'name = "portal-checker"\nversion = "{next_version}"',
    )
    assert "Module Structure (v3.0.0+)" in (tmp_path / "README.md").read_text()


def test_python_failure_blocks_release(tmp_path):
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/full-release-on-main-merge.yml").read_text()
    )
    steps = workflow["jobs"]["complete-release-process"]["steps"]
    test_step = next(step for step in steps if step["name"] == "Run Python tests")
    publish_index = next(
        i
        for i, step in enumerate(steps)
        if step["name"].startswith("Build and Push Official")
    )
    assert steps.index(test_step) < publish_index
    assert not test_step.get("continue-on-error", False)
    assert not workflow["jobs"]["complete-release-process"].get(
        "continue-on-error", False
    )
    for command, exit_code in [("python", 0), ("uv", 0)]:
        executable = tmp_path / command
        executable.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        executable.chmod(0o755)
    (tmp_path / "uv").write_text(
        '#!/bin/sh\ncase "$1" in run) exit 7 ;; *) exit 0 ;; esac\n'
    )
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", test_step["run"]],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        check=False,
    )
    assert result.returncode == 7


@pytest.mark.parametrize(
    "filename", ["full-release-on-main-merge.yml", "changelog.yml"]
)
def test_changelog_includes_scoped_and_breaking_commits(tmp_path, filename):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
    steps = next(iter(workflow["jobs"].values()))["steps"]
    step = next(
        step for step in steps if step.get("name", "").lower() == "generate changelog"
    )
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }

    def git(*args):
        subprocess.run(
            ["git", *args], cwd=tmp_path, env=git_env, check=True, capture_output=True
        )

    git("init")
    git("commit", "--allow-empty", "-m", "initial")
    git("tag", "v0.0.0")
    subjects = [
        "feat(metrics): expose metrics",
        "fix(api)!: fix format",
        "docs(readme): clarify install",
        "ci: require tests",
    ]
    for subject in subjects:
        git("commit", "--allow-empty", "-m", subject)
    git("tag", "v1.0.0")
    command = step["run"].replace(
        "${{ steps.bump_version.outputs.new_version }}", "1.0.0"
    )
    command = command.replace("${{ steps.bump_version.outputs.tag_name }}", "v1.0.0")
    command = command.replace("${{ github.repository }}", "didlawowo/portal-checker")
    subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", command],
        cwd=tmp_path,
        env=git_env,
        check=True,
        capture_output=True,
    )
    changelog = (tmp_path / "CHANGELOG.md").read_text()
    for subject in subjects:
        assert subject in changelog


def test_release_serializes_publication():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/full-release-on-main-merge.yml").read_text()
    )
    assert workflow["concurrency"] == {
        "group": "release-${{ github.repository }}",
        "cancel-in-progress": False,
    }


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("feat(metrics): expose metrics", "", "minor"),
        ("fix(release): block failures", "", "patch"),
        ("chore(ci): bump deps", "", "patch"),
        ("feat(api)!: change response", "", "major"),
        ("refactor(api): change response", "BREAKING CHANGE: new format", "major"),
    ],
)
def test_release_bump_uses_conventional_commit_messages(
    tmp_path, subject, body, expected
):
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/full-release-on-main-merge.yml").read_text()
    )
    step = next(
        step
        for step in workflow["jobs"]["complete-release-process"]["steps"]
        if step["name"] == "Determine version bump"
    )
    git = tmp_path / "git"
    git.write_text(
        '#!/bin/sh\ncase "$1" in\n'
        "describe) echo v3.0.28 ;;\n"
        "rev-parse) exit 0 ;;\n"
        'log) case "$*" in *--pretty=%s*) printf "%s\\n" "$SUBJECT" ;; '
        '*) printf "%s\\n" "$BODY" ;; esac ;;\nesac\n'
    )
    git.chmod(0o755)
    output = tmp_path / "output"
    subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "SUBJECT": subject,
            "BODY": body,
            "GITHUB_OUTPUT": str(output),
        },
        check=True,
        capture_output=True,
    )
    assert output.read_text().strip() == f"bump_type={expected}"
