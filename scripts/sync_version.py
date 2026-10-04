"""Keep release metadata aligned with the version in pyproject.toml."""

import argparse
import re
import tomllib
from pathlib import Path


def synchronize(root: Path, check: bool = False) -> None:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Unsupported release version: {version}")
    patterns = {
        "README.md": [
            (r"(badge/version-)\d+\.\d+\.\d+", rf"\g<1>{version}"),
            (r"(Latest version: \*\*)\d+\.\d+\.\d+", rf"\g<1>{version}"),
            (r"(--version )\d+\.\d+\.\d+", rf"\g<1>{version}"),
            (
                r"(docker pull fizzbuzz2/portal-checker:)\d+\.\d+\.\d+",
                rf"\g<1>{version}",
            ),
        ],
        "helm/values.yaml": [(r'(?m)^(  tag: )"[^"]+"$', rf'\g<1>"{version}"')],
        "helm/Chart.yaml": [
            (r"(?m)^version: .*$", f"version: {version}"),
            (r"(?m)^appVersion: .*$", f'appVersion: "{version}"'),
            (r"(image: docker.io/fizzbuzz2/portal-checker:)\S+", rf"\g<1>{version}"),
        ],
        "uv.lock": [
            (r'(name = "portal-checker"\nversion = )"[^"]+"', rf'\g<1>"{version}"'),
        ],
    }
    updates = {}
    for filename, replacements in patterns.items():
        path = root / filename
        original = path.read_text()
        updated = original
        for pattern, replacement in replacements:
            updated, count = re.subn(pattern, replacement, updated)
            if not count:
                raise ValueError(f"Missing version field in {filename}: {pattern}")
        if updated != original:
            updates[path] = updated
    if check and updates:
        raise ValueError(
            "Versions differ: " + ", ".join(str(p.relative_to(root)) for p in updates)
        )
    for path, content in updates.items():
        path.write_text(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    synchronize(Path(__file__).resolve().parent.parent, check=args.check)
