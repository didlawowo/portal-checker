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
    project.write_text(
        project.read_text().replace(
            f'version = "{original_version}"', 'version = "3.1.0"', 1
        )
    )
    with pytest.raises(ValueError, match="Versions differ"):
        sync_version.synchronize(tmp_path, check=True)
    original_lock = (tmp_path / "uv.lock").read_text()
    sync_version.synchronize(tmp_path)
    sync_version.synchronize(tmp_path, check=True)
    assert (tmp_path / "uv.lock").read_text() == original_lock.replace(
        f'name = "portal-checker"\nversion = "{original_version}"',
        'name = "portal-checker"\nversion = "3.1.0"',
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
    for command, exit_code in [("pip", 0), ("python", 0), ("pytest", 7)]:
        executable = tmp_path / command
        executable.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        executable.chmod(0o755)
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", test_step["run"]],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        check=False,
    )
    assert result.returncode == 7


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("feat(metrics): expose metrics", "", "minor"),
        ("fix(release): block failures", "", "patch"),
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
